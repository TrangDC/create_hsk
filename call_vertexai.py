# call_vertexai.py
import os
from google.oauth2 import service_account
import vertexai
from dotenv import load_dotenv
from vertexai.preview.generative_models import GenerativeModel, GenerationConfig, Part
import json
from typing import List, Dict, Any
import time

# Load environment variables
load_dotenv()

class VertexAIConfig:
    """Cấu hình cho Vertex AI API"""
    def __init__(self):
        self.project_id = os.getenv("PROJECT_ID")
        self.region = "us-central1"  # Region mặc định
        self.model_name = "gemini-2.5-pro"  # Model mặc định
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

def generate_content_from_pdfs(
    pdf_file_paths: List[str], 
    prompt_file_path: str,
    schema_file_path: str,
    max_retries: int = 5,
    retry_delay: int = 5
) -> Dict[str, Any] | List[Any]:
    """
    Gọi Vertex AI model với PDF, prompt, và schema để tạo ra nội dung có cấu trúc.

    Returns:
        Dict | List: Dữ liệu đã được phân tích từ JSON do AI trả về.
        
    Raises:
        ValueError: Nếu AI không trả về nội dung hoặc nội dung không phải là JSON hợp lệ.
        FileNotFoundError: Nếu không tìm thấy file PDF, prompt, hoặc schema.
        Exception: Các lỗi khác từ Vertex AI.
    """
    if not is_vertex_initialized:
        raise ConnectionError("Vertex AI chưa được khởi tạo thành công. Vui lòng kiểm tra credentials.")

    # --- Tải cấu hình (chỉ cần làm một lần) ---
    prompt_text = load_prompt_from_txt(prompt_file_path)
    response_schema = load_schema_from_json(schema_file_path)

    request_parts = [prompt_text]
    for pdf_path in pdf_file_paths:
        try:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
                request_parts.append(Part.from_data(data=pdf_bytes, mime_type="application/pdf"))
        except FileNotFoundError:
            raise FileNotFoundError(f"Không tìm thấy file PDF tại: {pdf_path}")

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
            response = model.generate_content(
                contents=request_parts,
                generation_config=generation_config,
                stream=False
            )
            
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
    raise ConnectionError(f"Không thể lấy dữ liệu từ Vertex AI sau {max_retries} lần thử. Lỗi cuối cùng: {last_exception}")


if __name__ == '__main__':
    print("--- Chạy ở chế độ kiểm thử module callvertexai.py ---")

    if not is_vertex_initialized:
        print("Thoát vì Vertex AI không thể khởi tạo.")
        exit(1)
    # Đường dẫn đến các file PDF, prompt và schema để kiểm thử
    test_pdf_files = [
        os.path.join("draft", "HSK5 课文 第五课 _compressed.pdf"),
        os.path.join("draft", "TT_H5_B1.pdf"),
    ]
    test_prompt_path = os.path.join("resources/prompt_tao", "hsk1", "hsk1_prompt_6_7_8.txt")
    test_schema_path = os.path.join("resources/schema", "hsk1", "hsk1_prompt_6_7_8.json")
    
    # Kiểm tra sự tồn tại của các file test
    if not all(os.path.exists(p) for p in test_pdf_files + [test_prompt_path, test_schema_path]):
         print("\nLỗi: Không tìm thấy một hoặc nhiều file/thư mục cần thiết cho việc test.")
         print("Vui lòng kiểm tra cấu trúc thư mục: draft/, prompts/hsk1/, schemas/hsk1/")
         exit(1)
    
    try:
        print(f"\nSử dụng prompt từ: '{test_prompt_path}'")
        print(f"Sử dụng schema từ: '{test_schema_path}'")
        
        # Gọi hàm chính của module
        generated_data = generate_content_from_pdfs(
            pdf_file_paths=test_pdf_files,
            prompt_file_path=test_prompt_path,
            schema_file_path=test_schema_path
        )
        
        print("\n--- ✅ Nhận được dữ liệu hợp lệ từ AI ---")
        
        # In dữ liệu ra màn hình với định dạng đẹp
        print(json.dumps(generated_data, indent=2, ensure_ascii=False))
        
        # Lưu vào file để kiểm tra
        output_filename = "test_output.json"
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(generated_data, f, ensure_ascii=False, indent=4)
        print(f"\nKết quả kiểm thử đã được lưu vào file: '{output_filename}'")

    except (FileNotFoundError, ValueError, ConnectionError) as e:
        print(f"\n--- ❌ ĐÃ XẢY RA LỖI ---")
        print(e)
    except Exception as e:
        print(f"\n--- ❌ ĐÃ XẢY RA LỖI KHÔNG MONG MUỐN ---")
        print(f"Lỗi: {e}")