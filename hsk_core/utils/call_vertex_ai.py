import os
import json
import time
import sys
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from dotenv import load_dotenv

import vertexai
from google.oauth2 import service_account
from vertexai.generative_models import GenerativeModel, GenerationConfig, Part

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

class VertexAIClient:
    def __init__(self):
        self.project_id = os.getenv("PROJECT_ID")
        self.location = os.getenv("REGION", "us-central1")
        self.model_name = os.getenv("MODEL_NAME", "gemini-2.5-pro") # Dòng model ổn định và nhanh
        self.credentials = self._load_credentials()
        self._initialized = False
        
    def _load_credentials(self):
        """Thiết lập credentials từ biến môi trường .env"""
        try:
            service_account_info = {
                "type": os.getenv("TYPE"),
                "project_id": os.getenv("PROJECT_ID"),
                "private_key_id": os.getenv("PRIVATE_KEY_ID"),
                "private_key": os.getenv("PRIVATE_KEY", "").replace('\\n', '\n'),
                "client_email": os.getenv("CLIENT_EMAIL"),
                "token_uri": os.getenv("TOKEN_URI"),
            }
            # Kiểm tra nếu thiếu thông tin quan trọng
            if not service_account_info["project_id"] or not service_account_info["private_key"]:
                return None
                
            return service_account.Credentials.from_service_account_info(service_account_info)
        except Exception as e:
            print(f"❌ Lỗi cấu hình Credentials: {e}")
            return None

    def init_ai(self):
        """Khởi tạo Vertex AI một lần duy nhất"""
        if not self._initialized:
            if not self.credentials:
                raise ValueError("Cấu hình Vertex AI không hợp lệ. Kiểm tra file .env")
            
            vertexai.init(
                project=self.project_id,
                location=self.location,
                credentials=self.credentials
            )
            self._initialized = True
            print(f"✅ Đã khởi tạo Vertex AI (Project: {self.project_id}, Model: {self.model_name})")

    def generate_content(
        self,
        prompt_text: str,
        response_schema: Dict[str, Any],
        pdf_paths: Optional[List[str]] = None,
        text_context: Optional[str] = None,
        temperature: float = 0.2,
        max_retries: int = 3
    ) -> Union[Dict[str, Any], List[Any]]:
        """
        Gọi Vertex AI để sinh nội dung.
        - prompt_text: String nội dung hướng dẫn.
        - response_schema: Dictionary định nghĩa cấu trúc JSON mong muốn.
        - pdf_paths: Danh sách các đường dẫn file PDF (nếu có).
        """
        self.init_ai()
        
        # Chuẩn bị danh sách các "Parts" gửi cho AI
        request_parts = [prompt_text]
        
        # 1. Thêm context từ text (nếu có)
        if text_context:
            request_parts.append(text_context)
            
        # 2. Thêm context từ PDF (nếu có)
        if pdf_paths:
            for path in pdf_paths:
                if os.path.exists(path):
                    with open(path, "rb") as f:
                        pdf_data = f.read()
                        request_parts.append(Part.from_data(data=pdf_data, mime_type="application/pdf"))
                    print(f"   📎 Đã đính kèm PDF: {os.path.basename(path)}")
                else:
                    print(f"   ⚠️ Cảnh báo: Không tìm thấy file {path}")

        # Cấu hình phản hồi dạng JSON
        generation_config = GenerationConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=response_schema
        )

        model = GenerativeModel(self.model_name)
        
        # Vòng lặp thử lại (Retry logic)
        for attempt in range(max_retries):
            try:
                response = model.generate_content(
                    request_parts,
                    generation_config=generation_config
                )
                
                if not response.text:
                    raise ValueError("AI trả về nội dung rỗng.")
                
                # Parse kết quả JSON
                return json.loads(response.text)

            except Exception as e:
                print(f"   ⚠️ Lần thử {attempt + 1} thất bại: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                else:
                    print(f"❌ Thất bại sau {max_retries} lần thử.")
                    raise

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

    print("--- Đang chạy thử nghiệm Vertex AI Client ---")
    try:
        # Lưu ý: Cần có file .env đúng thông tin để chạy được
        result = ai_client.generate_content(test_prompt, test_schema)
        print("Kết quả JSON từ AI:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as err:
        print(f"Lỗi kiểm thử: {err}")