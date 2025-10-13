# question_generator.py
import os
import openpyxl
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional
from openpyxl.styles import Alignment
import json
# Sửa đổi import
from call_vertexai import generate_content, extract_structured_data_from_pdf
import shutil
from config.hsk_question_configs import get_prompt_config

def format_structured_data_for_prompt(structured_data: Dict[str, Any]) -> str:
    """
    Định dạng dữ liệu có cấu trúc (bao gồm tóm tắt tình huống) thành một chuỗi văn bản
    sạch sẽ để làm ngữ cảnh cho AI tạo câu hỏi.
    """
    content_parts = []
    
    content_parts.append("Dưới đây là nội dung học thuật từ tài liệu đã được phân tích. Dựa vào đây để tạo câu hỏi:\n")
    
    if structured_data.get("vocabulary"):
        content_parts.append("--- PHẦN TỪ VỰNG ---\n")
        for item in structured_data["vocabulary"]:
            content_parts.append(f"- Từ vựng: {item.get('word', '')}")
            content_parts.append(f"  Phiên âm: {item.get('pinyin', '')}")
            content_parts.append(f"  Nghĩa: {item.get('meaning', '')}")
        content_parts.append("\n")

    if structured_data.get("grammar_points"):
        content_parts.append("--- PHẦN NGỮ PHÁP ---\n")
        for item in structured_data["grammar_points"]:
            content_parts.append(f"- Cấu trúc: {item.get('structure', '')}")
            content_parts.append(f"  Cách dùng: {item.get('usage', '')}\n")
        content_parts.append("\n")
    
    if structured_data.get("situational_contexts"):
        content_parts.append("--- PHẦN NGỮ CẢNH TÌNH HUỐNG (Tóm tắt) ---\n")
        for i, context in enumerate(structured_data["situational_contexts"], 1):
            topic = context.get('topic', 'Không rõ chủ đề')
            participants = ", ".join(context.get('participants', []))
            summary = context.get('summary', '')
            
            content_parts.append(f"Tình huống {i}: {topic}")
            content_parts.append(f"Nhân vật: {participants}")
            content_parts.append(f"Tóm tắt: {summary}\n")
        content_parts.append("\n")
        
    return "\n".join(content_parts)

# --- HÀM ĐIỀU PHỐI CHÍNH CỦA MODULE ---
def run_question_generation(hsk_level: str, pdf_folder_path: str, output_folder_path: str):
    """
    Thực hiện toàn bộ quy trình tạo câu hỏi.
    Returns:
        tuple[str, str] | tuple[None, None]: Đường dẫn đến file data trung gian và file excel output, hoặc None nếu thất bại.
    """
    print("==========================================================")
    print(" BẮT ĐẦU QUY TRÌNH TẠO CÂU HỎI ".center(58, "="))
    print("==========================================================")

    # 1. Lấy cấu hình động dựa trên hsk_level
    PROMPT_CONFIGS = get_prompt_config(hsk_level)
    if not PROMPT_CONFIGS:
        print(f"❌ Lỗi: Không thể tiếp tục vì không có cấu hình cho '{hsk_level}'.")
        return None, None
    
    # --- 1. XÁC ĐỊNH CÁC ĐƯỜNG DẪN ĐỘNG ---
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
    RESOURCES_DIR = os.path.join(ROOT_DIR, "resources")
    
    PROMPTS_FOLDER = os.path.join(RESOURCES_DIR, "prompts", "create", hsk_level)
    SCHEMAS_FOLDER = os.path.join(RESOURCES_DIR, "schema", "create", hsk_level)
    # (MỚI) Đường dẫn cho prompt và schema tiền xử lý
    PREPROCESSING_PROMPT_PATH = os.path.join(RESOURCES_DIR, "prompts", "preprocessing", "extract_lesson_structure.txt")
    PREPROCESSING_SCHEMA_PATH = os.path.join(RESOURCES_DIR, "schema", "preprocessing", "extract_lesson_structure.json")
    EXCEL_TEMPLATE_PATH = os.path.join(RESOURCES_DIR, "sheet", f"{hsk_level}.xlsx")
    
    OUTPUT_EXCEL_PATH = os.path.join(output_folder_path, f"{hsk_level}_output.xlsx")
    INTERMEDIATE_DATA_FILE = os.path.join(output_folder_path, "generated_question_data.json")

    # --- 2. CHUẨN BỊ MÔI TRƯỜNG ---
    # Quét file PDF
    try:
        pdf_files = [os.path.join(pdf_folder_path, f) for f in os.listdir(pdf_folder_path) if f.lower().endswith('.pdf')]
        if not pdf_files:
            print(f"❌ Lỗi: Không tìm thấy file PDF nào trong '{pdf_folder_path}'.")
            return None, None
        print(f"✅ Tìm thấy {len(pdf_files)} file PDF.")
    except FileNotFoundError:
        print(f"❌ Lỗi: Thư mục PDF '{pdf_folder_path}' không tồn tại.")
        return None, None
    
    # --- (LOGIC MỚI) BƯỚC TIỀN XỬ LÝ ĐỘNG ---
    preprocessed_text_content: Optional[str] = None
    # Điều kiện: chỉ có 1 file và tên chứa "bài khóa" (không phân biệt hoa thường)
    if len(pdf_files) == 1 or "bài khóa" in os.path.basename(pdf_files[0]).lower():
        print("\n--- Phát hiện file 'bài khóa' duy nhất. Bắt đầu quy trình tiền xử lý. ---")
        try:
            structured_data = extract_structured_data_from_pdf(
                pdf_path=pdf_files[0],
                prompt_file_path=PREPROCESSING_PROMPT_PATH,
                schema_file_path=PREPROCESSING_SCHEMA_PATH
            )
            preprocessed_text_content = format_structured_data_for_prompt(structured_data)
            print("--- ✅ Tiền xử lý thành công. Sử dụng dữ liệu đã bóc tách để tạo câu hỏi. ---")
            # Lưu lại file text đã bóc tách để debug
            with open(os.path.join(output_folder_path, "preprocessed_content.txt"), 'w', encoding='utf-8') as f:
                f.write(preprocessed_text_content)

        except Exception as e:
            print(f"❌ Lỗi trong quá trình tiền xử lý: {e}.")
            print("--- ⚠️ Sẽ tiếp tục tạo câu hỏi bằng file PDF gốc. Kết quả có thể không chính xác. ---")
            preprocessed_text_content = None # Đảm bảo quay về trạng thái null nếu lỗi

    # Tạo bản sao file Excel
    try:
        shutil.copy2(EXCEL_TEMPLATE_PATH, OUTPUT_EXCEL_PATH)
        print(f"✅ Đã tạo file Excel output tại: '{OUTPUT_EXCEL_PATH}'")
    except FileNotFoundError:
        print(f"❌ Lỗi: Không tìm thấy file Excel mẫu tại '{EXCEL_TEMPLATE_PATH}'.")
        return None, None

    print("\n--- Bắt đầu gọi Vertex AI API để tạo câu hỏi ---")
    generated_data_map = {}
    with ThreadPoolExecutor(max_workers=len(PROMPT_CONFIGS)/2) as executor:
        future_to_prompt = {}
        for p_name in PROMPT_CONFIGS.keys():
            api_kwargs = {
                'prompt_file_path': os.path.join(PROMPTS_FOLDER, f"{p_name}.txt"),
                'schema_file_path': os.path.join(SCHEMAS_FOLDER, f"{p_name}.json")
            }
            # (LOGIC MỚI) Quyết định nguồn dữ liệu đầu vào
            if preprocessed_text_content:
                api_kwargs['text_content'] = preprocessed_text_content
            else:
                api_kwargs['pdf_file_paths'] = pdf_files

            future = executor.submit(generate_content, **api_kwargs)
            future_to_prompt[future] = p_name
        for future in as_completed(future_to_prompt):
            prompt_name = future_to_prompt[future]
            try:
                data = future.result()
                generated_data_map[prompt_name] = data
                print(f"✅ Nhận dữ liệu thành công từ prompt: {prompt_name}")
            except Exception as exc:
                print(f"❌ Lỗi khi xử lý prompt {prompt_name}: {exc}")
    
    if not generated_data_map:
        print("\nKhông nhận được dữ liệu nào từ API. Dừng chương trình.")
        return
    print("--- ✅ Hoàn tất gọi API ---\n")
    
    with open(INTERMEDIATE_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(generated_data_map, f, ensure_ascii=False, indent=2)
    print(f"✅ Đã lưu dữ liệu câu hỏi trung gian vào '{INTERMEDIATE_DATA_FILE}'")

    try:
        workbook = openpyxl.load_workbook(OUTPUT_EXCEL_PATH)
        
        for prompt_name, data in generated_data_map.items():
            config = PROMPT_CONFIGS.get(prompt_name)
            if not config:
                continue

            print(f"\nBắt đầu xử lý dữ liệu từ prompt '{prompt_name}':")
            
            # Phân nhánh logic dựa trên loại cấu trúc JSON
            if config["type"] == "keyed":
                for json_key, sheet_name, processing_func in config["processors"]:
                    if sheet_name in workbook.sheetnames:
                        worksheet = workbook[sheet_name]
                        data_part = data.get(json_key)
                        if data_part:
                            processing_func(worksheet, data_part)
                        else:
                            print(f"   ⚠️ Cảnh báo: Không tìm thấy key '{json_key}' trong dữ liệu.")
                    else:
                        print(f"   ⚠️ Cảnh báo: Không tìm thấy sheet '{sheet_name}'.")
            
            elif config["type"] == "array":
                processing_func = config["processor"]
                processing_func(workbook, data)
        
        workbook.save(OUTPUT_EXCEL_PATH)
        print(f"\n--- ✅ Đã điền dữ liệu và lưu thành công file: {OUTPUT_EXCEL_PATH} ---")
        
    except Exception as e:
        print(f"❌ Lỗi nghiêm trọng khi ghi file Excel: {e}")

    print("\n==========================================================")
    print(" KẾT THÚC QUY TRÌNH TẠO CÂU HỎI ".center(58, "="))
    print("==========================================================")
    
    return INTERMEDIATE_DATA_FILE, OUTPUT_EXCEL_PATH

# TEST hàm tạo
if __name__ == '__main__':
    hsk_level = "hsk3"
    pdf_folder_path = r"D:\Edmicro\Tools\create_hsk\input\hsk3_bk"
    output_folder_path = r"D:\Edmicro\Tools\create_hsk\output\test"
    run_question_generation(hsk_level, pdf_folder_path, output_folder_path)
