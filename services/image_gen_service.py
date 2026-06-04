# services/image_gen_service.py
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
        self.model_name = "gemini-3.1-flash-image-preview"
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

    def generate_image(self, prompt, aspect_ratio="1:1", max_retries=5, retry_delay=3,):
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

    def generate_image_pdfs(self, prompt, pdf_path=None, aspect_ratio="1:1", max_retries=5, retry_delay=3):
        """
        Tạo ảnh với tham chiếu từ file PDF Mascot và ép quy tắc nền trắng.
        """
        if not self.client:
            return None

        # --- ÉP QUY TẮC NỀN TRẮNG (STRICT WHITE BACKGROUND) ---
        # Chúng ta thêm hậu tố này vào cuối mọi prompt để Imagen xử lý chính xác
        style_suffix = (
            "Isolated on a pure white background, no background scenery, "
            "no floor, no horizon, flat 2D vector illustration, high resolution."
        )
        final_prompt = f"{prompt}. {style_suffix}"

        # --- CHUẨN BỊ NỘI DUNG (MULTIMODAL) ---
        request_contents = []
        
        # 1. Nếu có file PDF Mascot (Dành cho use_mascot=True)
        if pdf_path and os.path.exists(pdf_path):
            try:
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                
                request_contents.append(
                    types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
                )
                # Chỉ dẫn bổ sung khi có PDF tham khảo
                final_prompt = (
                    f"Follow the character design from the attached PDF. "
                    f"Action: {final_prompt}"
                )
            except Exception as e:
                print(f"⚠️ Không thể đọc file PDF Mascot: {e}")

        # 2. Đưa Prompt văn bản cuối cùng vào
        request_contents.append(types.Part.from_text(text=final_prompt))

        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    print(f"   🔄 Thử lại lần {attempt}/{max_retries}...")
                
                # Gọi Model Image Generation (Imagen)
                response = self.client.models.generate_content(
                    model=self.model_name,
    
                    contents=request_contents,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        candidate_count=1,
                        image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
                    )
                )

                if response.parts:
                    for part in response.parts:
                        if part.inline_data and part.inline_data.data:
                            return part.inline_data.data

                raise Exception("Empty image data from API")

            except Exception as e:
                print(f"      ❌ Lỗi sinh ảnh (Lần {attempt}): {str(e)}")
                if attempt < max_retries:
                    time.sleep(retry_delay)
                else:
                    return None
        return None

    def generate_image_with_image_ref(self, prompt, image_path=None, aspect_ratio="1:1", max_retries=5, retry_delay=3):
        """
        Tạo ảnh với tham chiếu từ file ảnh mẫu.
        Returns: tuple (image_bytes, usage_dict) hoặc (None, usage_dict) nếu thất bại.
        usage_dict = {
            "prompt_tokens": int,
            "output_tokens": int,
            "total_tokens": int,
            "attempts": int,   # số lần thử thực tế
        }
        """
        usage = {"prompt_tokens": 0, "output_tokens": 0, "total_tokens": 0, "attempts": 0}

        if not self.client:
            return None, usage

        request_contents = []
        
        # Nếu có file ảnh mẫu
        if image_path and os.path.exists(image_path):
            try:
                # Lấy đúng mime type
                ext = os.path.splitext(image_path)[1].lower()
                mime_type = "image/png" if ext == ".png" else "image/jpeg"
                
                with open(image_path, "rb") as f:
                    image_bytes = f.read()
                
                request_contents.append(
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                )
                
                final_prompt = (
                    f"Follow the visual style and aesthetic of the attached reference image. "
                    f"Action: {prompt}"
                )
            except Exception as e:
                print(f"⚠️ Không thể đọc file ảnh mẫu: {e}")
                final_prompt = prompt
        else:
            final_prompt = prompt

        request_contents.append(types.Part.from_text(text=final_prompt))

        for attempt in range(1, max_retries + 1):
            usage["attempts"] = attempt
            try:
                if attempt > 1:
                    print(f"   🔄 Thử lại lần {attempt}/{max_retries}...")
                
                # Gọi Model Image Generation
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=request_contents,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        candidate_count=1,
                        image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
                    )
                )

                # Lấy usage metadata nếu có
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    meta = response.usage_metadata
                    usage["prompt_tokens"]  = getattr(meta, 'prompt_token_count', 0) or 0
                    usage["output_tokens"]  = getattr(meta, 'candidates_token_count', 0) or 0
                    usage["total_tokens"]   = getattr(meta, 'total_token_count', 0) or 0

                if response.parts:
                    for part in response.parts:
                        if part.inline_data and part.inline_data.data:
                            return part.inline_data.data, usage

                raise Exception("Empty image data from API")

            except Exception as e:
                print(f"      ❌ Lỗi sinh ảnh (Lần {attempt}): {str(e)}")
                if attempt < max_retries:
                    time.sleep(retry_delay)
                else:
                    return None, usage
        return None, usage

# --- KHỐI TEST ---
if __name__ == "__main__":
    service = ImageGenerationService()
    test_prompt = "Một con mèo đang ngủ."
    img = service.generate_image_with_image_ref(test_prompt, None, aspect_ratio="1:1")
    if img: print("Thành công")