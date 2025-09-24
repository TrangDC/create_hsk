# explanation_generator.py
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import openpyxl
from config.hsk_explanation_configs import get_explanation_config
from config.hsk_question_configs import get_prompt_config as get_question_gen_config
from services.explanation_sheet_formatters import render_ds_vocab_explanation # Import hàm đặc biệt này
from call_vertexai import generate_content_from_pdfs
import inspect

def create_dynamic_prompt(task: dict, hsk_level: str) -> str:
    """Tạo prompt động bằng cách gọi hàm builder từ config."""
    q_type = task['question_type']
    
    config_map = get_explanation_config(hsk_level)
    q_config = config_map.get(q_type)

    if not q_config or 'prompt_builder' not in q_config:
        return None
    
    try:
        with open(q_config['prompt_path'], 'r', encoding='utf-8') as f:
            prompt_template = f.read()
        
        # Gọi hàm builder tương ứng từ config
        return q_config['prompt_builder'](task, prompt_template)

    except (FileNotFoundError, KeyError) as e:
        print(f"Lỗi khi tạo prompt cho '{q_type}': {e}")
        return None

def load_source_data(filepath: str) -> dict:
    """Đọc file JSON chứa dữ liệu câu hỏi đã được tạo."""
    print(f"--- Đang đọc dữ liệu nguồn từ: {filepath} ---")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Lỗi: Không tìm thấy file dữ liệu nguồn '{filepath}'.")
        print("Vui lòng chạy 'main_processor.py' trước để tạo file này.")
        return None
    except json.JSONDecodeError:
        print(f"❌ Lỗi: File '{filepath}' không chứa dữ liệu JSON hợp lệ.")
        return None

def flatten_question_data(data_map: dict, hsk_level: str) -> list:
    print("--- Đang chuẩn hóa và làm phẳng dữ liệu câu hỏi ---")
    flat_list = []
    question_gen_config = get_question_gen_config(hsk_level)
    if not question_gen_config:
        print(f"❌ Lỗi: Không tìm thấy cấu hình TẠO CÂU HỎI cho '{hsk_level}'.")
        return []

    for prompt_name, data in data_map.items():
        prompt_details = question_gen_config.get(prompt_name)
        if not prompt_details:
            print(f"   ⚠️ Cảnh báo: Không tìm thấy chi tiết cho prompt '{prompt_name}'. Bỏ qua.")
            continue
        
        data_type = prompt_details.get("type")
        if data_type == "keyed":
            for json_key, content in data.items():
                if json_key == "listening_comprehension":
                    for material_block in content:
                        task = {
                            "prompt_name": prompt_name,
                            "question_type": json_key,
                            "data": material_block # 'data' bây giờ chứa TOÀN BỘ học liệu
                        }
                        flat_list.append(task)
                elif json_key in ["passage_cloze", "long_passage_comprehension"]:
                    task = {
                        "prompt_name": prompt_name,
                        "question_type": json_key,
                        "data": content # 'data' chứa toàn bộ object passage_cloze
                    }
                    flat_list.append(task)
                else:
                    # Logic cũ cho các dạng 'keyed' khác
                    questions = content.get('questions', []) if isinstance(content, dict) else content
                    shared_material = content.get('shared_material') if isinstance(content, dict) else None
                    for question in questions:
                        task = {
                            "prompt_name": prompt_name,
                            "question_type": json_key,
                            "data": question
                        }
                        if shared_material:
                            task['shared_material'] = shared_material
                        flat_list.append(task)

        elif data_type == "array":
            for question in data:
                flat_list.append({ "prompt_name": prompt_name, "question_type": question.get('kind'), "data": question })

    print(f"✅ Đã tìm thấy tổng cộng {len(flat_list)} task.") # Chú ý, đây là số task, không phải câu hỏi
    return flat_list

def generate_explanations_concurrently(flat_question_list: list, hsk_level: str) -> list:
    """Gọi Vertex AI song song để tạo lời giải cho tất cả các câu hỏi."""
    print("\n--- Bắt đầu gọi API đồng thời để tạo lời giải ---")

    explanation_configs = get_explanation_config(hsk_level)
    if not explanation_configs:
        print("Lỗi: Không có cấu hình prompt lời giải, không thể tiếp tục.")
        return flat_question_list
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_task = {}
        for task in flat_question_list:
            if task['question_type'] in ["writing_from_keywords", "writing_from_image"]:
                # Không cần gọi API, lời giải đã có trong task['data']
                task['explanation_details'] = task['data'] # Gán trực tiếp
                print(f"   - ✅ Lấy lời giải có sẵn cho dạng: {task['question_type']}")
                continue # Chuyển sang task tiếp theo            
            if task['question_type'] in explanation_configs:
                prompt_text = create_dynamic_prompt(task, hsk_level)
                if prompt_text:
                    config = explanation_configs[task['question_type']]
                    temp_prompt_filename = f"temp_prompt_{os.getpid()}_{id(task)}.txt"
                    with open(temp_prompt_filename, "w", encoding="utf-8") as f:
                        f.write(prompt_text)
                    
                    future = executor.submit(
                        generate_content_from_pdfs,
                        pdf_file_paths=[],
                        prompt_file_path=temp_prompt_filename,
                        schema_file_path=config['schema_path']
                    )
                    future_to_task[future] = (task, temp_prompt_filename)

        for future in as_completed(future_to_task):
            task, temp_prompt_filename = future_to_task[future]
            try:
                explanation_data = future.result()
                task['explanation_details'] = explanation_data
                print(f"   - ✅ Nhận lời giải cho dạng: {task['question_type']}")
            except Exception as exc:
                print(f"   - ❌ Lỗi khi tạo lời giải cho {task['question_type']}: {exc}")
                task['explanation_details'] = None
            finally:
                os.remove(temp_prompt_filename)
    
    print("--- ✅ Đã tạo xong tất cả lời giải ---")
    return flat_question_list

def update_excel_with_explanations(excel_path: str, enriched_question_list: list, hsk_level: str):
    """Mở file Excel và ghi các lời giải đã được tạo vào cột 'I', sau đó thay thế chữ cái bằng số trong cột I (trừ hàng tiêu đề)."""
    print(f"\n--- Bắt đầu cập nhật lời giải vào file: {excel_path} ---")

    # Lấy config renderer động
    config_map = get_explanation_config(hsk_level)
    if not config_map: return
    
    try:
        workbook = openpyxl.load_workbook(excel_path)
        row_counters = {sheet.title: 2 for sheet in workbook.worksheets}

        for task in enriched_question_list:
            q_type = task.get('question_type')
            q_config = config_map.get(q_type)
            
            if not q_config: continue

            sheet_name = q_config.get('sheet_name')
            renderer_func = q_config.get('renderer')
            explanation_data = task.get('explanation_details')

            if sheet_name and renderer_func and explanation_data and sheet_name in workbook.sheetnames:
                worksheet = workbook[sheet_name]
                current_row = row_counters[sheet_name]
                
                # Xử lý đặc biệt cho các renderer xử lý theo cụm
                if q_type in ["listening_comprehension", "reading_comprehension_short_passage", "passage_cloze", "long_passage_comprehension"]: # <-- THÊM DẠNG MỚI
                    # Cần truyền vào: worksheet, dòng bắt đầu, dữ liệu lời giải, và dữ liệu câu hỏi gốc
                    rows_written = renderer_func(worksheet, current_row, explanation_data, task)
                    row_counters[sheet_name] += rows_written
                elif q_type in ["sentence_sequence_reordering", "image_with_word_sentence_creation", "main_idea_comprehension"]: # <-- THÊM DẠNG MỚI
                    cell = worksheet[f'I{current_row}']
                    renderer_func(cell, explanation_data, task) # Gọi với 3 tham số
                    row_counters[sheet_name] += 1
                else:
                    # Logic cũ cho các renderer ghi 1 dòng
                    cell = worksheet[f'I{current_row}']
                    renderer_func(cell, explanation_data) # Sửa đổi nếu cần
                    row_counters[sheet_name] += 1
        # Xử lý đặc biệt cho sheet "ĐS (img) HSK1" và "ĐS Ko phụ đề (img) HSK1"
        if "ĐS (img) HSK1" in workbook.sheetnames:
            ds_worksheet = workbook["ĐS (img) HSK1"]
            render_ds_vocab_explanation(ds_worksheet, "ĐS (img) HSK1")
        if "ĐS Ko phụ đề (img) HSK1" in workbook.sheetnames:
            ds_no_sub_worksheet = workbook["ĐS Ko phụ đề (img) HSK1"]
            render_ds_vocab_explanation(ds_no_sub_worksheet, "ĐS Ko phụ đề (img) HSK1")        
        workbook.save(excel_path)
    except Exception as e:
        print(f"❌ Lỗi nghiêm trọng khi ghi file Excel: {e}")    

def run_explanation_generation(hsk_level: str, source_data_file: str, excel_output_path: str):
    """
    Thực hiện toàn bộ quy trình tạo lời giải.
    """
    print("\n==========================================================")
    print(" BẮT ĐẦU QUY TRÌNH TẠO LỜI GIẢI ".center(58, "="))
    print("==========================================================")
    
    # 1. Tải và chuẩn hóa dữ liệu
    data_map = load_source_data(source_data_file)
    if not data_map: return
    flat_question_list = flatten_question_data(data_map, hsk_level)
    
    # 2. Gọi API tạo lời giải
    enriched_question_list = generate_explanations_concurrently(flat_question_list, hsk_level)

    # 3. Cập nhật vào Excel
    update_excel_with_explanations(excel_output_path, enriched_question_list, hsk_level)
    
    print("\n==========================================================")
    print(" KẾT THÚC QUY TRÌNH TẠO LỜI GIẢI ".center(58, "="))
    print("==========================================================")

# Test hàm xử lý
if __name__ == "__main__":
    HSK_LEVEL = "hsk3"
    SOURCE_DATA_FILE = r"D:\Edmicro\Tools\create_hsk\output\hsk3_20250918_134052\generated_question_data.json"
    EXCEL_OUTPUT_PATH = r"D:\Edmicro\Tools\create_hsk\output\hsk3_20250918_134052\hsk3_output.xlsx"
    
    run_explanation_generation(HSK_LEVEL, SOURCE_DATA_FILE, EXCEL_OUTPUT_PATH)