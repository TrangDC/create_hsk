import os
import time
import random
import pandas as pd

# Import services
from services.image_gen_service import ImageGenerationService

# --- CẤU HÌNH ---
# 1. Đường dẫn file Excel đầu vào (CẬP NHẬT ĐƯỜNG DẪN TẠI ĐÂY)
INPUT_EXCEL_PATH = r"D:\Edmicro\Tools\create_hsk\input\Bản sao của Flashcard A1-A2.xlsx" # Sửa lại thành file thật của bạn

# 2. Cấu hình Output
OUTPUT_BASE = "output/eng_flashcards"

# 3. Cấu hình Templates & Resources
TEMPLATE_IMG_DIR = "resources/images/image_eng_template"
COLOR_PALETTE = """
- Bảng màu: 
#FF6388
#FFB800
#5AB0FF
#43DF94
"""

PROMPT_TEMPLATE = """Make an image for the word/phrase "{word}" with this style and color code. Only gen image, no add text in image
{color_palette}"""

def setup_folders():
    """Tạo các thư mục cần thiết"""
    for d in [OUTPUT_BASE, TEMPLATE_IMG_DIR]:
        if not os.path.exists(d):
            os.makedirs(d)

def get_random_template_image():
    """Lấy ngẫu nhiên 1 file ảnh mẫu từ thư mục."""
    if not os.path.exists(TEMPLATE_IMG_DIR):
        return None
    valid_ext = ('.png', '.jpg', '.jpeg', '.webp')
    images = [f for f in os.listdir(TEMPLATE_IMG_DIR) if f.lower().endswith(valid_ext)]
    if not images:
        return None
    return os.path.join(TEMPLATE_IMG_DIR, random.choice(images))

def main():
    print("🚀 BẮT ĐẦU CHƯƠNG TRÌNH TẠO ẢNH FLASHCARD TIẾNG ANH...")
    setup_folders()
    
    # 1. Kiểm tra File Đầu Vào
    if not os.path.exists(INPUT_EXCEL_PATH):
        print(f"❌ Không tìm thấy file Excel tại: {INPUT_EXCEL_PATH}")
        return

    # 2. Khởi tạo Service
    try:
        img_service = ImageGenerationService()
        print("✅ Init Image Generation Service thành công.")
    except Exception as e:
        print(f"❌ Init Service failed: {e}")
        return

    # 3. Đọc dữ liệu từ file Excel
    try:
        # Đọc tất cả các sheet
        xls = pd.ExcelFile(INPUT_EXCEL_PATH)
        sheet_names = [sheet for sheet in xls.sheet_names if sheet.strip().lower() != "yêu cầu"]
        print(f"📄 Tìm thấy các sheet cần xử lý: {sheet_names}")
    except Exception as e:
        print(f"❌ Lỗi khi đọc file Excel: {e}")
        return

    # CHỌN SHEET ĐỂ CHẠY Ở ĐÂY (Có thể cấu hình thành tham số đầu vào)
    # Ví dụ: sheets_to_run = ["Sheet1", "Sheet2"]
    # Mặc định lấy tất cả:
    sheets_to_run = sheet_names

    total_generated = 0

    for sheet in sheets_to_run:
        print(f"\n======== ĐANG XỬ LÝ SHEET: {sheet} ========")
        
        # Tạo thư mục con dựa theo tên sheet
        sheet_safe_name = "".join([c for c in sheet if c.isalnum() or c in (' ', '-', '_')]).strip()
        sheet_out_dir = os.path.join(OUTPUT_BASE, sheet_safe_name)
        os.makedirs(sheet_out_dir, exist_ok=True)

        try:
            df = pd.read_excel(xls, sheet_name=sheet)
        except Exception as e:
            print(f"⚠️ Lỗi đọc sheet '{sheet}': {e}")
            continue
        
        # Kiểm tra xem cột 'Từ' có tồn tại không
        if 'Từ' not in df.columns:
            print(f"⚠️ Sheet '{sheet}' không có cột 'Từ'. Bỏ qua sheet này.")
            continue
            
        # Lọc ra các dòng có chứa 'Từ' (không bị rỗng/NaN)
        words = df['Từ'].dropna().astype(str).tolist()
        
        print(f"📋 Tìm thấy {len(words)} từ vựng trong sheet '{sheet}'.")

        for idx, word in enumerate(words):
            word = word.strip()
            if not word:
                continue

            print(f"  [{idx + 1}/{len(words)}] Xử lý từ: '{word}'")
            
            # Khởi tạo prompt
            image_prompt = PROMPT_TEMPLATE.format(
                word=word, 
                color_palette=COLOR_PALETTE
            )

            # Đặt tên file ảnh
            # Xóa các ký tự đặc biệt khỏi tên file
            safe_word = "".join([c for c in word if c.isalnum() or c in (' ', '-', '_')]).strip()
            final_img_path = os.path.join(sheet_out_dir, f"{safe_word}.png")

            # Bỏ qua nếu đã tồn tại
            if os.path.exists(final_img_path):
                print(f"      ⏭️ Ảnh '{safe_word}.png' đã tồn tại, bỏ qua.")
                continue

            # Chọn ảnh template ngẫu nhiên
            template_img_path = get_random_template_image()
            if not template_img_path:
                print("      ⚠️ Không tìm thấy ảnh template nào trong resources/images/image_eng_template. Hãy thêm ảnh mẫu vào.")
            
            # Gọi AI vẽ ảnh
            try:
                img_bytes = img_service.generate_image_with_image_ref(
                    prompt=image_prompt,
                    image_path=template_img_path,
                    aspect_ratio="3:2" # Hình chữ nhật nằm ngang theo tỉ lệ 480x240
                )
                
                if img_bytes:
                    with open(final_img_path, "wb") as f:
                        f.write(img_bytes)
                    print(f"      ✅ Đã lưu ảnh: {safe_word}.png")
                    total_generated += 1
                else:
                    print(f"      ❌ Không sinh được ảnh cho từ '{word}'")
                    
            except Exception as e:
                print(f"      ❌ Lỗi khi gọi AI vẽ ảnh: {e}")
                
            # Nghỉ ngơi giữa các lượt request để tránh rate limit
            time.sleep(3)

    print(f"\n🎉 HOÀN TẤT! Đã tạo thành công {total_generated} ảnh.")
    print(f"📁 Xem ảnh tại: {os.path.abspath(OUTPUT_BASE)}")

if __name__ == "__main__":
    main()
