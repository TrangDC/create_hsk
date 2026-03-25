# call_vertexai.py
import os
from google.oauth2 import service_account
import vertexai
from dotenv import load_dotenv
from vertexai.preview.generative_models import GenerativeModel, GenerationConfig, Part
import json
from typing import List, Dict, Any, Optional
import time
import threading

# Load environment variables
load_dotenv()

class VertexAIConfig:
    """Cấu hình cho Vertex AI API"""
    def __init__(self):
        self.project_id = os.getenv("PROJECT_ID")
        self.region = "global"  # Region mặc định
        self.model_name = "gemini-3-flash-preview"  # Model mặc định
        self.credentials = None
        
        # Thiết lập credentials
        self._setup_credentials()
    
    def _setup_credentials(self):
        """Thiết lập credentials từ service account"""
        try:
            service_account_data = {
                "type": os.getenv("TYPE"),
                "project_id": os.getenv("PROJECT_ID"),
                "private_key_id": os.getenv("PRIVATE_KEY_ID"),
                "private_key": os.getenv("PRIVATE_KEY").replace('\\n', '\n') if os.getenv("PRIVATE_KEY") else None,
                "client_email": os.getenv("CLIENT_EMAIL"),
                "client_id": os.getenv("CLIENT_ID", ""),
                "auth_uri": os.getenv("AUTH_URI"),
                "token_uri": os.getenv("TOKEN_URI"),
                "auth_provider_x509_cert_url": os.getenv("AUTH_PROVIDER_X509_CERT_URL"),
                "client_x509_cert_url": os.getenv("CLIENT_X509_CERT_URL"),
                "universe_domain": os.getenv("UNIVERSE_DOMAIN")
            }
            
            self.credentials = service_account.Credentials.from_service_account_info(
                service_account_data,
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            
        except Exception as e:
            print(f"Lỗi khi tạo credentials từ service account: {e}")
            self.credentials = None
    
    def initialize_vertex_ai(self):
        """Khởi tạo Vertex AI với credentials"""
        try:
            if not self.is_configured():
                raise ValueError("Vertex AI chưa được cấu hình đúng")
                
            vertexai.init(
                project=self.project_id, 
                location=self.region, 
                credentials=self.credentials
            )
            return True
            
        except Exception as e:
            print(f"Lỗi khi khởi tạo Vertex AI: {e}")
            return False
    
    def is_configured(self):
        """Kiểm tra xem API đã được cấu hình chưa"""
        return bool(self.project_id and self.credentials)
    
    def get_generation_config(self, temperature=0.5, top_p=0.8, max_output_tokens=None):
        """Trả về generation config cho model"""
        config = {
            "temperature": temperature,
            "top_p": top_p
        }
        
        if max_output_tokens:
            config["max_output_tokens"] = max_output_tokens
            
        return config
    
    def get_project_info(self):
        """Trả về thông tin project"""
        return {
            "project_id": self.project_id,
            "region": self.region,
            "model_name": self.model_name,
            "is_configured": self.is_configured()
        }

# Tạo instance global để sử dụng trong toàn bộ ứng dụng
vertex_ai_config = VertexAIConfig()

# Khởi tạo một lần khi module được import
is_vertex_initialized = vertex_ai_config.initialize_vertex_ai()

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

def validate_vertex_ai_config() -> bool:
    """
    Kiểm tra và khởi tạo cấu hình Vertex AI.
    
    Returns:
        bool: True nếu cấu hình hợp lệ và khởi tạo thành công, False nếu không.
    """
    if not vertex_ai_config.is_configured():
        print("Lỗi: Cấu hình Vertex AI không hợp lệ.")
        return False

    if not vertex_ai_config.initialize_vertex_ai():
        print("Lỗi: Không thể khởi tạo Vertex AI.")
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
    Gọi Vertex AI model với prompt, schema và nội dung (từ PDF hoặc text) để tạo câu hỏi.
    LƯU Ý: Phải cung cấp `pdf_file_paths` HOẶC `text_content`, không phải cả hai.
    """
    if not is_vertex_initialized:
        raise ConnectionError("Vertex AI chưa được khởi tạo thành công. Vui lòng kiểm tra credentials.")
    
    if pdf_file_paths is None and text_content is None:
        raise ValueError("Phải cung cấp hoặc 'pdf_file_paths' hoặc 'text_content'.")
    if pdf_file_paths and text_content:
        raise ValueError("Chỉ cung cấp một trong hai: 'pdf_file_paths' hoặc 'text_content'.")

    # --- Tải cấu hình (chỉ cần làm một lần) ---
    prompt_text = load_prompt_from_txt(prompt_file_path)
    response_schema = load_schema_from_json(schema_file_path)

    request_parts = [prompt_text]
    # Xây dựng nội dung yêu cầu dựa trên đầu vào
    if pdf_file_paths:
        for pdf_path in pdf_file_paths:
            try:
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                    request_parts.append(Part.from_data(data=pdf_bytes, mime_type="application/pdf"))
            except FileNotFoundError:
                raise FileNotFoundError(f"Không tìm thấy file PDF tại: {pdf_path}")
    elif text_content:
        # Nếu là nội dung text, coi nó như một tài liệu duy nhất
        request_parts.append(Part.from_text(text_content))

    generation_config = GenerationConfig(
        temperature=0.3,
        top_p=0.9,
        response_mime_type="application/json",
        response_schema=response_schema
    )
   
    model = GenerativeModel(vertex_ai_config.model_name)
    
    # --- Bắt đầu vòng lặp Retry ---
    last_exception = None
    for attempt in range(max_retries):
        try:
            print(f"Đang gửi yêu cầu đến Vertex AI... (Lần thử {attempt + 1}/{max_retries})")
            
            # Set up threading event to track completion
            response_event = threading.Event()
            response_container = [None]  # To store the response
            exception_container = [None]  # To store any exception

            def run_api_call():
                try:
                    response = model.generate_content(
                        contents=request_parts,
                        generation_config=generation_config,
                        stream=False
                    )
                    response_container[0] = response
                    response_event.set()  # Signal completion
                except Exception as e:
                    exception_container[0] = e
                    response_event.set()  # Signal completion even on error

            # Start the API call in a separate thread
            api_thread = threading.Thread(target=run_api_call)
            api_thread.start()

            # Wait for the API call to complete or timeout
            if not response_event.wait(timeout=timeout_seconds):
                # Timeout occurred
                print(f"   ⚠️ API call vượt quá {timeout_seconds} giây.")
                last_exception = TimeoutError(f"API call timed out after {timeout_seconds} seconds")
                if attempt < max_retries - 1:
                    print(f"   -> Thử lại sau {retry_delay} giây...")
                    time.sleep(retry_delay)
                continue  # Retry the API call

            # Check if an exception occurred during the API call
            if exception_container[0]:
                raise exception_container[0]

            # Process the response
            response = response_container[0]
            response_text = response.text.strip()
            
            if not response_text:
                raise ValueError("AI không trả về nội dung.")
            
            # Xử lý format markdown code block nếu có
            if response_text.startswith('```json') and response_text.endswith('```'):
                response_text = response_text[7:-3].strip()
            
            try:
                # Nếu parse JSON thành công, thoát khỏi vòng lặp và trả về kết quả
                return json.loads(response_text)
            except json.JSONDecodeError:
                print("--- LỖI PHÂN TÍCH JSON ---")
                print("AI đã trả về nội dung không hợp lệ:")
                print(response_text)
                print("--------------------------")
                raise ValueError("AI không trả về một đối tượng JSON hợp lệ.")

        except Exception as e:
            last_exception = e
            print(f"   ⚠️ Gặp lỗi ở lần thử {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                print(f"   -> Thử lại sau {retry_delay} giây...")
                time.sleep(retry_delay)
            else:
                print(f"   -> Đã thử lại {max_retries} lần nhưng không thành công.")
    
    # Nếu vòng lặp kết thúc mà không thành công, raise lỗi cuối cùng gặp phải
    raise ConnectionError(f"Không thể lấy dữ liệu từ Vertex AI sau {max_retries} lần thử.")


def get_credentials():
    """Lấy credentials và project_id từ config."""
    return vertex_ai_config.credentials, vertex_ai_config.project_id


class VertexClient:
    """Client wrapper để tương thích ngược với cách gọi cũ của api.callApi."""
    def __init__(self, project_id, creds, model_name="gemini-2.5-pro", region="us-central1"):
        # vertexai.init đã được gọi qua vertex_ai_config.initialize_vertex_ai() ở trên
        self.model = GenerativeModel(model_name)

    def send_data_to_AI(self, prompt, data=None, mime_type=None, temperature=0.5, top_p=0.8, file_paths=None):
        parts = []
        if data and mime_type:
            parts.append(Part.from_data(data=data, mime_type=mime_type))
        if file_paths:
            import mimetypes
            for path in file_paths:
                with open(path, "rb") as f:
                    file_data = f.read()
                mt = mimetypes.guess_type(path)[0] or "application/pdf"
                parts.append(Part.from_data(data=file_data, mime_type=mt))
        
        parts.append(Part.from_text(prompt))
        generation_config = GenerationConfig(temperature=temperature, top_p=top_p)
        response = self.model.generate_content(parts, generation_config=generation_config)
        return response.text