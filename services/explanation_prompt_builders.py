# services/explanation_prompt_builders.py

# Mỗi hàm nhận vào task và prompt_template, trả về chuỗi prompt đã được format.

def build_script_hinh_anh_prompt(task: dict, prompt_template: str) -> str:
    q_data = task['data']
    answer_text = "Đúng" if q_data.get('correct_answer') == 1 else "Sai"
    return prompt_template.format(
        image_description=q_data.get('image_des', ''),
        script_chinese=q_data.get('script', ''),
        script_pinyin=q_data.get('pinyin', ''),
        script_translation=q_data.get('translation', ''),
        correct_answer_text=answer_text
    )

def build_tuvung_hinh_anh_prompt(task: dict, prompt_template: str) -> str:
    q_data = task['data']
    answer_text = "Đúng" if q_data.get('correct_answer') == 1 else "Sai"
    return prompt_template.format(
        image_description=q_data.get('image_des', ''),
        word_chinese=q_data.get('script', ''),
        word_pinyin=q_data.get('pinyin', ''),
        word_translation=q_data.get('translation', ''),
        correct_answer_text=answer_text
    )

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
    correct_letter = q_data.get('correct_answer', '')
    correct_word_obj = next((item for item in shared_material if item.get('option_letter') == correct_letter), None)
    correct_word_str = correct_word_obj.get('chinese_word', 'N/A') if correct_word_obj else 'N/A'
    return prompt_template.format(
        shared_material_list=material_list_str,
        question_context_str=question_context_str,
        correct_answer_letter=correct_letter,
        correct_answer_word_chinese=correct_word_str
    )