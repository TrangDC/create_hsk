# services/question_sheet_processors.py

from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.workbook.workbook import Workbook
from openpyxl.styles import Alignment
import random

# --- CÁC HÀM ĐIỀN DỮ LIỆU VÀO EXCEL ---
# Sheet TN PA đúng (img) (HSK1)
def populate_individual_image_matching(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'TN PA đúng (img) (HSK1)'.
    Key JSON: individual_image_matching
    """
    print(f"   -> Đang điền dữ liệu vào sheet: {worksheet.title}")
    start_row = 2  # Bắt đầu điền từ hàng thứ 2
    for i, question in enumerate(data, start=start_row):
        # Cột F: Mô tả ảnh + script
        image_options_str = "\n".join(question.get('image_options', []))
        script_chinese = question.get('script_chinese', '')
        content_f = f"{image_options_str}\n\n{script_chinese}"
        
        worksheet[f'F{i}'] = content_f
        
        # Cột H: Đáp án
        worksheet[f'H{i}'] = question.get('correct_answer')
    print(f"   ✅ Hoàn thành điền {len(data)} câu hỏi.")

# Sheet ĐS (img) HSK1 và ĐS Ko phụ đề (img) HSK1
def populate_true_false_from_array(workbook, data: list):
    """
    Điền dữ liệu cho 2 sheet Đúng/Sai từ một mảng JSON phẳng.
    Key JSON: (không có, xử lý toàn bộ mảng)
    """
    print(f"   -> Đang phân phối dữ liệu Đúng/Sai vào các sheet...")
    # Lấy các sheet cần điền
    try:
        sheet_img = workbook["ĐS (img) HSK1"]
        sheet_vocab = workbook["ĐS Ko phụ đề (img) HSK1"]
    except KeyError as e:
        print(f"   ❌ Lỗi: Không tìm thấy sheet cần thiết: {e}. Bỏ qua.")
        return

    # Khởi tạo bộ đếm hàng cho mỗi sheet
    row_counters = {
        "ĐS (img) HSK1": 2,
        "ĐS Ko phụ đề (img) HSK1": 2
    }

    # Lặp qua từng câu hỏi trong mảng dữ liệu
    for item in data:
        kind = item.get("kind")
        sheet_to_populate = None
        if kind == "script_hinh_anh":
            sheet_to_populate = sheet_img
            current_row = row_counters["ĐS (img) HSK1"]
            row_counters["ĐS (img) HSK1"] += 1
            # Định dạng nội dung cột F
            content_f = f"Ảnh: {item.get('image_des', '')}\nScript: {item.get('script', '')}"
        elif kind == "tuvung_hinh_anh":
            sheet_to_populate = sheet_vocab
            current_row = row_counters["ĐS Ko phụ đề (img) HSK1"]
            row_counters["ĐS Ko phụ đề (img) HSK1"] += 1
            # Định dạng nội dung cột F
            content_f = f"Ảnh: {item.get('image_des', '')}\nTừ vựng: {item.get('script', '')}\nPinyin: {item.get('pinyin', '')}"
        # Nếu tìm thấy loại câu hỏi hợp lệ, điền dữ liệu
        if sheet_to_populate:
            sheet_to_populate.cell(row=current_row, column=3).value = "DS"
            sheet_to_populate.cell(row=current_row, column=4).value = "NB"
            sheet_to_populate.cell(row=current_row, column=6).value = content_f
            sheet_to_populate.cell(row=current_row, column=8).value = f"đúng sai: {item.get('correct_answer')}"
            if kind == "script_hinh_anh":
                explanation = f"{item.get('explanation', '')}\n\nPhụ đề:\n{item.get('script', '')}\n{item.get('pinyin', '')}\n\nTạm dịch: {item.get('translation', '')}"
            else:  # tuvung_hinh_anh
                explanation = f"{item.get('explanation', '')}\n\nTạm dịch: {item.get('translation', '')}"
            sheet_to_populate.cell(row=current_row, column=9).value = explanation
    print(f"   ✅ Hoàn thành điền dữ liệu Đúng/Sai.")

# Sheet TN PA đúng (img) (HL) (HSK1)
def populate_shared_image_comprehension(worksheet, data: dict):
    """
    Điền dữ liệu cho sheet 'TN PA đúng (img) (HL) (HSK1)'.
    Key JSON: shared_image_comprehension
    Sửa đổi: Merge ô cột B cho học liệu, điền script vào cột E.
    """
    print(f"   -> Đang điền dữ liệu vào sheet: {worksheet.title}")
    
    questions = data.get('questions', [])
    if not questions:
        print("   ⚠️ Cảnh báo: Không có câu hỏi nào để điền cho dạng này.")
        return

    # --- Cấu hình hàng bắt đầu và số lượng câu hỏi ---
    start_row = 2  # Giả sử tiêu đề ở hàng 1, dữ liệu bắt đầu từ hàng 2
    num_questions = len(questions)
    end_row = start_row + num_questions - 1

    # --- 1. Xử lý Học liệu chung (Cột B, merged) ---
    shared_material = data.get('shared_material', [])
    shared_material_str = "\n".join(
        f"{desc}" for idx, desc in enumerate(shared_material)
    )
    
    # Merge các ô từ start_row đến end_row trong cột B
    # Ví dụ: nếu có 4 câu, sẽ merge từ B2 đến B5
    if num_questions > 0:
        merge_range = f'B{start_row}:B{end_row}'
        worksheet.merge_cells(merge_range)
        
        # Gán giá trị vào ô trên cùng bên trái của vùng đã merge
        top_left_cell = worksheet[f'B{start_row}']
        top_left_cell.value = shared_material_str
        
        # Căn chỉnh nội dung lên trên và tự động xuống dòng cho đẹp
        top_left_cell.alignment = Alignment(vertical='top', wrap_text=True)

    # --- 2. Điền script (Cột E) và đáp án (Cột H) ---
    for i, question in enumerate(questions):
        current_row = start_row + i
        
        # Cột E: Script câu hỏi
        worksheet[f'E{current_row}'] = question.get('script_chinese', '')
        
        # Cột H: Đáp án
        worksheet[f'H{current_row}'] = question.get('correct_answer')
        
    print(f"   ✅ Hoàn thành điền học liệu và {num_questions} câu hỏi.")

# Sheet TN PA đúng (HSK1)
def populate_reading_comprehension_choice(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'TN PA đúng (HSK1)'.
    Key JSON: reading_comprehension_choice
    """
    print(f"   -> Đang điền dữ liệu vào sheet: {worksheet.title}")
    start_row = 2
    for i, question in enumerate(data, start=start_row):
        # Cột F: Ngữ cảnh + Câu hỏi
        context = question.get('context_chinese', '')
        query = question.get('query_chinese', '')
        worksheet[f'F{i}'] = f"{context}\n{query}"
        
        # Cột G: Các lựa chọn đáp án
        options = question.get('answer_options', [])
        options_str = "\n".join(
            f"{opt.get('chinese_text', '')}<br/>{opt.get('pinyin', '')}" for opt in options
        )
        worksheet[f'G{i}'] = options_str

        # Cột H: Đáp án đúng
        worksheet[f'H{i}'] = question.get('correct_answer')
    print(f"   ✅ Hoàn thành điền {len(data)} câu hỏi.")

# Sheet TN chọn ảnh (img) (HL) (HSK1)
def populate_image_matching_shared(worksheet, data: dict):
    """
    Điền dữ liệu cho sheet 'TN chọn ảnh đúng (HL) (HSK1)'.
    Key JSON: image_matching_questions
    """
    print(f"   -> Đang điền dữ liệu vào sheet: {worksheet.title}")
    questions = data.get('questions', [])
    if not questions:
        print("   ⚠️ Cảnh báo: Không có câu hỏi nào để điền.")
        return

    start_row = 2
    num_questions = len(questions)
    end_row = start_row + num_questions - 1

    # Cột B: Học liệu chung (merge)
    shared_material = data.get('shared_material', [])
    shared_material_str = "\n".join(
        f"{desc}" for idx, desc in enumerate(shared_material)
    )
    if num_questions > 0:
        worksheet.merge_cells(f'B{start_row}:B{end_row}')
        top_cell = worksheet[f'B{start_row}']
        top_cell.value = shared_material_str
        top_cell.alignment = Alignment(vertical='top', wrap_text=True)

    # Cột F và H: Câu hỏi và đáp án
    for i, question in enumerate(questions):
        current_row = start_row + i
        # Cột F: Câu hỏi
        chinese = question.get('question_text_chinese', '')
        pinyin = question.get('pinyin', '')
        worksheet[f'F{current_row}'] = f"{chinese} （ ）\n{pinyin}"
        # Cột H: Đáp án
        worksheet[f'H{current_row}'] = question.get('correct_answer')
    print(f"   ✅ Hoàn thành điền học liệu và {num_questions} câu hỏi.")

# Sheet TN câu trả lời đúng (HL) (HSK1)
def populate_sentence_matching_shared(worksheet, data: dict):
    """
    Điền dữ liệu cho sheet 'TN câu trả lời đúng (HL) (HSK1)'.
    Key JSON: sentence_matching_questions
    """
    print(f"   -> Đang điền dữ liệu vào sheet: {worksheet.title}")
    questions = data.get('questions', [])
    if not questions:
        print("   ⚠️ Cảnh báo: Không có câu hỏi nào để điền.")
        return

    start_row = 2
    num_questions = len(questions)
    end_row = start_row + num_questions - 1

    # Cột B: Học liệu chung (merge)
    shared_material = data.get('shared_material', [])
    shared_material_lines = [""]
    for item in shared_material:
        letter = item.get('option_letter', '')
        chinese = item.get('chinese_text', '')
        pinyin = item.get('pinyin', '')
        # Định dạng thụt lề cho pinyin
        shared_material_lines.append(f"{letter}. {chinese}\n   {pinyin}")
    
    shared_material_str = "\n".join(shared_material_lines)
    
    if num_questions > 0:
        worksheet.merge_cells(f'B{start_row}:B{end_row}')
        top_cell = worksheet[f'B{start_row}']
        top_cell.value = shared_material_str
        top_cell.alignment = Alignment(vertical='top', wrap_text=True, indent=0)

    # Cột F và H: Câu hỏi và đáp án
    for i, question in enumerate(questions):
        current_row = start_row + i
        # Cột F: Câu hỏi
        chinese = question.get('question_text_chinese', '')
        pinyin = question.get('pinyin', '')
        worksheet[f'F{current_row}'] = f"{chinese} （ ）\n{pinyin}"
        # Cột H: Đáp án
        # tạo map label đáp án với số thứ tự
        map_labels = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}
        answer_label = question.get('correct_answer', '')
        if answer_label in map_labels:
            answer_index = map_labels[answer_label]
            worksheet[f'H{current_row}'] = f"{answer_index}"

    print(f"   ✅ Hoàn thành điền học liệu và {num_questions} câu hỏi.")

# Sheet TN chọn từ đúng (HL) (HSK1)
def populate_word_fill_in_shared(worksheet, data: dict):
    """
    Điền dữ liệu cho sheet 'TN chọn từ đúng (HL) (HSK1)'.
    Key JSON: word_fill_in_questions
    (Nâng cấp để xử lý cả câu đơn và hội thoại)
    """
    print(f"   -> Đang điền dữ liệu vào sheet: {worksheet.title}")
    questions = data.get('questions', [])
    if not questions:
        print("   ⚠️ Cảnh báo: Không có câu hỏi nào để điền.")
        return

    start_row = 2
    num_questions = len(questions)
    end_row = start_row + num_questions - 1

    # Cột B: Học liệu chung (merge) - Logic này không đổi
    shared_material = data.get('shared_material', [])
    shared_material_lines = [""]
    for item in shared_material:
        letter = item.get('option_letter', '')
        chinese = item.get('chinese_word', '')
        pinyin = item.get('pinyin', '')
        shared_material_lines.append(f"{letter}. {chinese}\n   {pinyin}")

    shared_material_str = "\n".join(shared_material_lines)

    if num_questions > 0:
        worksheet.merge_cells(f'B{start_row}:B{end_row}')
        top_cell = worksheet[f'B{start_row}']
        top_cell.value = shared_material_str
        top_cell.alignment = Alignment(vertical='top', wrap_text=True, indent=0)

    # Cột F và H: Câu hỏi và đáp án (Logic được nâng cấp)
    for i, question in enumerate(questions):
        current_row = start_row + i
        
        # Cột F: Câu hỏi (đã có thể xử lý hội thoại)
        question_lines_formatted = []
        for line in question.get('lines', []):
            speaker = line.get('speaker', '')
            prefix = f"{speaker}：" if speaker else ""
            chinese = line.get('chinese_text', '')
            pinyin = line.get('pinyin', '')
            question_lines_formatted.append(f"{prefix}{chinese}\n{' ' * len(prefix)}{pinyin}")
        
        worksheet[f'F{current_row}'] = "\n".join(question_lines_formatted)
        
        # Cột H: Đáp án - Logic này không đổi
        answer_label = question.get('correct_answer', '')
        if answer_label:
            # Tạo map label đáp án với số thứ tự
            map_labels = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}
            if answer_label in map_labels:
                answer_index = map_labels[answer_label]
                worksheet[f'H{current_row}'] = f"{answer_index}"
            else:
                worksheet[f'H{current_row}'] = answer_label

    print(f"   ✅ Hoàn thành điền học liệu và {num_questions} câu hỏi.")

# Dạng 1 - HSK2: Đúng sai (img) (HSK2)
def populate_true_false_image(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'Đúng sai (img) (HSK2)'.
    Key JSON: true_false_image_questions
    """
    print(f"   -> Đang điền dữ liệu vào sheet: {worksheet.title}")
    start_row = 2  # Bắt đầu điền từ hàng thứ 2
    for i, question in enumerate(data, start=start_row):
        # Cột F: Mô tả ảnh + script
        image_des = question.get('image_des', '')
        script = question.get('script', '')
        content_f = f"Ảnh: {image_des}\nScript: {script}"
        worksheet[f'F{i}'] = content_f
        
        # Cột H: Đáp án
        answer = question.get('correct_answer')
        worksheet[f'H{i}'] = f"đúng sai: {answer}"
        
    print(f"   ✅ Hoàn thành điền {len(data)} câu hỏi.")

# Dạng 3 & 4 - HSK2: TN PA đúng (HSK2) và TN PA đúng_v2 (HSK2)
def populate_reading_comprehension_dialogue(worksheet, data: list):
    """
    Điền dữ liệu cho các sheet đọc hiểu hội thoại.
    Hàm này xử lý cả hội thoại ngắn (2 lượt lời) và dài (4 lượt lời).
    Key JSON: reading_comprehension_dialogue_2_lines / reading_comprehension_dialogue_4_lines
    """
    print(f"   -> Đang điền dữ liệu vào sheet: {worksheet.title}")
    start_row = 2
    for i, question in enumerate(data, start=start_row):
        # --- Cột F: Hội thoại + Câu hỏi ---
        dialogue_parts = []
        for line in question.get('dialogue', []):
            speaker = line.get('speaker', '')
            chinese = line.get('line_chinese', '')
            pinyin = line.get('line_pinyin', '')
            # Thêm thụt lề cho pinyin để dễ đọc
            dialogue_parts.append(f"{speaker}： {chinese}")
        
        query = question.get('query_chinese', '')
        dialogue_parts.append(f"问： {query}")
        
        worksheet[f'F{i}'] = "\n".join(dialogue_parts)
        
        # --- Cột G: Các lựa chọn đáp án ---
        options = question.get('answer_options', [])
        options_parts = []
        for opt in options:
            chinese = opt.get('chinese_text', '')
            pinyin = opt.get('pinyin', '')
            if pinyin:
                options_parts.append(f"{chinese}<br/>{pinyin}")
            else:
                options_parts.append(f"{chinese}")    
        worksheet[f'G{i}'] = "\n".join(options_parts)

        # --- Cột H: Đáp án đúng ---
        worksheet[f'H{i}'] = question.get('correct_answer')
        
    print(f"   ✅ Hoàn thành điền {len(data)} câu hỏi.")

# Dạng 6 - HSK2: ĐS lựa chọn (HSK2)
def populate_true_false_statement(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'ĐS lựa chọn (HSK2)'.
    Key JSON: true_false_statement_questions
    """
    print(f"   -> Đang điền dữ liệu vào sheet: {worksheet.title}")
    start_row = 2
    for i, question in enumerate(data, start=start_row):
        # Cột F: Script + Statement
        script_chinese = question.get('script_chinese', '')
        script_pinyin = question.get('script_pinyin', '')
        statement_chinese = question.get('statement_chinese', '')
        statement_pinyin = question.get('statement_pinyin', '')
        
        # Thêm thụt lề cho pinyin của statement để dễ đọc
        content_f = f"{script_chinese}\n{script_pinyin}\n★ {statement_chinese}\n    {statement_pinyin}"
        worksheet[f'F{i}'] = content_f
        
        # Cột H: Đáp án
        answer = question.get('correct_answer')
        worksheet[f'H{i}'] = f"đúng sai: {answer}"

    print(f"   ✅ Hoàn thành điền {len(data)} câu hỏi.")

# Dạng 8 - HSK2: TN câu trả lời đúng (HL) (HSK2)
def populate_sentence_matching_inverted(worksheet, data: dict):
    """
    Điền dữ liệu cho sheet 'TN câu trả lời đúng (HL) (HSK2)'.
    Logic tương tự như hàm populate_sentence_matching_shared của HSK1.
    Key JSON: sentence_matching_inverted_questions
    """
    print(f"   -> Đang điền dữ liệu vào sheet: {worksheet.title}")
    questions = data.get('questions', [])
    if not questions:
        print("   ⚠️ Cảnh báo: Không có câu hỏi nào để điền.")
        return

    start_row = 2
    num_questions = len(questions)
    end_row = start_row + num_questions - 1

    # Cột B: Học liệu chung (merge)
    shared_material = data.get('shared_material', [])
    shared_material_lines = [""]
    for item in shared_material:
        letter = item.get('option_letter', '')
        chinese = item.get('chinese_text', '')
        pinyin = item.get('pinyin', '')
        shared_material_lines.append(f"{letter}. {chinese}\n   {pinyin}")
    
    shared_material_str = "\n".join(shared_material_lines)
    
    if num_questions > 0:
        worksheet.merge_cells(f'B{start_row}:B{end_row}')
        top_cell = worksheet[f'B{start_row}']
        top_cell.value = shared_material_str
        top_cell.alignment = Alignment(vertical='top', wrap_text=True, indent=0)

    # Cột F và H: Câu hỏi và đáp án
    for i, question in enumerate(questions):
        current_row = start_row + i
        # Cột F: Câu hỏi
        chinese = question.get('question_text_chinese', '')
        pinyin = question.get('pinyin', '')
        # Theo ví dụ, câu hỏi có thể có dấu ( ) ở cuối
        worksheet[f'F{current_row}'] = f"{chinese} (   )\n{pinyin}"
        # Cột H: Đáp án
        # Tạo map label đáp án với số thứ tự
        map_labels = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6}
        answer_label = question.get('correct_answer', '')
        if answer_label in map_labels:
            answer_index = map_labels[answer_label]
            worksheet[f'H{current_row}'] = f"{answer_index}"

    print(f"   ✅ Hoàn thành điền học liệu và {num_questions} câu hỏi.")

# Dạng 2 - HSK3: ĐS nghe chọn (HSK3)  
def populate_true_false_listening_choice(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'ĐS nghe chọn (HSK3)'.
    Key JSON: true_false_listening_choice
    """
    print(f"   -> Đang điền dữ liệu vào sheet: {worksheet.title}")
    start_row = 2
    for i, question in enumerate(data, start=start_row):
        # Cột F: Statement + Script
        statement = question.get('statement_chinese', '')
        script = question.get('script_chinese', '')
        
        content_f = f"{statement} （ ）\nScript: {script}"
        worksheet[f'F{i}'] = content_f
        
        # Cột H: Đáp án
        answer = question.get('correct_answer')
        worksheet[f'H{i}'] = f"đúng sai: {answer}"

    print(f"   ✅ Hoàn thành điền {len(data)} câu hỏi.")

# Dạng 7: TN PA đúng ko pinyin_v3 (HSK3)
def populate_reading_comprehension_v3(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'TN PA đúng ko pinyin_v3 (HSK3)'.
    Key JSON: reading_comprehension_no_pinyin_v3
    """
    print(f"   -> Đang điền dữ liệu vào sheet: {worksheet.title}")
    start_row = 2
    for i, question in enumerate(data, start=start_row):
        # Cột F: Script + Query
        script = question.get('script_chinese', '')
        query = question.get('query_chinese', '')
        worksheet[f'F{i}'] = f"{script}\n{query}"
        
        # Cột G: Các lựa chọn đáp án
        options = question.get('answer_options', [])
        worksheet[f'G{i}'] = "\n".join(options)

        # Cột H: Đáp án đúng
        worksheet[f'H{i}'] = question.get('correct_answer')
        
    print(f"   ✅ Hoàn thành điền {len(data)} câu hỏi.")

# Dạng 8: Sắp xếp câu (HSK3)
def populate_sentence_reordering(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'Sắp xếp câu (HSK3)'.
    Key JSON: sentence_reordering
    """
    print(f"   -> Đang điền dữ liệu vào sheet: {worksheet.title}")
    start_row = 2
    for i, question in enumerate(data, start=start_row):
        # Cột G: Các thành phần câu
        components = question.get('components', [])
        worksheet[f'G{i}'] = "; ".join(components)
        
        # Cột H: Đáp án đúng
        worksheet[f'H{i}'] = question.get('correct_order')
        
    print(f"   ✅ Hoàn thành điền {len(data)} câu hỏi.")

# Dạng 9: Điền từ đúng (HSK3)
def populate_word_fill_in_display_answer(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'Điền từ đúng (HSK3)'.
    Key JSON: word_fill_in_display_answer
    """
    print(f"   -> Đang điền dữ liệu vào sheet: {worksheet.title}")
    start_row = 2
    for i, question in enumerate(data, start=start_row):
        # Ghép các thành phần lại thành câu hoàn chỉnh
        part1 = question.get('sentence_part_1', '')
        word = question.get('correct_word', '')
        pinyin = question.get('correct_word_pinyin', '')
        part2 = question.get('sentence_part_2', '')

        full_sentence = f"{part1} [{word}] ({pinyin}) {part2}"
        
        # Cột G: Điền câu hoàn chỉnh
        worksheet[f'G{i}'] = full_sentence
        
    print(f"   ✅ Hoàn thành điền {len(data)} câu hỏi.")

# HÀM TÁI SỬ DỤNG cho Dạng 4 (TN Nghe hiểu) và Dạng 8 (TN Đọc hiểu ngắn)
def populate_passage_with_multiple_questions(worksheet, data: list):
    """
    Điền dữ liệu cho các dạng bài có 1 học liệu chung cho nhiều câu hỏi.
    Hàm này sẽ merge ô ở cột B và điền dữ liệu cho các câu hỏi tương ứng.
    Key JSON: listening_comprehension / reading_comprehension_short_passage
    """
    print(f"   -> Đang điền dữ liệu vào sheet: {worksheet.title}")
    current_row = 2  # Bắt đầu từ hàng 2

    for passage_data in data:
        questions = passage_data.get('questions', [])
        num_questions = len(questions)
        
        if num_questions == 0:
            continue

        start_row_for_merge = current_row
        end_row_for_merge = current_row + num_questions - 1

        # --- Cột B: Merge và điền học liệu ---
        merge_range = f'B{start_row_for_merge}:B{end_row_for_merge}'
        worksheet.merge_cells(merge_range)
        top_left_cell = worksheet[f'B{start_row_for_merge}']
        top_left_cell.value = passage_data.get('script_chinese', '')
        top_left_cell.alignment = Alignment(vertical='top', wrap_text=True)

        # --- Cột F, G, H: Điền từng câu hỏi ---
        for question in questions:
            worksheet[f'F{current_row}'] = question.get('query_chinese', '')
            
            options = question.get('answer_options', [])
            worksheet[f'G{current_row}'] = "\n".join(options)
            
            worksheet[f'H{current_row}'] = question.get('correct_answer')
            
            current_row += 1 # Tăng số hàng cho câu hỏi tiếp theo

    print(f"   ✅ Hoàn thành điền {len(data)} học liệu.")

# Hàm cho Dạng 6: Sắp xếp các câu (HSK4)
def populate_sentence_sequence_reordering(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'Sắp xếp các câu (HSK4)'.
    Key JSON: sentence_sequence_reordering
    """
    print(f"   -> Đang điền dữ liệu vào sheet: {worksheet.title}")
    start_row = 2
    for i, question in enumerate(data, start=start_row):
        
        components = question.get('components', [])
        correct_order = question.get('correct_order', '')
        
        # Ghép các thành phần và đáp án thành một chuỗi duy nhất
        lines = []
        for comp in components:
            label = comp.get('label', '')
            text = comp.get('text', '')
            lines.append(f"{label}. {text}")
            
        lines.append(f"[{correct_order}]")
        
        # Cột G: Điền toàn bộ nội dung
        worksheet[f'G{i}'] = "\n".join(lines)
        
    print(f"   ✅ Hoàn thành điền {len(data)} câu hỏi.")

def populate_image_with_word_sentence_creation(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'Ảnh với từ (img) (HSK4)'.
    Key JSON: image_with_word_sentence_creation
    """
    print(f"   -> Đang điền dữ liệu vào sheet: {worksheet.title}")
    start_row = 2
    for i, question in enumerate(data, start=start_row):
        # Lấy dữ liệu từ JSON
        image_des = question.get('image_description', '')
        vocab = question.get('vocabulary_word', '')
        sample_sentence = question.get('sample_sentence', '') # Đáp án mẫu

        # Xây dựng nội dung cho cột E (Câu hỏi cho người học)
        content_e = f"Ảnh: {image_des}\nTừ vựng: {vocab}"
        
        # Quy tắc đặc biệt: Thêm đề bài chung cho câu đầu tiên
        if i == start_row:
            header = "看图，用词造句。\n\n" # Đề bài: Nhìn hình, dùng từ đặt câu.
            content_e = header + content_e
            
        # Điền dữ liệu vào sheet
        worksheet[f'E{i}'] = content_e
        worksheet[f'H{i}'] = sample_sentence # Cột H giờ là câu trả lời mẫu

    print(f"   ✅ Hoàn thành điền {len(data)} câu hỏi.")

# Hàm cho HSK5
def populate_passage_cloze(worksheet, data: dict):
    """
    Điền dữ liệu cho sheet 'Điền từ đoạn văn (HSK5)'.
    Key JSON: passage_cloze
    """
    print(f"   -> Đang điền dữ liệu vào sheet: {worksheet.title}")
    questions = data.get('questions', [])
    num_questions = len(questions)

    if num_questions == 0:
        print("   ⚠️ Cảnh báo: Không có câu hỏi nào để điền.")
        return

    start_row = 2
    end_row = start_row + num_questions - 1

    # Cột B: Merge ô và điền học liệu
    merge_range = f'B{start_row}:B{end_row}'
    worksheet.merge_cells(merge_range)
    top_left_cell = worksheet[f'B{start_row}']
    top_left_cell.value = data.get('shared_material', '')
    top_left_cell.alignment = Alignment(vertical='top', wrap_text=True)

    # Cột G và H: Điền các bộ phương án và đáp án
    for i, question in enumerate(questions, start=start_row):
        # Cột G: Phương án trả lời
        options = question.get('answer_options', [])
        worksheet[f'G{i}'] = "\n".join(options)
        
        # Cột H: Đáp án
        worksheet[f'H{i}'] = question.get('correct_answer')

    print(f"   ✅ Hoàn thành điền học liệu và {num_questions} câu hỏi.")

def populate_main_idea_comprehension(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'Chọn chủ đề đoạn văn (HSK5)'.
    Key JSON: main_idea_comprehension
    """
    print(f"   -> Đang điền dữ liệu vào sheet: {worksheet.title}")
    start_row = 2
    for i, question in enumerate(data, start=start_row):
        # Cột F: Đoạn văn
        worksheet[f'F{i}'] = question.get('passage_chinese', '')
        
        # Cột G: Các lựa chọn đáp án
        options = question.get('answer_options', [])
        worksheet[f'G{i}'] = "\n".join(options)

        # Cột H: Đáp án đúng
        worksheet[f'H{i}'] = question.get('correct_answer')
        
    print(f"   ✅ Hoàn thành điền {len(data)} câu hỏi.")

def populate_long_passage_comprehension(worksheet, data: dict):
    """
    Điền dữ liệu cho sheet 'TN Đọc hiểu (img) (HSK5)'.
    Key JSON: long_passage_comprehension
    """
    print(f"   -> Đang điền dữ liệu vào sheet: {worksheet.title}")
    questions = data.get('questions', [])
    num_questions = len(questions)

    if num_questions == 0:
        print("   ⚠️ Cảnh báo: Không có câu hỏi nào để điền.")
        return

    start_row = 2
    end_row = start_row + num_questions - 1
    
    # --- Cột B: Merge ô và điền học liệu + mô tả ảnh ---
    passage = data.get('shared_passage', '')
    image_des = data.get('image_description', '')
    
    full_material = f"{passage}\nẢnh : {image_des}"
    
    merge_range = f'B{start_row}:B{end_row}'
    worksheet.merge_cells(merge_range)
    top_left_cell = worksheet[f'B{start_row}']
    top_left_cell.value = full_material
    top_left_cell.alignment = Alignment(vertical='top', wrap_text=True)

    # --- Cột F, G, H: Điền các câu hỏi, phương án, và đáp án ---
    for i, question in enumerate(questions, start=start_row):
        worksheet[f'F{i}'] = question.get('query_chinese', '')
        
        options = question.get('answer_options', [])
        worksheet[f'G{i}'] = "\n".join(options)
        
        worksheet[f'H{i}'] = question.get('correct_answer')

    print(f"   ✅ Hoàn thành điền học liệu và {num_questions} câu hỏi.")

def populate_writing_from_keywords(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'Viết dựa vào từ (HSK5)'.
    Key JSON: writing_from_keywords
    """
    print(f"   -> Đang điền dữ liệu vào sheet: {worksheet.title}")
    start_row = 2
    for i, question in enumerate(data, start=start_row):
        # Lấy dữ liệu
        keywords = question.get('keywords', [])
        paragraph = question.get('sample_paragraph_marked', '')
        translation = question.get('translation', '')
        
        # Cột E: Đề bài và từ khóa
        prompt_text = "请结合下列词语(要全部使用,顺序不分先后),写一篇80字左右的短文。"
        keywords_text = "\t".join(keywords) # Dùng tab để có khoảng cách đẹp
        content_e = f"{prompt_text}\n\n{keywords_text}"
        worksheet[f'E{i}'] = content_e
        
        # Cột I: Đoạn văn mẫu và bản dịch
        content_i = f"{paragraph}\n\nTạm dịch:\n{translation}"
        worksheet[f'I{i}'] = content_i

    print(f"   ✅ Hoàn thành điền {len(data)} câu hỏi.")

def populate_writing_from_image(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'Viết dựa vào ảnh (img) (HSK5)'.
    Key JSON: writing_from_image
    """
    print(f"   -> Đang điền dữ liệu vào sheet: {worksheet.title}")
    start_row = 2
    for i, question in enumerate(data, start=start_row):
        # Lấy dữ liệu
        image_des = question.get('image_description', '')
        paragraph = question.get('sample_paragraph', '')
        translation = question.get('translation', '')

        # Cột E: Đề bài và mô tả ảnh
        prompt_text = "请结合这张图片写一篇80字左右的短文。"
        content_e = f"Ảnh: {image_des}\n{prompt_text}"
        worksheet[f'E{i}'] = content_e

        # Cột I: Đoạn văn mẫu, bản dịch và ghi chú AICham
        content_i = f"{paragraph}\n\nTạm dịch:\n{translation}\nAICham: {image_des}"
        worksheet[f'I{i}'] = content_i

    print(f"   ✅ Hoàn thành điền {len(data)} câu hỏi.")

def populate_topik_word_matching(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'Nối từ với nghĩa'.
    Logic: Giữ nguyên cột tiếng Việt, trộn cột tiếng Hàn, tính toán key nối.
    """
    print(f"   -> Đang điền dữ liệu Nối từ (TOPIK) vào sheet: {worksheet.title}")
    
    start_row = 2
    while worksheet[f'D{start_row}'].value is not None:
        start_row += 1

    for i, question in enumerate(data, start=start_row):
        pairs = question.get('pairs', [])
        if len(pairs) < 4: continue

        # 1. Cột D: NB
        worksheet[f'D{i}'] = "NB"

        # 2. Cột E: Đề bài
        worksheet[f'E{i}'] = "Nối từ với nghĩa tương tự"

        # 3. Xử lý logic trộn đề (Cột G & H)
        # Tách danh sách
        list_vn = [p['vietnamese'] for p in pairs] # [Hàn Quốc, Trung Quốc, Mỹ, Anh]
        list_kr = [p['korean'] for p in pairs]     # [한국, 중국, 미국, 영국]
        
        # Tạo bản sao list_kr để trộn
        list_kr_shuffled = list_kr.copy()
        random.shuffle(list_kr_shuffled) # Ví dụ thành: [중국, 한국, 영국, 미국]

        # Tạo nội dung hiển thị cho Cột G
        # Phần tiếng Việt
        content_vn = "\n".join(list_vn)
        # Phần tiếng Hàn (đã trộn)
        content_kr = "\n".join(list_kr_shuffled)
        
        worksheet[f'G{i}'] = f"{content_vn}\n---\n{content_kr}"

        # Tính toán Đáp án (Cột H) - Format: 12,21,34,43
        # Logic: Tìm xem từ VN ở vị trí k (1-based) nối với từ KR ở vị trí nào trong list đã trộn
        answer_codes = []
        for vn_idx, vn_word in enumerate(list_vn, 1):
            # Tìm từ tiếng Hàn gốc tương ứng với từ VN này
            original_kr_word = pairs[vn_idx-1]['korean']
            
            # Tìm vị trí của từ tiếng Hàn đó trong list đã trộn (1-based)
            kr_shuffled_idx = list_kr_shuffled.index(original_kr_word) + 1
            
            # Tạo mã: Vị trí VN + Vị trí KR (Ví dụ: 12)
            answer_codes.append(f"{vn_idx}{kr_shuffled_idx}")
        
        worksheet[f'H{i}'] = ",".join(answer_codes)

    print(f"   ✅ Hoàn thành điền {len(data)} câu hỏi nối từ.")

def populate_topik_image_matching(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'Nối (img)'.
    Logic: Giữ nguyên thứ tự từ tiếng Hàn, trộn thứ tự mô tả ảnh.
    """
    print(f"   -> Đang điền dữ liệu Nối ảnh (TOPIK) vào sheet: {worksheet.title}")
    
    start_row = 2
    while worksheet[f'G{start_row}'].value is not None:
        start_row += 1

    for i, question in enumerate(data, start=start_row):
        pairs = question.get('pairs', [])
        if len(pairs) < 4: continue

        # 1. Điền các cột định danh
        worksheet[f'C{i}'] = "N"
        worksheet[f'D{i}'] = "NB"
        worksheet[f'E{i}'] = "Nối từ với hình ảnh tương tự"

        # 2. Chuẩn bị dữ liệu
        list_kr = [p['korean'] for p in pairs]           # Từ gốc
        list_desc = [p['image_description'] for p in pairs] # Mô tả ảnh gốc
        
        # 3. Trộn danh sách ẢNH (Mô tả)
        # Tạo bản sao và shuffle
        list_desc_shuffled = list_desc.copy()
        random.shuffle(list_desc_shuffled) 

        # 4. Tạo nội dung Cột G
        # Phần text (Từ vựng)
        content_kr = "\n".join(list_kr)
        # Phần ảnh (Mô tả)
        # Thêm prefix "Ảnh: " hoặc [Image prompt] để dễ nhận diện sau này
        formatted_desc = [f"Ảnh: {desc}" for desc in list_desc_shuffled]
        content_img = "\n".join(formatted_desc)
        
        worksheet[f'G{i}'] = f"{content_kr}\n---\n\n{content_img}"

        # 5. Tính toán Đáp án (Cột H) - Format: 13,24...
        # Logic: Từ ở vị trí k (1-based) nối với Ảnh ở vị trí nào trong list đã trộn?
        answer_codes = []
        for word_idx, word in enumerate(list_kr, 1):
            # Lấy mô tả ảnh đúng của từ này
            correct_desc = pairs[word_idx-1]['image_description']
            
            # Tìm vị trí của mô tả đó trong list ảnh đã trộn (1-based)
            shuffled_img_idx = list_desc_shuffled.index(correct_desc) + 1
            
            # Key = Vị trí Từ + Vị trí Ảnh
            answer_codes.append(f"{word_idx}{shuffled_img_idx}")
        
        worksheet[f'H{i}'] = ",".join(answer_codes)

    print(f"   ✅ Hoàn thành điền {len(data)} câu hỏi nối ảnh.")

def populate_topik_image_selection(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'TN chọn ảnh (img)'.
    Logic: Trộn 4 phương án ảnh, tìm ra vị trí của ảnh đúng.
    """
    print(f"   -> Đang điền dữ liệu TN chọn ảnh (TOPIK) vào sheet: {worksheet.title}")
    
    start_row = 2
    while worksheet[f'F{start_row}'].value is not None:
        start_row += 1

    for i, question in enumerate(data, start=start_row):
        target_word = question.get('target_vietnamese', '')
        options = question.get('options', [])
        
        if len(options) < 4: continue

        # 1. Điền các cột định danh
        worksheet[f'C{i}'] = "TN"
        worksheet[f'D{i}'] = "NB"
        worksheet[f'E{i}'] = "Chọn đáp án đúng"

        # 2. Cột F: Câu hỏi
        # Format: Chọn 'Bưu điện'
        worksheet[f'F{i}'] = f"Chọn '{target_word}'"

        # 3. Xử lý trộn đáp án (Shuffle Options)
        # Lưu ý: Cần shuffle options để đáp án đúng không luôn nằm ở vị trí đầu tiên
        random.shuffle(options)
        
        # 4. Tìm đáp án đúng và Tạo nội dung mô tả ảnh
        correct_index = 0
        img_descriptions = []
        
        for idx, opt in enumerate(options, 1):
            # Thêm mô tả ảnh vào danh sách
            img_descriptions.append("Ảnh: " + opt['image_description'])
            
            # Kiểm tra xem đây có phải đáp án đúng không
            if opt.get('is_correct') is True:
                correct_index = idx

        # 5. Cột G: 4 mô tả ảnh (xuống dòng)
        worksheet[f'G{i}'] = "\n".join(img_descriptions)

        # 6. Cột H: Đáp án đúng (Index 1-4)
        worksheet[f'H{i}'] = correct_index
        
        # LƯU Ý QUAN TRỌNG:
        # Cập nhật lại danh sách options đã trộn vào object data gốc
        # Để lát nữa hàm Renderer lời giải lấy được đúng thứ tự đã trộn (nếu cần)
        question['options'] = options

    print(f"   ✅ Hoàn thành điền {len(data)} câu hỏi TN chọn ảnh.")

def populate_topik_image_to_word(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'Nhìn hình chọn đáp án (img)'.
    Logic:
    - 3 câu đầu: E = "Chọn đáp án đúng"
    - 5 câu sau: E = "Chọn 'Từ tiếng Việt'"
    - Trộn đáp án ở cột G.
    """
    print(f"   -> Đang điền dữ liệu Nhìn hình đoán từ (TOPIK) vào sheet: {worksheet.title}")
    
    start_row = 2
    while worksheet[f'F{start_row}'].value is not None:
        start_row += 1

    # Loop qua dữ liệu với index đếm (idx) bắt đầu từ 0 để check logic 3 câu đầu
    for idx, question in enumerate(data):
        row = start_row + idx # Dòng trong Excel
        
        target_kr = question.get('target_korean', '')
        target_vn = question.get('target_vietnamese', '')
        options = question.get('options', [])
        
        if len(options) < 4: continue

        # 1. Cột C, D
        worksheet[f'C{row}'] = "TN"
        worksheet[f'D{row}'] = "NB"

        # 2. Cột E: Logic phân chia đề bài
        # idx chạy từ 0. Vậy 0, 1, 2 là 3 câu đầu.
        if idx < 3:
            worksheet[f'E{row}'] = "Chọn đáp án đúng"
        else:
            worksheet[f'E{row}'] = f"Chọn '{target_vn}'"

        # 3. Cột F: Mô tả ảnh (của Target Word)
        worksheet[f'F{row}'] = "Ảnh: " + question.get('image_description', '')

        # 4. Trộn đáp án (Shuffle)
        random.shuffle(options)
        
        # 5. Cột G: Danh sách 4 từ tiếng Hàn
        option_koreans = [opt['korean'] for opt in options]
        worksheet[f'G{row}'] = "\n".join(option_koreans)

        # 6. Cột H: Tìm vị trí đáp án đúng
        correct_index = 0
        for i, opt in enumerate(options, 1):
            if opt['korean'] == target_kr:
                correct_index = i
                break
        worksheet[f'H{row}'] = correct_index
        
        # Cập nhật lại options đã trộn vào data gốc để Renderer dùng
        question['options'] = options

    print(f"   ✅ Hoàn thành điền {len(data)} câu hỏi nhìn hình đoán từ.")

def populate_topik_vocab_selection(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'Chọn đáp án đúng'.
    Logic:
    - 2 câu đầu (vn_to_kr): E = Chọn 'Tiếng Việt', G = Tiếng Hàn.
    - 2 câu sau (kr_to_vn): E = Chọn 'Tiếng Hàn', G = Tiếng Việt.
    """
    print(f"   -> Đang điền dữ liệu Chọn từ vựng (TOPIK) vào sheet: {worksheet.title}")
    
    start_row = 2
    while worksheet[f'G{start_row}'].value is not None:
        start_row += 1

    for idx, question in enumerate(data):
        row = start_row + idx
        
        prompt_text = question.get('prompt_text', '')
        options = question.get('options', [])
        
        if len(options) < 4: continue

        # 1. Cột C, D
        worksheet[f'C{row}'] = "TN"
        worksheet[f'D{row}'] = "NB"

        # 2. Cột E: Đề bài "Chọn 'ABC'"
        worksheet[f'E{row}'] = f"Chọn '{prompt_text}'"

        # 3. Trộn đáp án
        random.shuffle(options)
        
        # 4. Cột G: Danh sách các lựa chọn (display_text)
        # Type 1: display_text là tiếng Hàn
        # Type 2: display_text là tiếng Việt
        option_texts = [opt['display_text'] for opt in options]
        worksheet[f'G{row}'] = "\n".join(option_texts)

        # 5. Cột H: Vị trí đáp án đúng
        correct_index = 0
        for i, opt in enumerate(options, 1):
            if opt['is_correct'] is True:
                correct_index = i
                break
        worksheet[f'H{row}'] = correct_index
        
        # Cập nhật options đã trộn vào data gốc
        question['options'] = options

    print(f"   ✅ Hoàn thành điền {len(data)} câu hỏi chọn từ vựng.")

def populate_topik_reading_shared(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'Đọc hiểu (HL)'.
    Data input: List chứa 10 objects bài đọc.
    """
    print(f"   -> Đang điền 40 câu Đọc hiểu chung (TOPIK)...")

    # Tìm dòng bắt đầu
    start_row = 2
    while worksheet[f'G{start_row}'].value is not None:
        start_row += 1
    
    current_row_cursor = start_row

    # VÒNG LẶP CHÍNH: Duyệt qua từng bài đọc (Passage)
    for passage_idx, passage_data in enumerate(data):
        passage_kr = passage_data.get('passage_korean', '')
        questions = passage_data.get('questions', [])
        
        if len(questions) < 4: continue

        # 1. Xử lý Merge Cột B (Học liệu chung)
        # Mỗi bài đọc chiếm 4 dòng
        end_row = current_row_cursor + 3
        worksheet.merge_cells(f'B{current_row_cursor}:B{end_row}')
        
        cell_b = worksheet[f'B{current_row_cursor}']
        cell_b.value = passage_kr
        cell_b.alignment = Alignment(wrap_text=True, vertical='top')

        # 2. Duyệt qua 4 câu hỏi của bài đọc này
        for q_idx, q in enumerate(questions):
            row = current_row_cursor + q_idx
            
            # Cột C, D
            worksheet[f'C{row}'] = "TN"
            worksheet[f'D{row}'] = "NB"

            # Cột E: Câu hỏi
            worksheet[f'E{row}'] = q.get('question_text', '')

            # Cột G: Phương án
            options = q.get('options', [])
            opts_text = "\n".join([opt['korean'] for opt in options])
            worksheet[f'G{row}'] = opts_text

            # Cột H: Đáp án
            worksheet[f'H{row}'] = q.get('correct_index')

            # Lưu lại data cho renderer (Quan trọng cho Pha 2)
            q['shared_passage_translation'] = passage_data.get('passage_vietnamese', '')
            # Lưu full data để renderer dùng
            q['full_passage_data'] = passage_data 

        # Cập nhật con trỏ dòng cho bài đọc tiếp theo
        current_row_cursor += 4

    print(f"   ✅ Hoàn thành điền {len(data)} bài đọc (tổng {len(data)*4} câu).")

def populate_topik_listening_vocab(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'Nghe và chọn đáp án đúng'.
    """
    print(f"   -> Đang điền dữ liệu Nghe từ vựng (TOPIK) vào sheet: {worksheet.title}")
    
    start_row = 2
    while worksheet[f'G{start_row}'].value is not None:
        start_row += 1

    for idx, question in enumerate(data):
        row = start_row + idx
        
        target_kr = question.get('target_korean', '')
        options = question.get('options', [])
        
        if len(options) < 4: continue

        # 1. Cột C, D
        worksheet[f'C{row}'] = "TN"
        worksheet[f'D{row}'] = "NB"

        # 2. Cột E: Chọn 'Từ Hàn'
        worksheet[f'E{row}'] = f"Chọn '{target_kr}'"

        # 3. Cột F: Script nghe (chính là từ tiếng Hàn)
        worksheet[f'F{row}'] = target_kr

        # 4. Trộn đáp án
        random.shuffle(options)
        
        # 5. Cột G: Danh sách 4 nghĩa Tiếng Việt
        option_texts = [opt['vietnamese'] for opt in options]
        worksheet[f'G{row}'] = "\n".join(option_texts)

        # 6. Cột H: Vị trí đáp án đúng
        correct_index = 0
        for i, opt in enumerate(options, 1):
            if opt['is_correct'] is True:
                correct_index = i
                break
        worksheet[f'H{row}'] = correct_index
        
        # Cập nhật options đã trộn vào data gốc cho renderer
        question['options'] = options

    print(f"   ✅ Hoàn thành điền {len(data)} câu hỏi nghe từ vựng.")

def populate_topik_listening_fill(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'Nghe và điền từ thích hợp'.
    """
    print(f"   -> Đang điền dữ liệu Nghe điền từ (TOPIK) vào sheet: {worksheet.title}")
    
    start_row = 2
    while worksheet[f'G{start_row}'].value is not None:
        start_row += 1

    for idx, question in enumerate(data):
        row = start_row + idx
        
        full_sentence = question.get('full_sentence', '')
        target = question.get('target_word', '')
        
        if not full_sentence or not target: continue

        # 1. Cột C, D
        worksheet[f'C{row}'] = "DT"
        worksheet[f'D{row}'] = "NB"

        # 2. Cột E: Đề bài cố định
        worksheet[f'E{row}'] = "Điền từ thích hợp vào chỗ trống"

        # 3. Cột F: Script (Câu đục lỗ)
        # Thay thế từ cần điền bằng ________
        masked_sentence = full_sentence.replace(target, "________")
        worksheet[f'F{row}'] = masked_sentence

        # 4. Cột G: Đáp án (Câu có ngoặc vuông)
        # Thay thế từ cần điền bằng [target]
        answer_sentence = full_sentence.replace(target, f"[{target}]")
        worksheet[f'G{row}'] = answer_sentence

        # Lưu lại data cho renderer dùng
        # (Không cần xử lý cột H vì dạng DT thường ko có đáp án trắc nghiệm số)

    print(f"   ✅ Hoàn thành điền {len(data)} câu nghe điền từ.")

def populate_topik_listening_reorder(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'Nghe và Sắp xếp câu'.
    """
    print(f"   -> Đang điền dữ liệu Sắp xếp câu (TOPIK) vào sheet: {worksheet.title}")
    
    start_row = 2
    while worksheet[f'G{start_row}'].value is not None:
        start_row += 1

    for idx, question in enumerate(data):
        row = start_row + idx
        
        items = question.get('items', [])
        if not items: continue

        # 1. Cột C, D
        worksheet[f'C{row}'] = "XB"
        worksheet[f'D{row}'] = "NB"

        # 2. Cột E: Đề bài
        worksheet[f'E{row}'] = "Sắp xếp các từ sau theo thứ tự đúng"

        # 3. Chuẩn bị dữ liệu
        # Danh sách đúng (Correct List)
        correct_koreans = [item['korean'] for item in items]
        
        # Danh sách trộn (Shuffled List)
        shuffled_items = items.copy()
        random.shuffle(shuffled_items)
        shuffled_koreans = [item['korean'] for item in shuffled_items]

        # 4. Cột F: File nghe (Thứ tự đúng)
        # Format: từ 1, từ 2, từ 3
        worksheet[f'F{row}'] = ", ".join(correct_koreans)

        # 5. Cột G: Đề bài (Thứ tự sai)
        worksheet[f'G{row}'] = ", ".join(shuffled_koreans)

        # 6. Cột H: Đáp án (Key String)
        # Logic: Duyệt qua từng từ trong danh sách ĐÚNG, tìm vị trí của nó trong danh sách SAI
        key_sequence = []
        for word in correct_koreans:
            # Tìm index trong list trộn (cộng 1 để ra số thứ tự 1-based)
            try:
                position = shuffled_koreans.index(word) + 1
                key_sequence.append(str(position))
            except ValueError:
                print(f"Lỗi: Không tìm thấy từ {word} trong danh sách trộn.")
        
        worksheet[f'H{row}'] = "".join(key_sequence)

        # Lưu data gốc để renderer dùng
        question['sorted_items'] = items # List gốc chưa trộn

    print(f"   ✅ Hoàn thành điền {len(data)} câu sắp xếp.")

def populate_topik_listening_shared(worksheet, data: list):
    """
    Điền dữ liệu cho sheet 'Nghe, hiểu (HL)'.
    Input: List 10 objects hội thoại.
    """
    print(f"   -> Đang điền 40 câu Nghe hiểu chung (TOPIK)...")
    
    # Tìm dòng bắt đầu
    start_row = 2
    while worksheet[f'G{start_row}'].value is not None:
        start_row += 1
    
    current_row_cursor = start_row

    # VÒNG LẶP CHÍNH: Duyệt qua 10 đoạn hội thoại
    for dia_idx, item in enumerate(data):
        dialogue = item.get('dialogue', [])
        questions = item.get('questions', [])
        
        if len(questions) < 4: continue

        # 1. Xử lý Cột B (Script chung) - Merge 4 dòng
        # Tạo nội dung Script
        script_header = "Nghe hội thoại sau và chọn X cho câu có nội dung sai, O cho câu có nội dung đúng\nfile nghe:\n\n"
        script_content = ""
        for line in dialogue:
            script_content += f"{line['korean']}\n\n"
        full_script = script_header + script_content.strip()

        end_row = current_row_cursor + 3
        worksheet.merge_cells(f'B{current_row_cursor}:B{end_row}')
        
        cell_b = worksheet[f'B{current_row_cursor}']
        cell_b.value = full_script
        cell_b.alignment = Alignment(wrap_text=True, vertical='top')

        # 2. Duyệt qua 4 câu hỏi con
        for q_idx, q in enumerate(questions):
            row = current_row_cursor + q_idx
            
            # Cột C, D
            worksheet[f'C{row}'] = "TN"
            worksheet[f'D{row}'] = "NB"

            # Cột E: Nhận định
            worksheet[f'E{row}'] = q.get('statement_korean', '')

            # Cột G: X/O
            worksheet[f'G{row}'] = "X\nO"

            # Cột H: Đáp án (1=X, 2=O)
            if q.get('is_correct'):
                worksheet[f'H{row}'] = 2
            else:
                worksheet[f'H{row}'] = 1

            # LƯU DATA CHO RENDERER (Quan trọng)
            q['full_dialogue_data'] = dialogue
            q['explanation_info'] = {
                'statement_vn': q.get('statement_vietnamese'),
                'explanation': q.get('explanation'),
                'evidence': q.get('evidence_korean'),
                'is_correct': q.get('is_correct')
            }

        # Tăng con trỏ dòng cho hội thoại tiếp theo
        current_row_cursor += 4

    print(f"   ✅ Hoàn thành điền {len(data)} đoạn hội thoại (tổng {len(data)*4} câu).")
