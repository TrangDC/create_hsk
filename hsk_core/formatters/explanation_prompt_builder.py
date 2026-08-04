# hsk_core/formatters/explanation_prompt_builder.py

# Mỗi hàm nhận vào task và prompt_template, trả về chuỗi prompt đã được format.

def build_individual_image_matching_prompt(task: dict, prompt_template: str) -> str:
    q_data = task['data']
    image_options = q_data.get('image_options', [])
    options_list_str = "\n".join(f"{idx + 1}. {desc}" for idx, desc in enumerate(image_options))
    correct_num = q_data.get('correct_answer', 0)
    correct_desc = image_options[correct_num - 1] if 0 < correct_num <= len(image_options) else "N/A"
    return prompt_template.format(
        script_chinese=q_data.get('script_chinese', ''),
        script_pinyin=q_data.get('script_pinyin', ''),
        image_options_list=options_list_str,
        correct_answer_number=correct_num,
        correct_answer_description=correct_desc
    )

def build_shared_image_comprehension_prompt(task: dict, prompt_template: str) -> str:
    q_data = task['data']
    shared_material = task.get('shared_material', [])
    material_list_str = "\n".join(f"{idx + 1}. {desc}" for idx, desc in enumerate(shared_material))
    correct_num = q_data.get('correct_answer', 0)
    correct_desc = shared_material[correct_num - 1] if 0 < correct_num <= len(shared_material) else "N/A"
    return prompt_template.format(
            shared_material_list=material_list_str,
            script_chinese=q_data.get('script_chinese', ''),
            script_pinyin=q_data.get('script_pinyin', ''),
            correct_answer_number=correct_num,
            correct_answer_description=correct_desc
    )

def build_reading_comprehension_choice_prompt(task: dict, prompt_template: str) -> str:
    q_data = task['data']
    options = q_data.get('answer_options', [])
    options_str = "\n".join(f"{chr(65+i)}. {opt.get('chinese_text', '')}" for i, opt in enumerate(options))
    
    correct_num = q_data.get('correct_answer', 0)
    correct_letter = chr(64 + correct_num) if correct_num > 0 else 'N/A'

    return prompt_template.format(
        context_chinese=q_data.get('context_chinese', ''),
        query_chinese=q_data.get('query_chinese', ''),
        options_list_str=options_str,
        correct_answer_letter=correct_letter
    )

def build_image_matching_questions_prompt(task: dict, prompt_template: str) -> str:
    q_data = task['data']
    shared_material = task.get('shared_material', [])
    material_list_str = "\n".join(f"{chr(65+idx)}. {desc}" for idx, desc in enumerate(shared_material)) # Dùng A, B, C...

    correct_num = q_data.get('correct_answer', 0)
    correct_desc = shared_material[correct_num - 1] if 0 < correct_num <= len(shared_material) else "N/A"

    return prompt_template.format(
    shared_material_list=material_list_str,
    question_chinese=q_data.get('question_text_chinese', ''),
    question_pinyin=q_data.get('pinyin', ''),
    correct_answer_number=chr(64 + correct_num), # Chuyển số thành chữ cái A, B, C...
    correct_answer_description=correct_desc
    )

def build_sentence_matching_questions_prompt(task: dict, prompt_template: str) -> str:
    q_data = task['data']
    shared_material = task.get('shared_material', [])
    # Định dạng học liệu chung cho prompt
    material_list_str = "\n".join(
        f"{item.get('option_letter')}. {item.get('chinese_text')} ({item.get('pinyin')})" 
        for item in shared_material
    )

    correct_letter = q_data.get('correct_answer', '')
    # Tìm câu trả lời đúng trong học liệu chung
    correct_sentence_obj = next((item for item in shared_material if item.get('option_letter') == correct_letter), None)
    correct_sentence_str = correct_sentence_obj.get('chinese_text', 'N/A') if correct_sentence_obj else 'N/A'
    
    return prompt_template.format(
        shared_material_list=material_list_str,
        question_chinese=q_data.get('question_text_chinese', ''),
        question_pinyin=q_data.get('pinyin', ''),
        correct_answer_letter=correct_letter,
        correct_answer_sentence=correct_sentence_str
    )

def build_word_fill_in_questions_prompt(task: dict, prompt_template: str) -> str:
    q_data = task['data']
    shared_material = task.get('shared_material', [])
    material_list_str = "\n".join(
        f"{item.get('option_letter')}. {item.get('chinese_word')} ({item.get('pinyin')})"
        for item in shared_material
    )
    question_context_lines = [
        f"__{line.get('speaker', '')}__：{line.get('chinese_text', '')}" if line.get('speaker') else line.get('chinese_text', '')
        for line in q_data.get('lines', [])
    ]
    question_context_str = "\n".join(question_context_lines)
    print("--- DEBUG: question_context_str ---\n\n")
    print(question_context_str)
    print("--- DEBUG END: question_context_str ---\n\n")
    correct_letter = q_data.get('correct_answer', '')
    correct_word_obj = next((item for item in shared_material if item.get('option_letter') == correct_letter), None)
    correct_word_str = correct_word_obj.get('chinese_word', 'N/A') if correct_word_obj else 'N/A'
    return prompt_template.format(
        shared_material_list=material_list_str,
        question_context_str=question_context_str,
        correct_answer_letter=correct_letter,
        correct_answer_word_chinese=correct_word_str
    )

def build_hsk2_true_false_image_prompt(task: dict, prompt_template: str) -> str:
    """
    Xây dựng prompt động cho dạng câu hỏi Đúng/Sai dựa trên hình ảnh của HSK2.
    """
    q_data = task.get('data', {})
    
    # Chuyển đổi đáp án từ số (1/0) sang chữ ("Đúng"/"Sai")
    correct_answer_num = q_data.get('correct_answer')
    answer_text = "Đúng" if correct_answer_num == 1 else "Sai"
    
    # Điền thông tin vào template
    return prompt_template.format(
        image_description=q_data.get('image_des', ''),
        script_chinese=q_data.get('script', ''),
        script_pinyin=q_data.get('pinyin', ''),
        script_translation=q_data.get('translation', ''),
        correct_answer_text=answer_text
    )

def build_hsk2_dialogue_comprehension_prompt(task: dict, prompt_template: str) -> str:
    """
    Xây dựng prompt động chung cho các dạng câu hỏi hội thoại HSK2 (2 và 4 lượt lời).
    """
    q_data = task.get('data', {})
    
    # 1. Định dạng chuỗi hội thoại cho prompt
    dialogue_lines = []
    for turn in q_data.get('dialogue', []):
        speaker = turn.get('speaker', '')
        line = turn.get('line_chinese', '')
        dialogue_lines.append(f"{speaker}: {line}")
    dialogue_str = "\n".join(dialogue_lines)

    # 2. Định dạng chuỗi các lựa chọn cho prompt
    options_lines = []
    options = q_data.get('answer_options', [])
    for i, opt in enumerate(options):
        letter = chr(65 + i) # A, B, C
        chinese_text = opt.get('chinese_text', '')
        options_lines.append(f"{letter}. {chinese_text}")
    options_list_str = "\n".join(options_lines)
    
    # 3. Chuyển đổi đáp án từ số (1, 2, 3) sang chữ (A, B, C)
    correct_answer_num = q_data.get('correct_answer')
    correct_answer_letter = chr(64 + correct_answer_num) if correct_answer_num in [1, 2, 3] else "N/A"

    # 4. Điền thông tin vào template
    return prompt_template.format(
        dialogue_str=dialogue_str,
        query_chinese=q_data.get('query_chinese', ''),
        options_list_str=options_list_str,
        correct_answer_letter=correct_answer_letter
    )

def build_hsk2_true_false_statement_prompt(task: dict, prompt_template: str) -> str:
    """
    Xây dựng prompt động cho dạng câu hỏi Đúng/Sai từ nhận định của HSK2.
    """
    q_data = task.get('data', {})
    
    # Chuyển đổi đáp án từ số (1/0) sang chữ ("Đúng"/"Sai")
    correct_answer_num = q_data.get('correct_answer')
    answer_text = "Đúng" if correct_answer_num == 1 else "Sai"
    
    # Điền thông tin vào template
    return prompt_template.format(
        script_chinese=q_data.get('script_chinese', ''),
        statement_chinese=q_data.get('statement_chinese', ''),
        correct_answer_text=answer_text
    )

def build_hsk2_sentence_matching_inverted_prompt(task: dict, prompt_template: str) -> str:
    """
    Xây dựng prompt động cho dạng câu hỏi ghép cặp câu trả lời của HSK2.
    """
    q_data = task.get('data', {})
    shared_material = task.get('shared_material', [])
    
    # 1. Định dạng học liệu chung cho prompt
    material_lines = []
    for item in shared_material:
        letter = item.get('option_letter', '')
        chinese = item.get('chinese_text', '')
        material_lines.append(f"{letter}. {chinese}")
    shared_material_str = "\n".join(material_lines)

    # 2. Tìm câu thoại đúng trong học liệu chung
    correct_letter = q_data.get('correct_answer', '')
    correct_statement_obj = next((item for item in shared_material if item.get('option_letter') == correct_letter), None)
    correct_statement_chinese = correct_statement_obj.get('chinese_text', 'N/A') if correct_statement_obj else 'N/A'
    
    # 3. Điền thông tin vào template
    return prompt_template.format(
        shared_material_str=shared_material_str,
        question_chinese=q_data.get('question_text_chinese', ''),
        correct_answer_letter=correct_letter,
        correct_answer_chinese=correct_statement_chinese
    )

def build_hsk3_true_false_listening_choice_prompt(task: dict, prompt_template: str) -> str:
    """
    Xây dựng prompt động cho dạng câu hỏi Đúng/Sai nghe chọn của HSK3.
    """
    q_data = task.get('data', {})
    
    # Chuyển đổi đáp án từ số (1/0) sang chữ ("Đúng"/"Sai")
    correct_answer_num = q_data.get('correct_answer')
    answer_text = "Đúng" if correct_answer_num == 1 else "Sai"
    
    # Điền thông tin vào template
    return prompt_template.format(
        script_chinese=q_data.get('script_chinese', ''),
        statement_chinese=q_data.get('statement_chinese', ''),
        correct_answer_text=answer_text
    )

def build_hsk3_reading_comprehension_no_pinyin_v3_prompt(task: dict, prompt_template: str) -> str:
    """
    Xây dựng prompt động cho dạng đọc hiểu không pinyin V3 của HSK3.
    """
    q_data = task.get('data', {})
    
    # 1. Định dạng chuỗi các lựa chọn cho prompt
    options_lines = []
    options = q_data.get('answer_options', [])
    for i, opt_chinese in enumerate(options):
        letter = chr(65 + i) # A, B, C
        options_lines.append(f"{letter}. {opt_chinese}")
    options_list_str = "\n".join(options_lines)
    
    # 2. Chuyển đổi đáp án từ số (1, 2, 3) sang chữ (A, B, C)
    correct_answer_num = q_data.get('correct_answer')
    correct_answer_letter = chr(64 + correct_answer_num) if correct_answer_num in [1, 2, 3] else "N/A"

    # 3. Điền thông tin vào template
    return prompt_template.format(
        script_chinese=q_data.get('script_chinese', ''),
        query_chinese=q_data.get('query_chinese', ''),
        options_list_str=options_list_str,
        correct_answer_letter=correct_answer_letter
    )

def build_hsk3_sentence_reordering_prompt(task: dict, prompt_template: str) -> str:
    """
    Xây dựng prompt động cho dạng câu hỏi sắp xếp thành phần câu của HSK3.
    """
    q_data = task.get('data', {})
    components = q_data.get('components', [])
    correct_order_str = q_data.get('correct_order', '')
    
    # 1. Định dạng chuỗi các thành phần cho prompt
    components_lines = []
    for i, comp in enumerate(components):
        components_lines.append(f"{i+1}. {comp}")
    components_str = "\n".join(components_lines)
    
    # 2. Tái tạo lại câu hoàn chỉnh từ các thành phần và thứ tự
    correct_sentence_parts = []
    if components and correct_order_str.isdigit():
        for order_char in correct_order_str:
            index = int(order_char) - 1
            if 0 <= index < len(components):
                correct_sentence_parts.append(components[index])
    correct_sentence_chinese = "".join(correct_sentence_parts)
    
    # 3. Điền thông tin vào template
    return prompt_template.format(
        components_str=components_str,
        correct_order_str=correct_order_str,
        correct_sentence_chinese=correct_sentence_chinese
    )

def build_hsk3_word_fill_in_display_answer_prompt(task: dict, prompt_template: str) -> str:
    """
    Xây dựng prompt động cho dạng câu hỏi điền từ đúng của HSK3.
    """
    q_data = task.get('data', {})
    
    part1 = q_data.get('sentence_part_1', '')
    word = q_data.get('correct_word', '')
    part2 = q_data.get('sentence_part_2', '')
    
    # Tái tạo lại câu hoàn chỉnh
    full_sentence_chinese = f"{part1}{word}{part2}"
    
    # Điền thông tin vào template
    return prompt_template.format(
        sentence_part_1=part1,
        sentence_part_2=part2,
        correct_word=word,
        correct_word_pinyin=q_data.get('correct_word_pinyin', ''),
        full_sentence_chinese=full_sentence_chinese
    )

def build_hsk4_listening_comprehension_prompt(task: dict, prompt_template: str) -> str:
    """
    Xây dựng prompt động cho dạng nghe hiểu HSK4, xử lý theo cụm học liệu.
    """
    material_block = task.get('data', {})
    script_chinese = material_block.get('script_chinese', '')
    questions = material_block.get('questions', [])

    # Đảm bảo có đúng 2 câu hỏi để xử lý
    if len(questions) != 2:
        # Trả về chuỗi rỗng hoặc log lỗi nếu dữ liệu không hợp lệ
        print(f"Cảnh báo: Dữ liệu nghe hiểu không chứa 2 câu hỏi. Bỏ qua.")
        return "" 
        
    q1_data = questions[0]
    q2_data = questions[1]

    # --- Xử lý cho Câu hỏi 1 ---
    options_1 = q1_data.get('answer_options', [])
    options_list_1 = "\n".join(f"{chr(65+i)}. {opt}" for i, opt in enumerate(options_1))
    correct_num_1 = q1_data.get('correct_answer', 0)
    correct_letter_1 = chr(64 + correct_num_1)
    correct_text_1 = options_1[correct_num_1 - 1] if 0 < correct_num_1 <= len(options_1) else 'N/A'

    # --- Xử lý cho Câu hỏi 2 ---
    options_2 = q2_data.get('answer_options', [])
    options_list_2 = "\n".join(f"{chr(65+i)}. {opt}" for i, opt in enumerate(options_2))
    correct_num_2 = q2_data.get('correct_answer', 0)
    correct_letter_2 = chr(64 + correct_num_2)
    correct_text_2 = options_2[correct_num_2 - 1] if 0 < correct_num_2 <= len(options_2) else 'N/A'
    
    # --- Điền vào template ---
    return prompt_template.format(
        script_chinese=script_chinese,
        query_chinese_1=q1_data.get('query_chinese', ''),
        options_list_1=options_list_1,
        correct_answer_letter_1=correct_letter_1,
        correct_answer_text_1=correct_text_1,
        query_chinese_2=q2_data.get('query_chinese', ''),
        options_list_2=options_list_2,
        correct_answer_letter_2=correct_letter_2,
        correct_answer_text_2=correct_text_2
    )

def build_hsk4_sentence_sequence_reordering_prompt(task: dict, prompt_template: str) -> str:
    """
    Xây dựng prompt động cho dạng sắp xếp 3 câu văn của HSK4.
    """
    q_data = task.get('data', {})
    components = q_data.get('components', [])
    correct_order = q_data.get('correct_order', '') # vd: "BCA"
    
    # 1. Định dạng chuỗi các thành phần
    components_str_lines = []
    component_map = {comp['label']: comp['text'] for comp in components}
    for comp in components:
        components_str_lines.append(f"- Câu {comp['label']}: {comp['text']}")
    components_str = "\n".join(components_str_lines)

    # 2. Tái tạo lại đoạn văn hoàn chỉnh
    full_passage_parts = []
    for letter in correct_order:
        if letter in component_map:
            full_passage_parts.append(component_map[letter])
    full_passage_chinese = " ".join(full_passage_parts)
    
    # 3. Điền vào template
    return prompt_template.format(
        components_str=components_str,
        correct_order=correct_order,
        full_passage_chinese=full_passage_chinese
    )

def build_hsk4_reading_passage_prompt(task: dict, prompt_template: str) -> str:
    """
    Xây dựng prompt động cho dạng đọc hiểu ngắn HSK4, xử lý theo cụm học liệu.
    """
    material_block = task.get('data', {})
    script_chinese = material_block.get('script_chinese', '') # Đổi tên biến
    questions = material_block.get('questions', [])
    
    if len(questions) != 2:
        print(f"Cảnh báo: Dữ liệu đọc hiểu ngắn không chứa 2 câu hỏi. Bỏ qua.")
        return "" 
        
    q1_data, q2_data = questions[0], questions[1]

    # Xử lý cho Câu hỏi 1
    options_1 = q1_data.get('answer_options', [])
    options_list_1 = "\n".join(f"{chr(65+i)}. {opt}" for i, opt in enumerate(options_1))
    correct_num_1 = q1_data.get('correct_answer', 0)
    correct_letter_1 = chr(64 + correct_num_1)
    correct_text_1 = options_1[correct_num_1 - 1] if 0 < correct_num_1 <= len(options_1) else 'N/A'

    # Xử lý cho Câu hỏi 2
    options_2 = q2_data.get('answer_options', [])
    options_list_2 = "\n".join(f"{chr(65+i)}. {opt}" for i, opt in enumerate(options_2))
    correct_num_2 = q2_data.get('correct_answer', 0)
    correct_letter_2 = chr(64 + correct_num_2)
    correct_text_2 = options_2[correct_num_2 - 1] if 0 < correct_num_2 <= len(options_2) else 'N/A'
    
    return prompt_template.format(
        script_chinese=script_chinese, # Đổi tiên biến
        query_chinese_1=q1_data.get('query_chinese', ''),
        options_list_1=options_list_1,
        correct_answer_letter_1=correct_letter_1,
        correct_answer_text_1=correct_text_1,
        query_chinese_2=q2_data.get('query_chinese', ''),
        options_list_2=options_list_2,
        correct_answer_letter_2=correct_letter_2,
        correct_answer_text_2=correct_text_2
    )

def build_hsk4_image_word_sentence_creation_prompt(task: dict, prompt_template: str) -> str:
    """
    Xây dựng prompt động cho lời giải của dạng Đặt câu với ảnh và từ HSK4.
    """
    q_data = task.get('data', {})
    
    return prompt_template.format(
        image_description=q_data.get('image_description', ''),
        vocabulary_word=q_data.get('vocabulary_word', ''),
        sample_sentence=q_data.get('sample_sentence', '')
    )

def build_hsk5_passage_cloze_prompt(task: dict, prompt_template: str) -> str:
    """
    Xây dựng prompt động cho dạng điền từ đoạn văn HSK5, xử lý theo cụm.
    """
    passage_block = task.get('data', {})
    passage_with_blanks = passage_block.get('shared_material', '')
    questions = passage_block.get('questions', [])
    
    if len(questions) != 4:
        print("Cảnh báo: Dữ liệu điền từ HSK5 không chứa 4 câu hỏi. Bỏ qua.")
        return ""

    # 1. Tạo chuỗi tóm tắt lựa chọn và đáp án
    choices_and_answers_lines = []
    correct_words = []
    for i, q in enumerate(questions):
        options = q.get('answer_options', [])
        correct_num = q.get('correct_answer', 0)
        correct_word = options[correct_num - 1] if 0 < correct_num <= len(options) else 'N/A'
        correct_words.append(correct_word)
        
        choices_and_answers_lines.append(f"- Chỗ trống {i+1}:")
        for j, opt in enumerate(options):
            choices_and_answers_lines.append(f"  {chr(65+j)}. {opt}")
        choices_and_answers_lines.append(f"  -> Đáp án đúng: {correct_word}")
    choices_and_answers_str = "\n".join(choices_and_answers_lines)
    
    # 2. Tái tạo đoạn văn hoàn chỉnh
    full_passage_chinese = passage_with_blanks
    for word in correct_words:
        full_passage_chinese = full_passage_chinese.replace('________', word, 1)

    # 3. Điền vào template
    return prompt_template.format(
        passage_with_blanks=passage_with_blanks,
        choices_and_answers_str=choices_and_answers_str,
        full_passage_chinese=full_passage_chinese
    )

def build_hsk5_main_idea_comprehension_prompt(task: dict, prompt_template: str) -> str:
    """
    Xây dựng prompt động cho dạng chọn chủ đề đoạn văn HSK5.
    """
    q_data = task.get('data', {})
    
    # 1. Định dạng chuỗi các lựa chọn
    options = q_data.get('answer_options', [])
    options_str = "\n".join(f"{chr(65+i)}. {opt}" for i, opt in enumerate(options))
    
    # 2. Tìm nội dung text của đáp án đúng
    correct_num = q_data.get('correct_answer', 0)
    correct_letter = chr(64 + correct_num) if 0 < correct_num <= len(options) else 'N/A'
    correct_text = options[correct_num - 1] if 0 < correct_num <= len(options) else 'N/A'
    
    # 3. Điền vào template
    return prompt_template.format(
        passage_chinese=q_data.get('passage_chinese', ''),
        options_list_str=options_str,
        correct_answer_letter=correct_letter,
        correct_answer_text=correct_text
    )

def build_hsk5_long_passage_comprehension_prompt(task: dict, prompt_template: str) -> str:
    """
    Xây dựng prompt động cho dạng đọc hiểu đoạn văn dài HSK5, xử lý theo cụm.
    """
    passage_block = task.get('data', {})
    passage_chinese = passage_block.get('shared_passage', '')
    questions = passage_block.get('questions', [])
    
    if len(questions) != 4:
        print("Cảnh báo: Dữ liệu đọc hiểu dài HSK5 không chứa 4 câu hỏi. Bỏ qua.")
        return ""

    # Tạo chuỗi tóm tắt các câu hỏi, lựa chọn và đáp án
    summary_lines = []
    for i, q in enumerate(questions):
        summary_lines.append(f"--- Câu hỏi {i+1} ---")
        summary_lines.append(f"Câu hỏi: {q.get('query_chinese', '')}")
        options = q.get('answer_options', [])
        summary_lines.append("Các lựa chọn:")
        for j, opt in enumerate(options):
            summary_lines.append(f"  {chr(65+j)}. {opt}")
        correct_num = q.get('correct_answer', 0)
        correct_word = options[correct_num - 1] if 0 < correct_num <= len(options) else 'N/A'
        summary_lines.append(f"-> Đáp án đúng: {chr(64+correct_num)}. {correct_word}")
    questions_summary_str = "\n".join(summary_lines)
    
    # Điền vào template
    return prompt_template.format(
        passage_chinese=passage_chinese,
        questions_summary_str=questions_summary_str
    )


