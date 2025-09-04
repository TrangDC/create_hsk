import os
import re
import time
import pandas as pd
from pathlib import Path
from typing import List, Tuple
from openpyxl import load_workbook
from google.oauth2 import service_account
from google.cloud import aiplatform
import vertexai
from vertexai.preview.vision_models import ImageGenerationModel
from dotenv import load_dotenv

def get_vertex_ai_credentials():
    """Lấy đối tượng credentials cho Vertex AI từ .env."""
    try:
        service_account_data = {
            "type": os.getenv("TYPE"),
            "project_id": os.getenv("PROJECT_ID"),
            "private_key_id": os.getenv("PRIVATE_KEY_ID"),
            "private_key": os.getenv("PRIVATE_KEY").replace('\\n', '\n'),
            "client_email": os.getenv("CLIENT_EMAIL"),
            "client_id": os.getenv("CLIENT_ID", ""),
            "auth_uri": os.getenv("AUTH_URI"),
            "token_uri": os.getenv("TOKEN_URI"),
            "auth_provider_x509_cert_url": os.getenv("AUTH_PROVIDER_X509_CERT_URL"),
            "client_x509_cert_url": os.getenv("CLIENT_X509_CERT_URL"),
            "universe_domain": os.getenv("UNIVERSE_DOMAIN")
        }
        credentials = service_account.Credentials.from_service_account_info(
            service_account_data,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return credentials
    except Exception as e:
        print(f"Lỗi khi tạo credentials từ service account: {e}")
        return None

def initialize_imagen_model():
    """Khởi tạo model Imagen với credentials - PHIÊN BẢN ĐÃ SỬA."""
    try:
        credentials = get_vertex_ai_credentials()
        if not credentials:
            return None
        
        project_id = os.getenv("PROJECT_ID")
        location = os.getenv("LOCATION", "us-central1")
        
        # Khởi tạo Vertex AI với cách tiếp cận đúng
        vertexai.init(
            project=project_id,
            location=location,
            credentials=credentials
        )
        
        # Khởi tạo model Imagen
        model = ImageGenerationModel.from_pretrained("imagen-4.0-ultra-generate-001")
        return model
    except Exception as e:
        print(f"Lỗi khi khởi tạo model Imagen: {e}")
        return None

def extract_image_prompts(cell_content: str) -> List[str]:
    """
    Trích xuất các prompt ảnh từ nội dung cell.
    Tìm các chuỗi sau "Ảnh:" cho đến khi gặp xuống dòng.
    """
    if pd.isna(cell_content) or not isinstance(cell_content, str):
        return []
    
    prompts = []
    lines = cell_content.split('\n')
    
    for i, line in enumerate(lines):
        if "Ảnh:" in line or "Ảnh :" in line:
            # Lấy nội dung sau "Ảnh:" hoặc "Ảnh :"
            keyword = "Ảnh:" if "Ảnh:" in line else "Ảnh :"
            start_idx = line.index(keyword) + len(keyword)
            prompt = line[start_idx:].strip()
            
            # Nếu prompt trống, kiểm tra dòng tiếp theo
            if not prompt and i + 1 < len(lines):
                prompt = lines[i + 1].strip()
            
            if prompt:
                prompts.append(prompt)
                
        # if "Ảnh:" in line or "Ảnh :" in line:
        #     # Lấy nội dung sau "Ảnh:"
        #     start_idx = line.index("Ảnh:") + 4
        #     prompt = line[start_idx:].strip()
            
        #     # Nếu prompt trống, kiểm tra dòng tiếp theo
        #     if not prompt and i + 1 < len(lines):
        #         prompt = lines[i + 1].strip()
            
        #     if prompt:
        #         prompts.append(prompt)
    
    return prompts

def generate_image_with_imagen(model, prompt: str, output_path: str):
    """
    Gọi API Imagen để tạo ảnh từ prompt - PHIÊN BẢN ĐÃ SỬA.
    """
    try:
        print(f"Đang tạo ảnh với prompt: {prompt[:50]}...")
        
        # Tạo ảnh với model Imagen - CẬP NHẬT THAM SỐ
        response = model.generate_images(
            prompt=prompt,
            number_of_images=4,
            aspect_ratio="1:1",
            negative_prompt="",
            person_generation="allow_all",
            safety_filter_level="block_few",
            add_watermark=False,
        )
        
        # Lưu ảnh
        if response.images and len(response.images) > 0:
            # Lưu ảnh đầu tiên
            image = response.images[0]
            image.save(output_path)
            print(f"✅ Đã lưu ảnh: {output_path}")
            return True
        else:
            print(f"❌ Không thể tạo ảnh cho prompt: {prompt[:50]}...")
            return False
            
    except Exception as e:
        print(f"❌ Lỗi khi tạo ảnh: {e}")
        print(f"Chi tiết lỗi: {type(e).__name__}: {str(e)}")
        return False

def update_excel_with_image_names(excel_path: str, sheet_name: str, row_number: int, image_filenames: List[str]):
    """
    Cập nhật tên ảnh vào cột K của file Excel.
    Nếu có nhiều ảnh thì nối bằng dấu ' - '.
    """
    try:
        # Load workbook với chế độ có thể chỉnh sửa
        workbook = load_workbook(excel_path)
        sheet = workbook[sheet_name]
        
        # Tạo chuỗi tên ảnh, nối bằng ' - ' nếu có nhiều ảnh
        image_names_only = [os.path.splitext(name)[0] for name in image_filenames]
        image_names_str = " - ".join(image_names_only)

        # Ghi vào cột K (cột 11)
        sheet.cell(row=row_number, column=11, value=image_names_str)
        
        # Lưu file
        workbook.save(excel_path)
        workbook.close()
        
        print(f"📝 Đã cập nhật cột K dòng {row_number}: {image_names_str}")
        return True
        
    except Exception as e:
        print(f"❌ Lỗi khi cập nhật Excel: {e}")
        return False

def process_sheet_case(sheet_name: str, excel_path: str, model, output_dir: Path):
    """
    Xử lý sheet theo các case khác nhau, sử dụng openpyxl để truy cập cột F (6) hoặc B (2).
    Đồng thời cập nhật tên ảnh vào cột K.
    """
    # Xác định chỉ số cột dựa trên sheet_name
    if sheet_name in ["ĐS (img) HSK1", "TN PA đúng (img) (HSK1)", "ĐS Ko phụ đề (img) HSK1","Đúng Sai (img) (HSK1)"]:
        column_to_process = 6  # Cột F
    elif sheet_name in ["TN PA đúng (img) (HL) (HSK1)", 
                        "TN chọn ảnh (img) (HL) (HSK1)",
                        "TN PA đúng (img) (HL) (HSK2)",
                        "TN chọn ảnh (img) (HL) (HSK2)",
                        "TN PA đúng (img) (HL) (HSK3)",
                        "TN Đọc hiểu (img) (HSK5)"]:
        column_to_process = 2  # Cột B
    elif sheet_name in ["Ảnh với từ (img) (HSK4)",
                        "Viết dựa vào ảnh (img) (HSK5)"]:
        column_to_process = 5  # Cột E
    else:
        column_to_process = 6  # Mặc định cột F cho các sheet có (img) khác
    
    print(f"📋 Xử lý sheet: {sheet_name} - Cột: {column_to_process}")
    
    try:
        # Load workbook và sheet bằng openpyxl (chỉ để đọc)
        workbook = load_workbook(excel_path, data_only=True)
        sheet = workbook[sheet_name]
        
        # Xử lý từng dòng trong cột được chọn, bắt đầu từ dòng 2
        row_idx = 2
        processed_count = 0
        
        while True:
            # Lấy giá trị ô tại cột chỉ định
            cell_value = sheet.cell(row=row_idx, column=column_to_process).value
            
            # Kiểm tra nếu ô trống thì thoát vòng lặp
            if cell_value is None:
                break
                
            prompts = extract_image_prompts(str(cell_value))
            
            if prompts:
                created_image_filenames = []  # Danh sách tên file ảnh đã tạo cho dòng này
                
                for prompt_idx, prompt in enumerate(prompts, start=1):
                    # Tạo tên file
                    if len(prompts) > 1:
                        filename = f"{sheet_name}_Row{row_idx}_Col{column_to_process}({prompt_idx}).png"
                    else:
                        filename = f"{sheet_name}_Row{row_idx}_Col{column_to_process}.png"
                    
                    # Loại bỏ ký tự không hợp lệ trong tên file
                    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
                    output_path = output_dir / filename
                    
                    # Kiểm tra nếu file đã tồn tại
                    if output_path.exists():
                        print(f"⏭️ File đã tồn tại, bỏ qua: {filename}")
                        created_image_filenames.append(filename)  # Vẫn thêm vào danh sách
                        continue
                    
                    # Gọi API tạo ảnh với retry logic
                    max_retries = 3
                    success = False
                    for attempt in range(1, max_retries + 1):
                        success = generate_image_with_imagen(model, prompt, str(output_path))
                        if success:
                            processed_count += 1
                            created_image_filenames.append(filename)
                            break
                        else:
                            if attempt < max_retries:
                                print(f"🔄 Thử lại lần {attempt}/{max_retries} sau 5 giây...")
                                time.sleep(5)
                            else:
                                print(f"❌ Không thể tạo ảnh sau {max_retries} lần thử.")
                    
                    # Thêm delay giữa các request để tránh rate limit
                    time.sleep(1)
                
                # Cập nhật tên ảnh vào cột K nếu có ảnh được tạo
                if created_image_filenames:
                    update_excel_with_image_names(excel_path, sheet_name, row_idx, created_image_filenames)
            
            row_idx += 1
        
        workbook.close()
        print(f"✅ Hoàn thành sheet {sheet_name}: Đã tạo {processed_count} ảnh")
    
    except Exception as e:
        print(f"❌ Lỗi khi xử lý sheet {sheet_name}: {e}")


def process_excel_file(excel_path: str) -> str | None:
    """
    Hàm chính xử lý file Excel, tạo ảnh và trả về đường dẫn thư mục output.
    """
    # Load environment variables
    load_dotenv()
    
    output_dir = Path("IMG_CREATE_BY_AI")
    output_dir.mkdir(exist_ok=True)
    
    print("🚀 Đang khởi tạo model Imagen...")
    model = initialize_imagen_model()
    if not model:
        print("❌ Không thể khởi tạo model Imagen. Vui lòng kiểm tra credentials và project setup.")
        return None
    
    try:
        print(f"📁 Đang đọc file Excel: {excel_path}")
        # Sử dụng openpyxl để lấy tên sheet
        wb = load_workbook(excel_path, read_only=True)
        sheet_names = wb.sheetnames
        wb.close()
        
        sheets_with_img = [name for name in sheet_names if "(img)" in name]
        print(f"📊 Tìm thấy {len(sheets_with_img)} sheet có '(img)' trong tên:")
        for sheet_name in sheets_with_img:
            print(f"  - {sheet_name}")
        
        if not sheets_with_img:
            print("⚠️ Không tìm thấy sheet nào có '(img)' trong tên!")
            return None
        
        total_processed = 0
        for i, sheet_name in enumerate(sheets_with_img, 1):
            print(f"\n📋 [{i}/{len(sheets_with_img)}] Đang xử lý sheet: {sheet_name}")
            process_sheet_case(sheet_name, excel_path, model, output_dir)
        
        print(f"\n🎉 Hoàn thành! Các ảnh đã được lưu trong thư mục: {output_dir}")
        print(f"📝 Tên các ảnh đã được cập nhật vào cột K của file Excel gốc")
        return str(output_dir)
        
    except FileNotFoundError:
        print(f"❌ Không tìm thấy file: {excel_path}")
        return None
    except Exception as e:
        print(f"❌ Lỗi khi xử lý file Excel: {e}")
        return None

def main():
    """
    Hàm main để chạy chương trình.
    """
    excel_path = r"C:\Users\EdmicroUser\Desktop\create_hsk\output\hsk1_20250822_113823\hsk1_output.xlsx"
    
    if not os.path.exists(excel_path):
        print(f"❌ File không tồn tại: {excel_path}")
        return
    
    result = process_excel_file(excel_path)
    if result:
        print(f"🎯 Thành công! Ảnh được lưu tại: {result}")
    else:
        print("❌ Quá trình xử lý thất bại!")

if __name__ == "__main__":
    main()