import os
import time
from google import genai
from google.genai import types
from google.oauth2 import service_account
from dotenv import load_dotenv

# Load biến môi trường
load_dotenv()

# --- CẤU HÌNH ---
PROJECT_ID = os.getenv("PROJECT_ID", "onluyen-media")

class ImageGenerationService:
    def __init__(self):
        self.credentials = self._get_vertex_ai_credentials()
        self.project_id = PROJECT_ID
        self.model_name = "gemini-3-pro-image-preview"
        self.location = "global"
        self.client = None

        if self.credentials and self.project_id:
            try:
                self.client = genai.Client(
                    vertexai=True, 
                    project=self.project_id, 
                    location=self.location, 
                    credentials=self.credentials
                )
            except Exception as e:
                print(f"❌ Lỗi khởi tạo Client trong __init__: {e}")
        else:
            print("⚠️ Cảnh báo: Không thể khởi tạo Client do thiếu Credentials.")

    def _get_vertex_ai_credentials(self):
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

            return service_account.Credentials.from_service_account_info(
                service_account_data,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
        except Exception as e:
            print(f"❌ Lỗi tạo credentials: {e}")
            return None

    def generate_image(self, prompt, aspect_ratio="1:1", max_retries=5, retry_delay=5):
        """
        Tạo ảnh với cơ chế KIÊN TRÌ (Retry mạnh mẽ).
        Chỉ trả về None khi đã thử hết max_retries.
        """
        if not self.credentials or not self.project_id:
            print("❌ Lỗi: Thiếu Credentials hoặc Project ID")
            return None

        for attempt in range(1, max_retries + 1):
            try:
                # Re-init client để tránh stale connection
                client = genai.Client(
                    vertexai=True, 
                    project=self.project_id, 
                    location=self.location, 
                    credentials=self.credentials
                )

                if attempt > 1:
                    print(f"   🔄 Thử lại lần {attempt}/{max_retries}...")
                else:
                    print(f"   🎨 Đang sinh ảnh: {prompt[:30]}...")

                response = client.models.generate_content(
                    model=self.model_name,
                    contents=f"Vẽ hình ảnh minh họa chính xác cho mô tả sau: {prompt}",
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        candidate_count=1,
                        image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
                    )
                )

                # Kiểm tra dữ liệu ảnh
                if response.parts:
                    for part in response.parts:
                        if part.inline_data and part.inline_data.data:
                            # ✅ THÀNH CÔNG -> Trả về luôn
                            return part.inline_data.data

                # ❌ NẾU KHÔNG CÓ DATA -> Raise Exception để kích hoạt cơ chế retry bên dưới
                print(f"      ⚠️ API trả về rỗng (Lần {attempt}).")
                raise Exception("Empty response from API (No image data)")

            except Exception as e:
                # Bắt mọi lỗi (bao gồm lỗi Empty response vừa raise ở trên)
                print(f"      ❌ Gặp lỗi (Lần {attempt}): {str(e)}")
                
                if attempt < max_retries:
                    print(f"      ⏳ Đợi {retry_delay} giây trước khi thử lại...")
                    time.sleep(retry_delay)
                else:
                    print("      ❌ ĐÃ THẤT BẠI HOÀN TOÀN sau tất cả các lần thử.")
                    return None
        
        return None

# --- KHỐI TEST ---
if __name__ == "__main__":
    service = ImageGenerationService()
    test_prompt = "Một con mèo đang ngủ."
    img = service.generate_image(test_prompt)
    if img: print("Thành công")