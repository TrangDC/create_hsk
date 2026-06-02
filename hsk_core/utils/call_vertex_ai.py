import os
import json
import time
import sys
import base64
import threading
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from dotenv import load_dotenv

# Load biến môi trường từ file .env
load_dotenv()

def get_resource_path(relative_path: str) -> Path:
    """
    Hỗ trợ lấy đường dẫn tài nguyên tuyệt đối, tương thích với cả 
    môi trường dev và khi đóng gói bằng PyInstaller.
    """
    if getattr(sys, 'frozen', False):
        # Nếu đang chạy từ file .exe
        base_path = Path(sys.executable).parent
    else:
        # Nếu đang chạy code script (nằm ở hsk_core/utils/call_vertex_ai.py)
        # Đi ngược lên 1 cấp để ra thư mục hsk_core
        base_path = Path(__file__).resolve().parent.parent
    
    return base_path / relative_path

def normalize_schema_for_openai(schema: Any) -> Any:
    """
    Chuẩn hóa JSON schema để tương thích với OpenAI structured outputs (strict).
    """
    def _make_nullable(prop_schema: Any) -> Any:
        if not isinstance(prop_schema, dict):
            return prop_schema

        result = normalize_schema_for_openai(prop_schema)

        t = result.get("type")
        if isinstance(t, list):
            if "null" not in t:
                result["type"] = t + ["null"]
            return result
        if isinstance(t, str):
            if t != "null":
                result["type"] = [t, "null"]
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

            for key in all_prop_keys:
                if key not in original_required_set:
                    properties[key] = _make_nullable(properties[key])

            normalized["required"] = all_prop_keys

    return normalized

def load_schema_from_json(schema_file_path: str) -> dict:
    """Đọc schema từ file JSON"""
    if not os.path.exists(schema_file_path):
        raise FileNotFoundError(f"Không tìm thấy file schema tại '{schema_file_path}'")
    
    with open(schema_file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_prompt_from_txt(prompt_file_path: str) -> str:
    """Đọc prompt từ file .txt"""
    if not os.path.exists(prompt_file_path):
        raise FileNotFoundError(f"Không tìm thấy file prompt tại '{prompt_file_path}'")
    
    with open(prompt_file_path, 'r', encoding='utf-8') as file:
        return file.read()


def get_openai_timeout_seconds() -> float:
    raw_timeout = os.getenv("OPENAI_TIMEOUT_SECONDS", "900")
    try:
        return float(raw_timeout)
    except ValueError:
        return 900.0


def get_openai_service_tier(default: Optional[str] = None) -> Optional[str]:
    raw_tier = default if default is not None else os.getenv("OPENAI_SERVICE_TIER", "auto")
    if raw_tier is None:
        return None

    normalized_tier = raw_tier.strip().lower()
    if normalized_tier in {"", "default"}:
        return None
    if normalized_tier in {"auto", "flex"}:
        return normalized_tier
    return None


def should_fallback_from_flex() -> bool:
    fallback_mode = os.getenv("OPENAI_FLEX_FALLBACK", "auto").strip().lower()
    return fallback_mode == "auto"


def is_flex_resource_unavailable_error(error: Exception) -> bool:
    status_code = getattr(error, "status_code", None)
    if status_code != 429:
        return False

    error_message = str(error).lower()
    return "resource unavailable" in error_message or "insufficient resources" in error_message


def create_chat_completion_with_fallback(client, kwargs: Dict[str, Any]):
    try:
        return client.chat.completions.create(**kwargs)
    except Exception as error:
        if kwargs.get("service_tier") == "flex" and should_fallback_from_flex() and is_flex_resource_unavailable_error(error):
            fallback_kwargs = dict(kwargs)
            fallback_kwargs["service_tier"] = "auto"
            print("   ⚠️ Flex tạm thời thiếu tài nguyên, chuyển sang service_tier=auto.")
            return client.chat.completions.create(**fallback_kwargs)
        raise

class VertexAIClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model_name = os.getenv("OPENAI_MODEL", "gpt-5.4")
        self.client = None
        self._initialized = False
        
    def _initialize_client(self):
        """Khởi tạo OpenAI client"""
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError("Chua cai thu vien openai. Hay chay: pip install openai") from e

        if not self.api_key:
            raise ValueError("Không tìm thấy OPENAI_API_KEY trong biến môi trường")

        self.client = OpenAI(api_key=self.api_key, timeout=get_openai_timeout_seconds())

    def init_ai(self):
        """Khởi tạo OpenAI client một lần duy nhất"""
        if not self._initialized:
            self._initialize_client()
            self._initialized = True
            print(f"✅ Đã khởi tạo OpenAI (Model: {self.model_name})")

    def generate_content(
        self,
        prompt_text: str,
        response_schema: Dict[str, Any],
        pdf_paths: Optional[List[str]] = None,
        text_context: Optional[str] = None,
        service_tier: Optional[str] = None,
        temperature: float = 0.2,
        max_retries: int = 3,
        timeout_seconds: int = 150,
        retry_delay: int = 5
    ) -> Union[Dict[str, Any], List[Any]]:
        """
        Gọi OpenAI để sinh nội dung có cấu trúc JSON.
        - prompt_text: String nội dung hướng dẫn.
        - response_schema: Dictionary định nghĩa cấu trúc JSON mong muốn.
        - pdf_paths: Danh sách các đường dẫn file PDF (nếu có).
        - text_context: Nội dung text bổ sung (nếu có).
        """
        self.init_ai()
        
        # Chuẩn hóa schema cho OpenAI
        response_schema = normalize_schema_for_openai(response_schema)
        
        # Chuẩn bị content blocks
        content_blocks = []
        
        # 1. Thêm context từ PDF (nếu có) - đọc text từ PDF
        if pdf_paths:
            try:
                import PyPDF2
            except ImportError:
                # Fallback: yêu cầu cài thư viện
                print("   ⚠️ Cảnh báo: pypdf2 chưa được cài đặt. Sẽ bỏ qua xử lý PDF.")
                print("   Để xử lý PDF, hãy chạy: pip install pypdf2")
                pdf_paths = None
            
            if pdf_paths:
                for path in pdf_paths:
                    if os.path.exists(path):
                        try:
                            with open(path, "rb") as f:
                                pdf_reader = PyPDF2.PdfReader(f)
                                pdf_text = ""
                                for page in pdf_reader.pages:
                                    pdf_text += page.extract_text() + "\n"
                            
                            if pdf_text.strip():
                                content_blocks.append({
                                    "type": "text",
                                    "text": f"=== Nội dung từ file: {os.path.basename(path)} ===\n{pdf_text}"
                                })
                                print(f"   📎 Đã đọc PDF: {os.path.basename(path)} ({len(pdf_text)} ký tự)")
                            else:
                                print(f"   ⚠️ Cảnh báo: PDF {path} không có text nào")
                        except Exception as e:
                            print(f"   ⚠️ Lỗi đọc PDF {path}: {e}")
                    else:
                        print(f"   ⚠️ Cảnh báo: Không tìm thấy file {path}")
        
        # 2. Thêm context từ text (nếu có)
        if text_context:
            content_blocks.append({"type": "text", "text": text_context})
        
        # 3. Thêm prompt
        content_blocks.append({"type": "text", "text": prompt_text})

        kwargs = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": content_blocks}],
            "temperature": temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_output",
                    "schema": response_schema,
                    "strict": True,
                },
            },
        }
        resolved_service_tier = get_openai_service_tier(service_tier)
        if resolved_service_tier:
            kwargs["service_tier"] = resolved_service_tier

        last_exception = None
        for attempt in range(max_retries):
            try:
                tier_label = kwargs.get("service_tier", "default")
                print(f"   Đang gửi yêu cầu đến OpenAI... (Lần thử {attempt + 1}/{max_retries}, tier={tier_label})")

                response_event = threading.Event()
                response_container = [None]
                exception_container = [None]

                def run_api_call():
                    try:
                        response = create_chat_completion_with_fallback(self.client, kwargs)
                        response_container[0] = response
                        response_event.set()
                    except Exception as e:
                        exception_container[0] = e
                        response_event.set()

                api_thread = threading.Thread(target=run_api_call)
                api_thread.start()

                if not response_event.wait(timeout=timeout_seconds):
                    print(f"   ⚠️ API call vượt quá {timeout_seconds} giây.")
                    last_exception = TimeoutError(f"API call timed out after {timeout_seconds} seconds")
                    if attempt < max_retries - 1:
                        print(f"   -> Thử lại sau {retry_delay} giây...")
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
                    raise ValueError("AI không trả về nội dung.")

                # Loại bỏ markdown code blocks nếu có
                if response_text.startswith('```json') and response_text.endswith('```'):
                    response_text = response_text[7:-3].strip()
                elif response_text.startswith('```') and response_text.endswith('```'):
                    response_text = response_text[3:-3].strip()

                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    print("--- LỖI PHÂN TÍCH JSON ---")
                    print("AI đã trả về nội dung không hợp lệ:")
                    print(response_text[:500])  # In 500 ký tự đầu để debug
                    print("-" * 30)
                    raise ValueError("AI không trả về một đối tượng JSON hợp lệ.")

            except Exception as e:
                last_exception = e
                print(f"   ⚠️ Gặp lỗi ở lần thử {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    print(f"   -> Thử lại sau {retry_delay} giây...")
                    time.sleep(retry_delay)
                else:
                    print(f"   -> Đã thử lại {max_retries} lần nhưng không thành công.")

        raise ConnectionError(f"Không thể lấy dữ liệu từ OpenAI sau {max_retries} lần thử. Lỗi cuối: {last_exception}")

# Khởi tạo client dùng chung cho toàn bộ module
ai_client = VertexAIClient()

# --- KHỐI TEST THỬ NGHIỆM ---
if __name__ == "__main__":
    # Test thử với một prompt đơn giản
    test_prompt = "Hãy tạo 2 từ vựng tiếng Trung HSK1 liên quan đến chủ đề gia đình."
    
    # Định nghĩa schema mong muốn
    test_schema = {
        "type": "object",
        "properties": {
            "vocab_list": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "word": {"type": "string"},
                        "pinyin": {"type": "string"},
                        "meaning": {"type": "string"}
                    }
                }
            }
        }
    }

    print("--- Đang chạy thử nghiệm OpenAI Client ---")
    try:
        # Lưu ý: Cần có file .env đúng thông tin để chạy được
        result = ai_client.generate_content(test_prompt, test_schema)
        print("✅ Kết quả JSON từ OpenAI:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as err:
        print(f"❌ Lỗi kiểm thử: {err}")