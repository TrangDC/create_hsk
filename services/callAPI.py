import base64
import os


def normalize_schema_for_openai(schema):
    """
    Chuan hoa JSON schema de tuong thich OpenAI structured outputs.
    Tu dong them additionalProperties=False cho moi object schema neu chua co.
    """
    if isinstance(schema, list):
        return [normalize_schema_for_openai(item) for item in schema]

    if not isinstance(schema, dict):
        return schema

    normalized = {}
    for key, value in schema.items():
        normalized[key] = normalize_schema_for_openai(value)

    is_object_schema = normalized.get("type") == "object" or "properties" in normalized
    if is_object_schema and "additionalProperties" not in normalized:
        normalized["additionalProperties"] = False

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

        self.client = OpenAI(api_key=api_key)
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

        model_lower = self.model_name.lower()
        is_o_model = any(m in model_lower for m in ["o1", "o3", "gpt-5"])
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

        response = self.client.chat.completions.create(**kwargs)
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
    
    
