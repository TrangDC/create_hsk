# processor.py
import os
from datetime import datetime
import json
import traceback
from question_generator import run_question_generation
from explanation_generator import run_explanation_generation

def run_full_pipeline(pdf_folder_path: str, level: str, preproc_mode: int = 0) -> str | None:
    """
    Hàm tổng điều phối toàn bộ quy trình tạo câu hỏi và lời giải.

    Args:
        pdf_folder_path (str): Đường dẫn đến thư mục chứa các file PDF đầu vào.
        hsk_level (str): Cấp độ HSK cần tạo (ví dụ: "hsk1", "hsk2",...).
        preproc_mode (int): Chế độ phân tích PDF (0: mặc định, 1: chỉ từ vựng & bài khóa, 2: chỉ từ vựng & ngữ pháp).

    Returns:
        str | None: Đường dẫn đến thư mục chứa kết quả nếu thành công, ngược lại trả về None.
    """
    # --- 1. CHUẨN BỊ MÔI TRƯỜNG ---
    output_dir = "output"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_files = [os.path.join(pdf_folder_path, f) for f in os.listdir(pdf_folder_path) if f.lower().endswith('.pdf')]
    if not pdf_files:
            print(f"❌ Lỗi: Không tìm thấy file PDF nào trong '{pdf_folder_path}'.")
            return None, None
    if level in ["topik1", "topik2", "topik3"]:
        # Ưu tiên tìm file có chữ "Bài"
        candidate_files = [f for f in pdf_files if "Bài" in os.path.basename(f)]
        if candidate_files:
            chosen_pdf = candidate_files[0]
        else:
            # Nếu không có file nào chứa chữ "Bài", lấy file đầu tiên bất kỳ
            chosen_pdf = pdf_files[0]
    else:
        chosen_pdf = pdf_files[0]        
    # Lấy tên file gốc bỏ đuôi .pdf
    base_name = os.path.splitext(os.path.basename(chosen_pdf))[0]
    output_folder_with_timestamp = os.path.join(output_dir, "excel", f"{base_name}_{level}_{timestamp}")
    os.makedirs(output_folder_with_timestamp, exist_ok=True)
    
    print("="*60)
    print("BẮT ĐẦU TẠO ĐỀ")
    print(f"Cấp độ HSK/TOPIK: {level.upper()}")
    print(f"Thư mục PDF: {os.path.abspath(pdf_folder_path)}")
    print(f"Thư mục Output: {os.path.abspath(output_folder_with_timestamp)}")
    print("="*60)

    # --- 2. CHẠY CÁC QUY TRÌNH TUẦN TỰ ---
    try:
        # ---- QUY TRÌNH 1: TẠO CÂU HỎI ----
        intermediate_file, output_excel = run_question_generation(
            level=level,
            pdf_folder_path=pdf_folder_path,
            output_folder_path=output_folder_with_timestamp,
            preproc_mode=preproc_mode  # <--- THÊM MỚI
        )
        # Kiểm tra nếu bước 1 thành công thì mới chạy bước 2
        if intermediate_file and output_excel:
            # ---- QUY TRÌNH 2: TẠO LỜI GIẢI ----
            run_explanation_generation(
                hsk_level=level,
                source_data_file=intermediate_file,
                excel_output_path=output_excel
            )
            print("\n🎉🎉🎉 PIPELINE HOÀN TẤT THÀNH CÔNG! 🎉🎉🎉")
            print(f"Kết quả đã được lưu tại: {os.path.abspath(output_folder_with_timestamp)}")
            return output_folder_with_timestamp
        else:
            print("\n❌ Pipeline đã dừng do lỗi trong quá trình tạo câu hỏi.")
            return None

    except Exception as e:
        print(f"\n❌ ĐÃ XẢY RA LỖI NGHIÊM TRỌNG TRONG PIPELINE: {e}")
        traceback.print_exc()
        return None

# --- KHỐI ĐỂ KIỂM THỬ TRỰC TIẾP SCRIPT NÀY ---
# Code trong khối này chỉ chạy khi bạn thực thi: python run_pipeline.py
if __name__ == "__main__":
    
    # --- Cấu hình cho việc kiểm thử ---
    PDF_INPUT_DIR = "input"
    HSK_LEVEL_TO_RUN = "hsk1"

    print("--- Chạy ở chế độ kiểm thử 'run_pipeline.py' ---")
    
    # Gọi hàm chính
    final_output_path = run_full_pipeline(
        pdf_folder_path=PDF_INPUT_DIR, 
        hsk_level=HSK_LEVEL_TO_RUN
    )

    # Kiểm tra kết quả trả về
    if final_output_path:
        print(f"\nKiểm thử thành công. Xem kết quả tại: {final_output_path}")
    else:
        print("\nKiểm thử thất bại. Vui lòng kiểm tra lại log lỗi ở trên.")