import base64
import os


def get_openai_timeout_seconds():
    raw_timeout = os.getenv("OPENAI_TIMEOUT_SECONDS", "900")
    try:
        return float(raw_timeout)
    except ValueError:
        return 900.0


def get_openai_service_tier(default=None):
    raw_tier = default if default is not None else os.getenv("OPENAI_SERVICE_TIER", "auto")
    if raw_tier is None:
        return None

    normalized_tier = raw_tier.strip().lower()
    if normalized_tier in {"", "default"}:
        return None
    if normalized_tier in {"auto", "flex"}:
        return normalized_tier
    return None


def should_fallback_from_flex():
    fallback_mode = os.getenv("OPENAI_FLEX_FALLBACK", "auto").strip().lower()
    return fallback_mode == "auto"


def is_flex_resource_unavailable_error(error):
    status_code = getattr(error, "status_code", None)
    if status_code != 429:
        return False

    error_message = str(error).lower()
    return "resource unavailable" in error_message or "insufficient resources" in error_message


def create_chat_completion_with_fallback(client, kwargs):
    try:
        return client.chat.completions.create(**kwargs)
    except Exception as error:
        if kwargs.get("service_tier") == "flex" and should_fallback_from_flex() and is_flex_resource_unavailable_error(error):
            fallback_kwargs = dict(kwargs)
            fallback_kwargs["service_tier"] = "auto"
            print("Warning: Flex tam thoi thieu tai nguyen, chuyen sang service_tier=auto.")
            return client.chat.completions.create(**fallback_kwargs)
        raise


def normalize_schema_for_openai(schema):
    """
    Chuan hoa JSON schema de tuong thich OpenAI structured outputs.
    Tu dong:
    - Chuyen type tu OBJECT/STRING/ARRAY (viet hoa) sang object/string/array (viet thuong)
    - Them additionalProperties=False cho moi object schema.
    - Dam bao required chua day du tat ca key trong properties.
    - Cac field optional cu se duoc cho phep null de van tuong thich voi strict mode.
    """
    def _make_nullable(prop_schema):
        if not isinstance(prop_schema, dict):
            return prop_schema

        result = normalize_schema_for_openai(prop_schema)

        schema_type = result.get("type")
        if isinstance(schema_type, str):
            schema_type = schema_type.lower()

        if isinstance(schema_type, list):
            normalized_types = [item.lower() if isinstance(item, str) else item for item in schema_type]
            if "null" not in normalized_types:
                result["type"] = normalized_types + ["null"]
            else:
                result["type"] = normalized_types
            return result

        if isinstance(schema_type, str):
            if schema_type != "null":
                result["type"] = [schema_type, "null"]
            return result

        for union_key in ("anyOf", "oneOf"):
            if union_key in result and isinstance(result[union_key], list):
                has_null = any(
                    isinstance(item, dict) and item.get("type") == "null"
                    for item in result[union_key]
                )
                if not has_null:
                    result[union_key].append({"type": "null"})
                return result

        return {"anyOf": [result, {"type": "null"}]}

    if isinstance(schema, list):
        return [normalize_schema_for_openai(item) for item in schema]

    if not isinstance(schema, dict):
        return schema

    normalized = {}
    for key, value in schema.items():
        if key == "type" and isinstance(value, str):
            # Chuyển type sang chữ thường (ví dụ: OBJECT -> object, STRING -> string)
            normalized[key] = value.lower()
        else:
            normalized[key] = normalize_schema_for_openai(value)

    is_object_schema = normalized.get("type") == "object" or "properties" in normalized
    if is_object_schema:
        normalized["additionalProperties"] = False

        properties = normalized.get("properties")
        if isinstance(properties, dict):
            original_required = normalized.get("required", [])
            if not isinstance(original_required, list):
                original_required = []

            original_required_set = set(original_required)
            all_prop_keys = list(properties.keys())

            for prop_key in all_prop_keys:
                if prop_key not in original_required_set:
                    properties[prop_key] = _make_nullable(properties[prop_key])

            normalized["required"] = all_prop_keys

    return normalized


class VertexClient:
    def __init__(self, project_id, creds, model, region="us-central1"):
        # Giu nguyen interface cu, doi backend sang OpenAI.
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError("Chua cai thu vien openai. Hay chay: pip install openai") from e

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Khong tim thay OPENAI_API_KEY trong bien moi truong.")

        self.client = OpenAI(api_key=api_key, timeout=get_openai_timeout_seconds())
        self.model_name = model

    def send_data_to_AI(
        self,
        prompt,
        data=None,
        mime_type=None,
        temperature=0.5,
        top_p=0.8,
        response_mime_type=None,
        response_schema=None,
        service_tier=None,
    ):
        content_blocks = []

        if data and mime_type:
            b64_data = base64.b64encode(data).decode("utf-8")
            if mime_type.startswith("image/"):
                content_blocks.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{b64_data}"},
                    }
                )
            else:
                content_blocks.append(
                    {
                        "type": "file",
                        "file": {
                            "filename": f"input.{mime_type.split('/')[-1]}",
                            "file_data": f"data:{mime_type};base64,{b64_data}",
                        },
                    }
                )

        content_blocks.append({"type": "text", "text": prompt})

        kwargs = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": content_blocks}],
        }
        resolved_service_tier = get_openai_service_tier(service_tier)
        if resolved_service_tier:
            kwargs["service_tier"] = resolved_service_tier

        model_lower = self.model_name.lower()
        is_o_model = any(m in model_lower for m in ["o1", "o3", "gpt-5.4"])
        if not is_o_model:
            kwargs["temperature"] = temperature
            kwargs["top_p"] = top_p

        if response_mime_type == "application/json":
            if isinstance(response_schema, dict) and response_schema:
                safe_schema = normalize_schema_for_openai(response_schema)
                kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "structured_output",
                        "schema": safe_schema,
                        "strict": True,
                    },
                }
            else:
                kwargs["response_format"] = {"type": "json_object"}

        response = create_chat_completion_with_fallback(self.client, kwargs)
        content = response.choices[0].message.content

        if isinstance(content, list):
            content = "".join(block.get("text", "") for block in content if isinstance(block, dict))
        content = (content or "").strip()

        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        return content.strip()

# import vertexai
# import os 

# from vertexai.generative_models import GenerativeModel, Part, GenerationConfig

# class VertexClient : 
#     def __init__(self, project_id , creds , model ,  region="us-central1"):
#         vertexai.init(
#             project=project_id,
#             location=region,
#             credentials=creds
#         )
#         self.model = GenerativeModel(model)

#     def send_data_to_AI(self, prompt ,data = None , mime_type = None ,temperature=0.5, top_p=0.8, response_mime_type=None, response_schema=None):
#         parts = []
#         if data and mime_type:
#             parts.append(Part.from_data(data=data, mime_type=mime_type))
#         parts.append(Part.from_text(prompt))
        
#         # Thiết lập config hỗ trợ Structured Output
#         config_args = {
#             "temperature": temperature,
#             "top_p": top_p
#         }
        
#         if response_mime_type:
#             config_args["response_mime_type"] = response_mime_type
            
#         if response_schema:
#             config_args["response_schema"] = response_schema
            
#         generation_config = GenerationConfig(**config_args)
        
#         response = self.model.generate_content(parts, generation_config=generation_config)
#         return response.text
    
    
