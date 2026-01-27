import os
import time
from google import genai
from google.genai import types
from google.oauth2 import service_account
import vertexai
from vertexai.preview.vision_models import ImageGenerationModel
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

        # 2. Cấu hình cho Imagen (Cũ - HSK)
        self.imagen_model_name = "imagen-4.0-ultra-generate-001"
        self.imagen_location = "us-central1" # Imagen bắt buộc us-central1
        self.imagen_model = None

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

            # Init Imagen (Vertex AI SDK cũ)
            try:
                vertexai.init(
                    project=self.project_id,
                    location=self.imagen_location,
                    credentials=self.credentials
                )
                self.imagen_model = ImageGenerationModel.from_pretrained(self.imagen_model_name)
                print(f"🚀 Đã khởi tạo Imagen Model: {self.imagen_model_name}")
            except Exception as e:
                print(f"❌ Lỗi khởi tạo Imagen Model: {e}")    
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

    def generate_image(self, prompt, aspect_ratio="1:1", max_retries=5, retry_delay=3):
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

    def generate_image_legacy(self, prompt, max_retries=3):
        """
        Tạo ảnh sử dụng Imagen Ultra (Cho HSK).
        Code logic lấy từ yêu cầu cũ.
        """
        if not self.imagen_model:
            print("❌ Lỗi: Imagen Model chưa được khởi tạo")
            return None

        # for attempt in range(1, max_retries + 1):
        #     try:
        #         if attempt > 1: print(f"   🔄 Imagen retry ({attempt}/{max_retries})...")
        #         else: print(f"   🎨 [Imagen] Đang sinh ảnh: {prompt[:30]}...")

        #         # Gọi API Imagen cũ
        #         response = self.imagen_model.generate_images(
        #             prompt=f"Vẽ hình ảnh theo phong cách thật, tả thực, minh họa chính xác cho mô tả sau: {prompt}. Không vẽ theo phong cách hoạt hình hay tranh vẽ tay.",
        #             number_of_images=1, # Chỉ lấy 1 ảnh để tiết kiệm
        #             aspect_ratio="1:1",
        #             negative_prompt="",
        #             person_generation="allow_all",
        #             safety_filter_level="block_few",
        #             add_watermark=False,
        #         )

        #         if response.images and len(response.images) > 0:
        #             # Imagen SDK trả về object GeneratedImage
        #             # Ta lấy bytes trực tiếp từ thuộc tính _image_bytes (hoặc save vào buffer)
        #             # Cách chuẩn nhất với SDK này là truy cập ._image_bytes
        #             return response.images[0]._image_bytes
                
        #         print(f"      ⚠️ Imagen không trả về ảnh (Lần {attempt}).")
        #         raise Exception("Empty response")

        #     except Exception as e:
        #         print(f"      ❌ Lỗi Imagen (Lần {attempt}): {str(e)}")
        #         if attempt < max_retries: time.sleep(3)
        #         else: return None
        # return None

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
                    contents=f"Vẽ hình ảnh theo phong cách thật, tả thực, minh họa chính xác cho mô tả sau: {prompt}. Không vẽ theo phong cách hoạt hình hay tranh vẽ tay.",
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        candidate_count=1,
                        image_config=types.ImageConfig(aspect_ratio="1:1"),
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
                    print(f"      ⏳ Đợi 3 giây trước khi thử lại...")
                    time.sleep(3)
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