# call_vertexai.py
# OpenAI-based implementation (Gemini/Vertex AI removed)
import os
import json
import base64
import time
import threading
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class VertexAIConfig:
    """DEPRECATED: Kept for backward compatibility only. Use OpenAI instead."""
    pass



def load_schema_from_json(schema_file_path: str) -> dict:
    """
    Đọc và tải cấu trúc schema từ một file JSON.
    """
    try:
        if not os.path.exists(schema_file_path):
            raise FileNotFoundError(f"Không tìm thấy file schema tại: '{schema_file_path}'")
        
        with open(schema_file_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
        return schema
    except json.JSONDecodeError as e:
        raise ValueError(f"Lỗi khi phân tích cú pháp file JSON schema '{schema_file_path}': {e}")

def normalize_schema_for_openai(schema: Any) -> Any:
    """
    Chuan hoa JSON schema de tuong thich voi OpenAI structured outputs (strict).

    Runtime normalize:
    - Them additionalProperties=False cho moi object schema.
    - Dam bao required chua day du tat ca key trong properties.
    - Cac field truoc do KHONG bat buoc (optional) se duoc cho phep null de
      giam nguy co vo logic schema cu khi bi nang cap thanh required.
    """
    def _make_nullable(prop_schema: Any) -> Any:
        if not isinstance(prop_schema, dict):
            return prop_schema

        result = normalize_schema_for_openai(prop_schema)

        # Da co nullable roi
        t = result.get("type")
        if isinstance(t, list):
            if "null" not in t:
                result["type"] = t + ["null"]
            return result
        if isinstance(t, str):
            if t != "null":
                result["type"] = [t, "null"]
            return result

        # Neu dung anyOf/oneOf thi chen them null schema
        for union_key in ("anyOf", "oneOf"):
            if union_key in result and isinstance(result[union_key], list):
                has_null = any(
                    isinstance(item, dict) and item.get("type") == "null"
                    for item in result[union_key]
                )
                if not has_null:
                    result[union_key].append({"type": "null"})
                return result

        # Khong xac dinh type -> fallback anyOf
        return {"anyOf": [result, {"type": "null"}]}

    if isinstance(schema, list):
        return [normalize_schema_for_openai(item) for item in schema]

    if not isinstance(schema, dict):
        return schema

    normalized = {}
    for key, value in schema.items():
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

            # Optional cu -> nullable, roi dua vao required
            for key in all_prop_keys:
                if key not in original_required_set:
                    properties[key] = _make_nullable(properties[key])

            normalized["required"] = all_prop_keys

    return normalized


def load_prompt_from_txt(prompt_file_path: str) -> str:
    """
    Đọc nội dung prompt từ file .txt.
    
    Args:
        prompt_file_path: Đường dẫn đến file .txt chứa prompt
        
    Returns:
        str: Nội dung prompt
        
    Raises:
        FileNotFoundError: Nếu file không tồn tại
        IOError: Nếu có lỗi khi đọc file
    """
    if not os.path.exists(prompt_file_path):
        raise FileNotFoundError(f"Không tìm thấy file prompt tại '{prompt_file_path}'")
    
    with open(prompt_file_path, 'r', encoding='utf-8') as file:
        return file.read()


def validate_openai_config() -> bool:
    """
    Kiểm tra cấu hình OpenAI.
    
    Returns:
        bool: True nếu API key được cấu hình, False nếu không.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Lỗi: Cấu hình OpenAI không hợp lệ. Kiểm tra biến OPENAI_API_KEY.")
        return False
    return True

# --- HÀM MỚI ---
def extract_structured_data_from_pdf(
    pdf_path: str,
    prompt_file_path: str,
    schema_file_path: str,
    max_retries: int = 3,
    retry_delay: int = 5,
    timeout_seconds: int = 180
) -> Dict[str, Any]:
    """
    Hàm chuyên dụng để bóc tách một file PDF bài khóa thành dữ liệu có cấu trúc.
    """
    print(f"   [Tiền xử lý] Bắt đầu bóc tách dữ liệu từ file: {os.path.basename(pdf_path)}")
    # Hàm này là một trường hợp đặc biệt của `generate_content`, nên ta gọi nó
    return generate_content(
        pdf_file_paths=[pdf_path],
        text_content=None,
        prompt_file_path=prompt_file_path,
        schema_file_path=schema_file_path,
        max_retries=max_retries,
        retry_delay=retry_delay,
        timeout_seconds=timeout_seconds
    )

def generate_content(
    prompt_file_path: str,
    schema_file_path: str,
    pdf_file_paths: Optional[List[str]] = None,
    text_content: Optional[str] = None,
    max_retries: int = 5,
    retry_delay: int = 5,
    timeout_seconds: int = 150
) -> Dict[str, Any] | List[Any]:
    """
    Goi model voi prompt, schema va noi dung (tu PDF hoac text) de tao cau hoi.
    LUU Y: Phai cung cap `pdf_file_paths` HOAC `text_content`, khong phai ca hai.
    """
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ImportError("Chua cai thu vien openai. Hay chay: pip install openai") from e

    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ConnectionError("Khong tim thay OPENAI_API_KEY trong bien moi truong.")

    if pdf_file_paths is None and text_content is None:
        raise ValueError("Phai cung cap hoac 'pdf_file_paths' hoac 'text_content'.")
    if pdf_file_paths and text_content:
        raise ValueError("Chi cung cap mot trong hai: 'pdf_file_paths' hoac 'text_content'.")

    prompt_text = load_prompt_from_txt(prompt_file_path)
    response_schema = normalize_schema_for_openai(load_schema_from_json(schema_file_path))

    content_blocks = []
    if pdf_file_paths:
        for pdf_path in pdf_file_paths:
            try:
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
                content_blocks.append({
                    "type": "file",
                    "file": {
                        "filename": os.path.basename(pdf_path),
                        "file_data": f"data:application/pdf;base64,{b64_pdf}",
                    },
                })
            except FileNotFoundError:
                raise FileNotFoundError(f"Khong tim thay file PDF tai: {pdf_path}")
    elif text_content:
        content_blocks.append({"type": "text", "text": text_content})

    content_blocks.append({"type": "text", "text": prompt_text})

    openai_client = OpenAI(api_key=openai_api_key)
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4.1")
    if openai_model.lower().startswith("gemini"):
        openai_model = "gpt-4.1"

    kwargs = {
        "model": openai_model,
        "messages": [{"role": "user", "content": content_blocks}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "structured_output",
                "schema": response_schema,
                "strict": True,
            },
        },
    }

    last_exception = None
    for attempt in range(max_retries):
        try:
            print(f"Dang gui yeu cau den OpenAI... (Lan thu {attempt + 1}/{max_retries})")

            response_event = threading.Event()
            response_container = [None]
            exception_container = [None]

            def run_api_call():
                try:
                    response = openai_client.chat.completions.create(**kwargs)
                    response_container[0] = response
                    response_event.set()
                except Exception as e:
                    exception_container[0] = e
                    response_event.set()

            api_thread = threading.Thread(target=run_api_call)
            api_thread.start()

            if not response_event.wait(timeout=timeout_seconds):
                print(f"   Warning: API call vuot qua {timeout_seconds} giay.")
                last_exception = TimeoutError(f"API call timed out after {timeout_seconds} seconds")
                if attempt < max_retries - 1:
                    print(f"   -> Thu lai sau {retry_delay} giay...")
                    time.sleep(retry_delay)
                continue

            if exception_container[0]:
                raise exception_container[0]

            response = response_container[0]
            response_text = response.choices[0].message.content
            if isinstance(response_text, list):
                response_text = "".join(
                    block.get("text", "") for block in response_text if isinstance(block, dict)
                )
            response_text = (response_text or "").strip()

            if not response_text:
                raise ValueError("AI khong tra ve noi dung.")

            if response_text.startswith('```json') and response_text.endswith('```'):
                response_text = response_text[7:-3].strip()
            elif response_text.startswith('```') and response_text.endswith('```'):
                response_text = response_text[3:-3].strip()

            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                print("--- LOI PHAN TICH JSON ---")
                print("AI da tra ve noi dung khong hop le:")
                print(response_text)
                print("--------------------------")
                raise ValueError("AI khong tra ve mot doi tuong JSON hop le.")

        except Exception as e:
            last_exception = e
            print(f"   Warning: Gap loi o lan thu {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                print(f"   -> Thu lai sau {retry_delay} giay...")
                time.sleep(retry_delay)
            else:
                print(f"   -> Da thu lai {max_retries} lan nhung khong thanh cong.")

    raise ConnectionError(f"Khong the lay du lieu tu OpenAI sau {max_retries} lan thu. Loi cuoi: {last_exception}")


class VertexClient:
    def __init__(self, project_id, creds, model, region="us-central1"):
        # Giu nguyen interface cu, doi backend sang OpenAI.
        try:
            from openai import OpenAI
            model= "gpt-5.4"
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

