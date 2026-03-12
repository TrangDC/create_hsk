import os
import re
import time
import pandas as pd
from pathlib import Path
from typing import List
from openpyxl import load_workbook
from dotenv import load_dotenv
import shutil  # THÊM import này
from datetime import datetime
import sys
# Import các service
from services.image_gen_service import ImageGenerationService
from services.drive_service import upload_image_and_get_link, create_subfolder

# Cấu hình Folder Drive (Cho TOPIK)
DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "15nuXv7cUkWLnyUp3TpVOIQSg3qvBGjo8")

# Danh sách các sheet TOPIK cần xử lý theo logic mới
TOPIK_TARGET_SHEETS = [
    "Nối (img)", 
    "Trắc nghiệm chọn ảnh đúng (img)", 
    "Nhìn hình chọn đáp án (img)"
]

# Load biến môi trường
load_dotenv()

# ==========================================
# CÁC HÀM TIỆN ÍCH CHUNG (UTILS)
# ==========================================

def get_resource_path(relative_path):
    """
    Lấy đường dẫn tài nguyên, tương thích với PyInstaller
    Tìm thư mục resources từ thư mục dự án
    """
    # Nếu đã frozen bởi PyInstaller, dùng directory của executable
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        # Nếu không, tìm thư mục dự án bằng cách tìm resources folder
        current_dir = os.path.abspath(".")
        if os.path.exists(os.path.join(current_dir, "resources")):
            base_path = current_dir
        else:
            # Fallback: dùng thư mục của script hiện tại
            base_path = os.path.dirname(os.path.abspath(__file__))
            # Nếu vẫn không tìm thấy, lên một cấp
            parent = os.path.dirname(base_path)
            if os.path.exists(os.path.join(parent, "resources")):
                base_path = parent
            else:
                base_path = current_dir
    return os.path.join(base_path, relative_path)

def get_output_path(folder_name):
    """Lấy đường dẫn output ở thư mục làm việc hiện tại (không phải temp)"""
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(".")
    
    return Path(base_path) / folder_name

def clear_directory(directory_path: Path):
    """Xóa toàn bộ nội dung bên trong thư mục nhưng giữ lại thư mục"""
    if directory_path.exists() and directory_path.is_dir():
        try:
            file_count = 0
            for item in directory_path.iterdir():
                if item.is_file():
                    item.unlink()
                    file_count += 1
                elif item.is_dir():
                    shutil.rmtree(item)
                    file_count += 1
            
            if file_count > 0:
                print(f"🗑️  Đã xóa {file_count} file/folder trong '{directory_path.name}'")
            else:
                print(f"📂 Thư mục '{directory_path.name}' đã trống")
        except Exception as e:
            print(f"⚠️  Lỗi khi xóa nội dung thư mục: {e}")
    else:
        print(f"📁 Thư mục '{directory_path.name}' chưa tồn tại, sẽ tạo mới")

def extract_pdf_name_from_excel(excel_path: str) -> str:
    """
    Tách tên file PDF gốc từ tên file Excel.
    Quy tắc: TênExcel = TênPDF_level.xlsx
    Ví dụ: Bai1_topik1.xlsx -> Bai1
    """
    stem = Path(excel_path).stem # Ví dụ: Bai1_topik1
    
    # Tìm vị trí dấu gạch dưới cuối cùng
    last_underscore_index = stem.rfind('_')
    
    if last_underscore_index != -1:
        # Lấy phần trước dấu gạch dưới cuối cùng
        return stem[:last_underscore_index]
    else:
        # Nếu không có dấu gạch dưới, lấy nguyên tên
        return stem

def extract_image_prompts(cell_content: str) -> List[str]:
    """Trích xuất prompt từ dòng bắt đầu bằng 'Ảnh:'"""
    if not cell_content or not isinstance(cell_content, str):
        return []
    
    prompts = []
    lines = cell_content.split('\n')
    for line in lines:
        if "Ảnh:" in line or "Ảnh :" in line:
            keyword = "Ảnh:" if "Ảnh:" in line else "Ảnh :"
            # Lấy nội dung sau dấu :
            try:
                prompt = line.split(keyword, 1)[1].strip()
                if prompt: prompts.append(prompt)
            except IndexError:
                continue
    return prompts

# ==========================================
# LOGIC 1: XỬ LÝ TOPIK (MỚI)
# Logic: Vẽ -> Upload Drive -> Thay thế dòng 'Ảnh:' bằng Link
# ==========================================

def update_topik_cell_inplace(excel_path: str, sheet_name: str, row_number: int, col_number: int, original_text: str, image_links: List[str]):
    """Ghi đè ô Excel: Thay thế dòng 'Ảnh: ...' bằng Link Drive"""
    try:
        workbook = load_workbook(excel_path)
        sheet = workbook[sheet_name]
        
        lines = original_text.split('\n')
        new_lines = []
        link_idx = 0
        
        for line in lines:
            if ("Ảnh:" in line or "Ảnh :" in line) and link_idx < len(image_links):
                new_lines.append(image_links[link_idx])
                link_idx += 1
            else:
                new_lines.append(line)
        
        final_text = "\n".join(new_lines)
        sheet.cell(row=row_number, column=col_number, value=final_text)
        
        workbook.save(excel_path)
        workbook.close()
        return True
    except Exception as e:
        print(f"❌ [TOPIK] Lỗi update Excel: {e}")
        return False

def process_topik_sheet(sheet_name: str, excel_path: str, img_service: ImageGenerationService, 
                        output_dir: Path, parent_drive_id: str, pdf_name: str, sheet_number: int):
    """
    Xử lý sheet TOPIK với logic đặt tên file mới: {pdf_name}_S{sheet_number}_{question_num}{suffix}.png
    """
    print(f"🔵 [TOPIK] Đang xử lý sheet: {sheet_name}")
    
    if sheet_name in ["Nối (img)", "Trắc nghiệm chọn ảnh đúng (img)"]: col_idx = 7 
    elif sheet_name == "Nhìn hình chọn đáp án (img)": col_idx = 6 
    else: return

    try:
        # 1. Tạo thư mục con Local
        clean_sheet_name = re.sub(r'[<>:"/\\|?*]', '_', sheet_name)
        sheet_local_dir = output_dir / clean_sheet_name
        sheet_local_dir.mkdir(exist_ok=True)
        print(f"   📂 Local Folder: {sheet_local_dir}")

        # 2. Tạo thư mục con trên Drive
        print(f"   ☁️ Tạo Drive Folder cho Sheet: {clean_sheet_name}")
        sheet_drive_id = create_subfolder(clean_sheet_name, parent_drive_id)
        if not sheet_drive_id: sheet_drive_id = parent_drive_id

        wb = load_workbook(excel_path, read_only=True)
        sheet = wb[sheet_name]
        jobs = []
        for i, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            if col_idx - 1 < len(row):
                val = row[col_idx - 1]
                prompts = extract_image_prompts(val)
                if prompts:
                    jobs.append({"row": i, "val": val, "prompts": prompts})
        wb.close()

        for job in jobs:
            row_num = job['row']
            prompts = job['prompts']
            links = []
            
            # Tính số thứ tự câu (Hàng 2 là câu 1)
            question_num = row_num - 1
            total_imgs = len(prompts)
            
            print(f"   -> Câu {question_num} (Dòng {row_num}): Có {total_imgs} ảnh.")
            
            for idx, prompt in enumerate(prompts):
                # --- LOGIC ĐẶT TÊN MỚI ---
                # Xử lý hậu tố a, b, c, d nếu có nhiều ảnh
                if total_imgs > 1:
                    suffix = chr(97 + idx) # 97 là mã ASCII của 'a', 98 là 'b'...
                else:
                    suffix = ""
                
                # Làm sạch tên PDF
                clean_pdf_name = re.sub(r'[<>:"/\\|?*]', '_', pdf_name)
                
                # Format: Bai_10_1a.png
                filename = f"{clean_pdf_name}_S{sheet_number}_{question_num}{suffix}.png"
                local_path = sheet_local_dir / filename
                
                # Vẽ ảnh
                if not local_path.exists():
                    img_bytes = img_service.generate_image(prompt)
                    if img_bytes:
                        with open(local_path, "wb") as f: f.write(img_bytes)
                    else:
                        links.append("(Lỗi tạo ảnh)")
                        continue
                
                # Upload
                print(f"      Uploading: {filename}...")
                link = upload_image_and_get_link(str(local_path), sheet_drive_id)
                if link:
                    links.append(link)
                else:
                    links.append("(Lỗi upload)")
            
            if links:
                update_topik_cell_inplace(excel_path, sheet_name, row_num, col_idx, job['val'], links)
                
    except Exception as e:
        print(f"❌ [TOPIK] Lỗi xử lý sheet {sheet_name}: {e}")
        import traceback
        traceback.print_exc()

# ==========================================
# LOGIC 2: XỬ LÝ HSK (CŨ)
# Logic: Vẽ -> Lưu Local -> Ghi tên file vào cột K
# ==========================================

def update_hsk_col_k(excel_path: str, sheet_name: str, row_number: int, image_filenames: List[str]):
    """Ghi tên file ảnh vào cột K (Cột 11)"""
    try:
        workbook = load_workbook(excel_path)
        sheet = workbook[sheet_name]
        
        names_str = " - ".join([os.path.splitext(n)[0] for n in image_filenames])
        sheet.cell(row=row_number, column=11, value=names_str)
        
        workbook.save(excel_path)
        workbook.close()
        return True
    except Exception as e:
        print(f"❌ [HSK] Lỗi update Excel: {e}")
        return False

def process_hsk_sheet(sheet_name: str, excel_path: str, img_service: ImageGenerationService, output_dir: Path):
    """Xử lý giữ nguyên logic cũ cho các sheet HSK"""
    print(f"🟠 [HSK] Đang xử lý sheet: {sheet_name}")
    
    # Logic xác định cột cũ của bạn
    if sheet_name in ["ĐS (img) HSK1", "TN PA đúng (img) (HSK1)", "ĐS Ko phụ đề (img) HSK1","Đúng Sai (img) (HSK1)"]:
        col_idx = 6
    elif sheet_name in ["TN PA đúng (img) (HL) (HSK1)", "TN chọn ảnh (img) (HL) (HSK1)", "TN PA đúng (img) (HL) (HSK2)", "TN chọn ảnh (img) (HL) (HSK2)", "TN PA đúng (img) (HL) (HSK3)", "TN Đọc hiểu (img) (HSK5)"]:
        col_idx = 2
    elif sheet_name in ["Ảnh với từ (img) (HSK4)", "Viết dựa vào ảnh (img) (HSK5)"]:
        col_idx = 5
    else:
        col_idx = 6

    try:
        wb = load_workbook(excel_path, read_only=True)
        sheet = wb[sheet_name]
        
        jobs = []
        for i, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            if col_idx - 1 < len(row):
                val = row[col_idx - 1]
                prompts = extract_image_prompts(val)
                if prompts:
                    jobs.append({"row": i, "prompts": prompts})
        wb.close()

        for job in jobs:
            row_num = job['row']
            prompts = job['prompts']
            created_files = []
            
            print(f"   -> Dòng {row_num}: Có {len(prompts)} ảnh.")
            
            for idx, prompt in enumerate(prompts):
                # Naming convention cũ
                suffix = f"({idx+1})" if len(prompts) > 1 else ""
                filename = f"{sheet_name}_Row{row_num}_Col{col_idx}{suffix}.png"
                filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
                local_path = output_dir / filename
                
                # Vẽ ảnh và lưu local (Không upload Drive)
                if not local_path.exists():
                    img_bytes = img_service.generate_image_legacy(prompt)
                    if img_bytes:
                        with open(local_path, "wb") as f: f.write(img_bytes)
                        created_files.append(filename)
                        print(f"      ✅ Đã lưu: {filename}")
                    else:
                        print("      ❌ Lỗi tạo ảnh.")
                else:
                    created_files.append(filename)
                    print(f"      ⏭️ Đã có: {filename}")
            
            # Ghi vào cột K
            if created_files:
                update_hsk_col_k(excel_path, sheet_name, row_num, created_files)

    except Exception as e:
        print(f"❌ [HSK] Lỗi xử lý sheet {sheet_name}: {e}")

# ==========================================
# MAIN CONTROLLER
# ==========================================

def process_excel_file(excel_path: str) -> str | None:
    # Thư mục gốc chứa ảnh
    output_dir = get_output_path("IMG_CREATE_BY_AI")
    output_dir.mkdir(exist_ok=True)
    
    # Xóa ảnh cũ để tránh lẫn lộn
    clear_directory(output_dir)
    
    print("🚀 Khởi tạo dịch vụ vẽ ảnh...")
    img_service = ImageGenerationService()
    if not img_service.client: return None
    
    try:
        # Lấy tên PDF gốc để đặt tên file ảnh
        pdf_name = extract_pdf_name_from_excel(excel_path)
        print(f"📄 Tên PDF gốc trích xuất được: {pdf_name}")

        # Tạo subfolder trên Drive
        excel_filename = Path(excel_path).stem
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        drive_subfolder_name = f"{excel_filename}_{date_str}"
        
        print(f"📂 Tạo subfolder Drive: {drive_subfolder_name}")
        subfolder_id = create_subfolder(drive_subfolder_name, DRIVE_FOLDER_ID)
        if not subfolder_id: subfolder_id = DRIVE_FOLDER_ID # Fallback

        wb = load_workbook(excel_path, read_only=True)
        all_sheets = wb.sheetnames
        wb.close()
        
        topik_sheets = [s for s in all_sheets if s in TOPIK_TARGET_SHEETS]
        hsk_sheets = [s for s in all_sheets if "(img)" in s and s not in TOPIK_TARGET_SHEETS]
        
        if not topik_sheets and not hsk_sheets:
            print("⚠️ Không tìm thấy sheet nào cần xử lý.")
            return None
            
        # Xử lý TOPIK (Truyền thêm pdf_name)
        for sheet_idx, sheet in enumerate(topik_sheets, start=1):
            process_topik_sheet(sheet, excel_path, img_service, output_dir, subfolder_id, pdf_name, sheet_idx)
            
        # Xử lý HSK (Logic cũ)
        for sheet in hsk_sheets:
            process_hsk_sheet(sheet, excel_path, img_service, output_dir)
            
        return str(output_dir)

    except Exception as e:
        print(f"❌ Lỗi file Excel: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Test path
    EXCEL_PATH = r"C:\Users\EdmicroUser\Desktop\create_hsk\output\topik1_20251212_143042\topik1_output.xlsx"
    if os.path.exists(EXCEL_PATH):
        process_excel_file(EXCEL_PATH)