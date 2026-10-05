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
import sys
import re


def load_old_generated_data(old_output_folder: Optional[str]) -> dict:
    """Đọc file generated_question_data.json từ thư mục output cũ nếu có."""
    if not old_output_folder:
        return {}

    old_json_path = os.path.join(old_output_folder, "generated_question_data.json")
    if not os.path.isfile(old_json_path):
        print(f"⚠️ Không tìm thấy file generated_question_data.json trong '{old_output_folder}'. Bỏ qua dữ liệu cũ.")
        return {}

    try:
        with open(old_json_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        if isinstance(data, dict):
            print(f"✅ Đã nạp dữ liệu câu hỏi cũ từ '{old_json_path}'.")
            return data
        print(f"⚠️ File JSON cũ không có định dạng object hợp lệ: '{old_json_path}'. Bỏ qua dữ liệu cũ.")
    except (OSError, json.JSONDecodeError) as exc:
        print(f"⚠️ Không thể đọc dữ liệu câu hỏi cũ từ '{old_json_path}': {exc}. Bỏ qua dữ liệu cũ.")

    return {}


def build_old_questions_context(prompt_name: str, old_generated_data: dict) -> Optional[str]:
    """Tạo khối context nhắc AI tránh lặp từ dữ liệu cũ cùng prompt_name."""
    if not old_generated_data:
        return None

    old_prompt_data = old_generated_data.get(prompt_name)
    if old_prompt_data is None:
        return None

    def collect_string_values(value: Any, bucket: list[str]):
        if isinstance(value, str):
            cleaned = " ".join(value.split())
            if cleaned:
                bucket.append(cleaned)
            return
        if isinstance(value, list):
            for item in value:
                collect_string_values(item, bucket)
            return
        if isinstance(value, dict):
            for item in value.values():
                collect_string_values(item, bucket)

    def unique_keep_order(items: list[str]) -> list[str]:
        seen = set()
        result = []
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result

    raw_strings: list[str] = []
    collect_string_values(old_prompt_data, raw_strings)
    unique_strings = unique_keep_order(raw_strings)

    serialized = json.dumps(old_prompt_data, ensure_ascii=False, indent=2)

    return (
        "RÀNG BUỘC BỔ SUNG BẮT BUỘC ĐỂ TRÁNH LẶP VỚI CÂU HỎI CŨ:\n"
        f"- prompt_name hiện tại: {prompt_name}\n"
        "- Đây là yêu cầu ưu tiên cao. Khi có xung đột nhẹ với ví dụ quen thuộc, hãy ưu tiên tạo nội dung khác với dữ liệu cũ.\n"
        "- Không được lặp lại hoặc chỉ thay rất ít chữ đối với: từ vựng trung tâm, mốc thời gian, địa điểm, hành động, nhân vật, chủ đề giao tiếp, học liệu chung, phương án nhiễu.\n"
        "- Tự động chọn các từ vựng khác trong danh sách từ vựng để tạo câu hỏi, ví dụ. Chỉ dùng lại từ cũ khi đó là từ bắt buộc hoặc không còn lựa chọn hợp lệ trong phạm vi bài.\n"
        "- Phải tạo bối cảnh mới rõ ràng, tránh toàn bộ mô típ đã xuất hiện ở trong các câu hỏi cũ như cùng khung giờ, cùng địa điểm, cùng chuỗi hành động, cùng kiểu hỏi đáp.\n"
        "- Trước khi trả kết quả, hãy tự đối chiếu với dữ liệu cũ và thay thế mọi câu nào còn quá giống.\n"
        "- Mục tiêu là bộ câu hỏi mới phải khác rõ về từ vựng sử dụng, từ khóa chính và khác rõ về tình huống sử dụng ngôn ngữ.\n\n"
        "CÁC CÂU/TỪ/NGỮ CẢNH CŨ ĐÃ XUẤT HIỆN, CẦN TRÁNH LẶP LẠI GẦN NGUYÊN VẸN.\n"
        "DỮ LIỆU THAM CHIẾU ĐẦY ĐỦ TỪ LẦN TẠO CŨ:\n"
        f"{serialized}"
    )

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

def format_structured_data_for_prompt(structured_data: Dict[str, Any], mode: int = 0) -> str:
    """
    Định dạng dữ liệu có cấu trúc (bao gồm tóm tắt tình huống) thành một chuỗi văn bản
    sạch sẽ để làm ngữ cảnh cho AI tạo câu hỏi.
    """
    content_parts = []
    
    # Thay đổi câu dẫn nhập dựa trên mode
    if mode == 1:
        content_parts.append("Dưới đây là nội dung TỪ VỰNG và TÓM TẮT BÀI KHÓA đã được bóc tách sạch sẽ. Hãy dựa vào đây để tạo câu hỏi:\n")
    elif mode == 2:
        content_parts.append("Dưới đây là nội dung TỪ VỰNG và NGỮ PHÁP TRỌNG TÂM đã được bóc tách sạch sẽ. Hãy dựa vào đây để tạo câu hỏi:\n")
    else:
        content_parts.append("Dưới đây là nội dung học thuật đầy đủ từ tài liệu. Dựa vào đây để tạo câu hỏi:\n")
    
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
            topic = context.get('topic', '')
            participants = ", ".join(context.get('participants', []))
            summary = context.get('summary', '')
            
            content_parts.append(f"Tình huống {i}: {topic}")
            content_parts.append(f"Nhân vật: {participants}")
            content_parts.append(f"Tóm tắt: {summary}\n")
        content_parts.append("\n")
        
    return "\n".join(content_parts)

# --- HÀM ĐIỀU PHỐI CHÍNH CỦA MODULE ---
def run_question_generation(
    level: str,
    pdf_path: str,
    output_folder_path: str,
    preproc_mode: int = 0,
    old_output_folder: Optional[str] = None
):
    """
    Thực hiện toàn bộ quy trình tạo câu hỏi.
    Returns:
        tuple[str, str] | tuple[None, None]: Đường dẫn đến file data trung gian và file excel output, hoặc None nếu thất bại.
    """
    print("==========================================================")
    print(" BẮT ĐẦU QUY TRÌNH TẠO CÂU HỎI ".center(58, "="))
    print("==========================================================")

    # 1. Lấy cấu hình động dựa trên level
    PROMPT_CONFIGS = get_prompt_config(level)
    if not PROMPT_CONFIGS:
        print(f"❌ Lỗi: Không thể tiếp tục vì không có cấu hình cho '{level}'.")
        return None, None
    
    # --- 1. XÁC ĐỊNH CÁC ĐƯỜNG DẪN ĐỘNG ---
    RESOURCES_DIR = get_resource_path("resources")

    # Mặc định
    prompt_file_name = "extract_lesson_structure.txt"
    
    if preproc_mode == 1:
        prompt_file_name = "extract_words_texts_structure.txt"
    elif preproc_mode == 2:
        prompt_file_name = "extract_words_grammars_structure.txt"
    
    PROMPTS_FOLDER = os.path.join(RESOURCES_DIR, "prompts", "create", level)
    SCHEMAS_FOLDER = os.path.join(RESOURCES_DIR, "schema", "create", level)
    # (MỚI) Đường dẫn cho prompt và schema tiền xử lý
    PREPROCESSING_PROMPT_PATH = os.path.join(RESOURCES_DIR, "prompts", "preprocessing", prompt_file_name)
    PREPROCESSING_SCHEMA_PATH = os.path.join(RESOURCES_DIR, "schema", "preprocessing", "extract_lesson_structure.json")
    EXCEL_TEMPLATE_PATH = os.path.join(RESOURCES_DIR, "sheet", f"{level}.xlsx")

    # --- 2. CHUẨN BỊ MÔI TRƯỜNG ---
    if not pdf_path or not os.path.isfile(pdf_path):
        print(f"❌ Lỗi: Không tìm thấy file PDF tại '{pdf_path}'.")
        return None, None
    print("✅ Đã nhận file PDF đầu vào.")

    pdf_files = [pdf_path]
    if level in ["topik1", "topik2", "topik3"]:
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_filename = f"{base_name}_{level}.xlsx"    
    else:
        output_filename = f"{level}_output.xlsx"
    OUTPUT_EXCEL_PATH = os.path.join(output_folder_path, output_filename)
    INTERMEDIATE_DATA_FILE = os.path.join(output_folder_path, "generated_question_data.json")
    old_generated_data = load_old_generated_data(old_output_folder)
    
    # --- (LOGIC MỚI) BƯỚC TIỀN XỬ LÝ ĐỘNG ---
    preprocessed_text_content: Optional[str] = None
    # Điều kiện: chỉ có 1 file và tên chứa "bài khóa" (không phân biệt hoa thường)
    if level in ["hsk1", "hsk4", "hsk5", "hsk2", "hsk3"]:
        print("\n--- Phát hiện file bài học đơn lẻ. Bắt đầu quy trình tiền xử lý. ---")
        try:
            structured_data = extract_structured_data_from_pdf(
                pdf_path=pdf_path,
                prompt_file_path=PREPROCESSING_PROMPT_PATH,
                schema_file_path=PREPROCESSING_SCHEMA_PATH,
                service_tier="flex"
            )
            preprocessed_text_content = format_structured_data_for_prompt(structured_data, preproc_mode)
            print("--- ✅ Tiền xử lý thành công. Sử dụng dữ liệu đã bóc tách để tạo câu hỏi. ---")
            with open(os.path.join(output_folder_path, "preprocessed_content.txt"), 'w', encoding='utf-8') as f:
                f.write(preprocessed_text_content)

        except Exception as e:
            print(f"❌ Lỗi trong quá trình tiền xử lý: {e}.")
            print("--- ⚠️ Sẽ tiếp tục tạo câu hỏi bằng file PDF gốc. Kết quả có thể không chính xác. ---")
            preprocessed_text_content = None

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
                'schema_file_path': os.path.join(SCHEMAS_FOLDER, f"{p_name}.json"),
                'service_tier': 'flex'
            }
            old_questions_context = build_old_questions_context(p_name, old_generated_data)
            if old_questions_context:
                api_kwargs['extra_context_text'] = old_questions_context
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