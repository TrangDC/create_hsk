# hsk_core/config/hsk_explanation_configs.py

from formatters.explanation_prompt_builder import (
    build_individual_image_matching_prompt,
    build_shared_image_comprehension_prompt,
    build_reading_comprehension_choice_prompt,
    build_image_matching_questions_prompt,
    build_sentence_matching_questions_prompt,
    build_word_fill_in_questions_prompt,
    build_hsk2_true_false_image_prompt,
    build_hsk2_dialogue_comprehension_prompt,
    build_hsk2_true_false_statement_prompt,
    build_hsk2_sentence_matching_inverted_prompt,
    build_hsk3_true_false_listening_choice_prompt,
    build_hsk3_reading_comprehension_no_pinyin_v3_prompt,
    build_hsk3_sentence_reordering_prompt,
    build_hsk3_word_fill_in_display_answer_prompt,
    build_hsk4_listening_comprehension_prompt,
    build_hsk4_sentence_sequence_reordering_prompt,
    build_hsk4_reading_passage_prompt,
    build_hsk4_image_word_sentence_creation_prompt,
    build_hsk5_passage_cloze_prompt,
    build_hsk5_main_idea_comprehension_prompt,
    build_hsk5_long_passage_comprehension_prompt
)

# from formatters.explanation_excel_formatter import (
#     render_individual_img_explanation,
#     render_shared_image_comprehension_explanation,
#     render_reading_comp_explanation,
#     render_image_matching_explanation,
#     render_sentence_matching_explanation,
#     render_word_fill_explanation,
#     render_hsk2_true_false_image_explanation,
#     render_hsk2_dialogue_comprehension_explanation,
#     render_hsk2_true_false_statement_explanation,
#     render_hsk2_sentence_matching_inverted_explanation,
#     render_hsk3_true_false_listening_choice_explanation,
#     render_hsk3_reading_comprehension_no_pinyin_v3_explanation_with_markers,
#     render_hsk3_sentence_reordering_explanation,
#     render_hsk4_listening_comprehension_explanation,
#     render_hsk4_sentence_sequence_reordering_explanation,
#     render_hsk4_reading_passage_explanation,
#     render_hsk4_image_word_sentence_creation_explanation,
#     render_hsk5_passage_cloze_explanation,
#     render_hsk5_main_idea_comprehension_explanation,
#     render_hsk5_long_passage_comprehension_explanation,
#     render_hsk5_writing_from_keywords, 
#     render_hsk5_writing_from_image
# )

HSK1_EXPLANATION_CONFIGS = {
    "individual_image_matching": {
        "prompt_file": "hsk1_individual_img_explanation_prompt.txt",
        "schema_path": "hsk1_individual_img_explanation_schema.json",
        "builder": build_individual_image_matching_prompt,
        "sheet_name": "TN PA đúng (img) (HSK1)",
        "renderer": render_individual_img_explanation
    },
    "shared_image_comprehension": {
        "prompt_file": "hsk1_shared_img_explanation_prompt.txt",
        "schema_path": "hsk1_shared_img_explanation_schema.json",
        "builder": build_shared_image_comprehension_prompt,
        "sheet_name": "TN PA đúng (img) (HL) (HSK1)",
        "renderer": render_shared_image_comprehension_explanation
    },
    "reading_comprehension_choice": {
        "prompt_file": "hsk1_reading_comp_explanation_prompt.txt",
        "schema_path": "hsk1_reading_comp_explanation_schema.json",
        "builder": build_reading_comprehension_choice_prompt,
        "sheet_name": "TN PA đúng (HSK1)",
        "renderer": render_reading_comp_explanation
    },
    "image_matching_questions": {
        "prompt_file": "hsk1_img_match_explanation_prompt.txt",
        "schema_path": "hsk1_img_match_explanation_schema.json",
        "builder": build_image_matching_questions_prompt,
        "sheet_name": "TN chọn ảnh (img) (HL) (HSK1)",
        "renderer": render_image_matching_explanation
    },
    "sentence_matching_questions": {
        "prompt_file": "hsk1_sentence_match_explanation_prompt.txt",
        "schema_path": "hsk1_sentence_match_explanation_schema.json",
        "builder": build_sentence_matching_questions_prompt,
        "sheet_name": "TN câu trả lời đúng (HL) (HSK1)",
        "renderer": render_sentence_matching_explanation
    },
    "word_fill_in_questions": {
        "prompt_file": "hsk1_word_fill_explanation_prompt.txt",
        "schema_path": "hsk1_word_fill_explanation_schema.json",
        "builder": build_word_fill_in_questions_prompt,
        "sheet_name": "TN chọn từ đúng (HL) (HSK1)",
        "renderer": render_word_fill_explanation
    }
}

HSK2_EXPLANATION_CONFIGS = {
    "true_false_image_questions": {
        "prompt_file": "hsk2_true_false_image_prompt.txt",
        "schema_path": "hsk2_true_false_image_schema.json",
        "builder": build_hsk2_true_false_image_prompt,
        "sheet_name": "Đúng sai (img) (HSK2)",
        "renderer": render_hsk2_true_false_image_explanation
    },
    "shared_image_comprehension": {
        "prompt_file": "hsk2_shared_img_explanation_prompt.txt",
        "schema_path": "hsk2_shared_img_explanation_schema.json",
        "builder": build_shared_image_comprehension_prompt,
        "sheet_name": "TN PA đúng (img) (HL) (HSK2)",
        "renderer": render_shared_image_comprehension_explanation
    },
    "reading_comprehension_dialogue_2_lines": {
        "prompt_file": "hsk2_dialogue_comprehension_prompt.txt",
        "schema_path": "hsk2_dialogue_comprehension_schema.json",
        "builder": build_hsk2_dialogue_comprehension_prompt,
        "sheet_name": "TN PA đúng (HSK2)",
        "renderer": render_hsk2_dialogue_comprehension_explanation
    },
    "reading_comprehension_dialogue_4_lines": {
        "prompt_file": "hsk2_dialogue_comprehension_prompt.txt",
        "schema_path": "hsk2_dialogue_comprehension_schema.json",
        "builder": build_hsk2_dialogue_comprehension_prompt,
        "sheet_name": "TN PA đúng_v2 (HSK2)",
        "renderer": render_hsk2_dialogue_comprehension_explanation
    },
    "image_matching_questions": {
        "prompt_file": "hsk1_img_match_explanation_prompt.txt",
        "schema_path": "hsk1_img_match_explanation_schema.json",
        "builder": build_image_matching_questions_prompt,
        "sheet_name": "TN chọn ảnh (img) (HL) (HSK2)",
        "renderer": render_image_matching_explanation
    },
    "word_fill_in_questions": {
        "prompt_file": "hsk1_word_fill_explanation_prompt.txt",
        "schema_path": "hsk1_word_fill_explanation_schema.json",
        "builder": build_word_fill_in_questions_prompt,
        "sheet_name": "TN chọn từ đúng (HL) (HSK2)",
        "renderer": render_word_fill_explanation
    },
    "true_false_statement_questions": {
        "prompt_file": "hsk2_true_false_statement_prompt.txt",
        "schema_path": "hsk2_true_false_statement_schema.json",
        "builder": build_hsk2_true_false_statement_prompt,
        "sheet_name": "ĐS lựa chọn (HSK2)",
        "renderer": render_hsk2_true_false_statement_explanation
    },
    "sentence_matching_inverted_questions": {
        "prompt_file": "hsk2_sentence_matching_inverted_prompt.txt",
        "schema_path": "hsk2_sentence_matching_inverted_schema.json",
        "builder": build_hsk2_sentence_matching_inverted_prompt,
        "sheet_name": "TN câu trả lời đúng (HL) (HSK2)",
        "renderer": render_hsk2_sentence_matching_inverted_explanation
    }
}

HSK3_EXPLANATION_CONFIGS={
    "shared_image_comprehension": {
        "prompt_file": "hsk2_shared_img_explanation_prompt.txt",
        "schema_path": "hsk2_shared_img_explanation_schema.json",
        "builder": build_shared_image_comprehension_prompt,
        "sheet_name": "TN PA đúng (img) (HL) (HSK3)",
        "renderer": render_shared_image_comprehension_explanation
    },
    "true_false_listening_choice": {
        "prompt_file": "hsk3_true_false_listening_choice_prompt.txt",
        "schema_path": "hsk3_true_false_listening_choice_schema.json",
        "builder": build_hsk3_true_false_listening_choice_prompt,
        "sheet_name": "ĐS nghe chọn (HSK3)",
        "renderer": render_hsk3_true_false_listening_choice_explanation
    },
    "reading_comprehension_dialogue_2_lines": {
        "prompt_file": "hsk2_dialogue_comprehension_prompt.txt",
        "schema_path": "hsk2_dialogue_comprehension_schema.json",
        "builder": build_hsk2_dialogue_comprehension_prompt,
        "sheet_name": "TN PA đúng ko pinyin (HSK3)",
        "renderer": render_hsk2_dialogue_comprehension_explanation
    },
    "reading_comprehension_dialogue_4_lines": {
        "prompt_file": "hsk2_dialogue_comprehension_prompt.txt",
        "schema_path": "hsk2_dialogue_comprehension_schema.json",
        "builder": build_hsk2_dialogue_comprehension_prompt,
        "sheet_name": "TN PA đúng ko pinyin_v2 (HSK3)",
        "renderer": render_hsk2_dialogue_comprehension_explanation
    },
    "sentence_matching_inverted_questions": {
        "prompt_file": "hsk2_sentence_matching_inverted_prompt.txt",
        "schema_path": "hsk2_sentence_matching_inverted_schema.json",
        "builder": build_hsk2_sentence_matching_inverted_prompt,
        "sheet_name": "TN câu trả lời đúng (HL) (HSK3)",
        "renderer": render_hsk2_sentence_matching_inverted_explanation
    },
    "word_fill_in_questions": {
        "prompt_file": "hsk1_word_fill_explanation_prompt.txt",
        "schema_path": "hsk1_word_fill_explanation_schema.json",
        "builder": build_word_fill_in_questions_prompt,
        "sheet_name": "TN chọn từ đúng (HL) (HSK3)",
        "renderer": render_word_fill_explanation
    },
    "reading_comprehension_no_pinyin_v3": {
        "prompt_file": "hsk3_reading_comprehension_no_pinyin_v3_prompt.txt",
        "schema_path": "hsk3_reading_comprehension_no_pinyin_v3_schema.json",
        "builder": build_hsk3_reading_comprehension_no_pinyin_v3_prompt,
        "sheet_name": "TN PA đúng ko pinyin_v3 (HSK3)",
        "renderer": render_hsk3_reading_comprehension_no_pinyin_v3_explanation_with_markers
    },
    "sentence_reordering": {
        "prompt_file": "hsk3_sentence_reordering_prompt.txt",
        "schema_path": "hsk3_sentence_reordering_schema.json",
        "builder": build_hsk3_sentence_reordering_prompt,
        "sheet_name": "Sắp xếp câu (HSK3)",
        "renderer": render_hsk3_sentence_reordering_explanation
    },
    "word_fill_in_display_answer": {
        "prompt_file": "hsk3_word_fill_in_display_answer_prompt.txt",
        "schema_path": "hsk3_word_fill_in_display_answer_schema.json",
        "builder": build_hsk3_word_fill_in_display_answer_prompt,
        "sheet_name": "Điền từ đúng (HSK3)",
        "renderer": render_word_fill_explanation
    }
}

HSK4_EXPLANATION_CONFIGS={
    "true_false_listening_choice": {
        "prompt_file": "hsk3_true_false_listening_choice_prompt.txt",
        "schema_path": "hsk3_true_false_listening_choice_schema.json",
        "builder": build_hsk3_true_false_listening_choice_prompt,
        "sheet_name": "ĐS nghe chọn (HSK4)",
        "renderer": render_hsk3_true_false_listening_choice_explanation
    },
    "reading_comprehension_dialogue_2_lines": {
        "prompt_file": "hsk2_dialogue_comprehension_prompt.txt",
        "schema_path": "hsk2_dialogue_comprehension_schema.json",
        "builder": build_hsk2_dialogue_comprehension_prompt,
        "sheet_name": "TN PA đúng (HSK4)",
        "renderer": render_hsk2_dialogue_comprehension_explanation
    },
    "reading_comprehension_dialogue_4_lines": {
        "prompt_file": "hsk2_dialogue_comprehension_prompt.txt",
        "schema_path": "hsk2_dialogue_comprehension_schema.json",
        "builder": build_hsk2_dialogue_comprehension_prompt,
        "sheet_name": "TN PA đúng_v2 (HSK4)",
        "renderer": render_hsk2_dialogue_comprehension_explanation
    },
    "listening_comprehension": {
        "prompt_file": "hsk4_listening_comprehension.txt",
        "schema_path": "hsk4_listening_comprehension_schema.json",
        "builder": build_hsk4_listening_comprehension_prompt,
        "sheet_name": "TN Nghe hiểu (HSK4)",
        "renderer": render_hsk4_listening_comprehension_explanation
    },
    "word_fill_in_questions": {
        "prompt_file": "hsk1_word_fill_explanation_prompt.txt",
        "schema_path": "hsk1_word_fill_explanation_schema.json",
        "builder": build_word_fill_in_questions_prompt,
        "sheet_name": "TN chọn từ đúng (HL) (HSK4)",
        "renderer": render_word_fill_explanation
    },
    "sentence_sequence_reordering": {
        "prompt_file": "hsk4_sentence_sequence_reordering.txt",
        "schema_path": "hsk4_sentence_sequence_reordering_schema.json",
        "builder": build_hsk4_sentence_sequence_reordering_prompt,
        "sheet_name": "Sắp xếp các câu (HSK4)", # Tên sheet này cần khớp với file Excel template
        "renderer": render_hsk4_sentence_sequence_reordering_explanation
    },
    "reading_comprehension_no_pinyin_v3": {
        "prompt_file": "hsk3_reading_comprehension_no_pinyin_v3_prompt.txt",
        "schema_path": "hsk3_reading_comprehension_no_pinyin_v3_schema.json",
        "builder": build_hsk3_reading_comprehension_no_pinyin_v3_prompt,
        "sheet_name": "TN PA đúng ko pinyin_v3 (HSK4)",
        "renderer": render_hsk3_reading_comprehension_no_pinyin_v3_explanation_with_markers
    },
    "reading_comprehension_short_passage": {
        "prompt_file": "hsk4_reading_short_passage.txt",
        "schema_path": "hsk4_reading_short_passage_schema.json",
        "builder": build_hsk4_reading_passage_prompt,
        "sheet_name": "TN Đọc hiểu ngắn (HSK4)", # Cần khớp với file Excel
        "renderer": render_hsk4_reading_passage_explanation
    },
    "sentence_reordering": {
        "prompt_file": "hsk3_sentence_reordering_prompt.txt",
        "schema_path": "hsk3_sentence_reordering_schema.json",
        "builder": build_hsk3_sentence_reordering_prompt,
        "sheet_name": "Sắp xếp câu (HSK4)",
        "renderer": render_hsk3_sentence_reordering_explanation
    },
    "image_with_word_sentence_creation": {
        "prompt_file": "hsk4_image_with_word_sentence_creation.txt",
        "schema_path": "hsk4_image_with_word_sentence_creation_schema.json",
        "builder": build_hsk4_image_word_sentence_creation_prompt,
        "sheet_name": "Ảnh với từ (img) (HSK4)", # Cần khớp với file Excel
        "renderer": render_hsk4_image_word_sentence_creation_explanation
    }
}

HSK5_EXPLANATION_CONFIGS={
    "reading_comprehension_dialogue_2_lines": {
        "prompt_file": "hsk2_dialogue_comprehension_prompt.txt",
        "schema_path": "hsk2_dialogue_comprehension_schema.json",
        "builder": build_hsk2_dialogue_comprehension_prompt,
        "sheet_name": "TN PA đúng (HSK5)",
        "renderer": render_hsk2_dialogue_comprehension_explanation
    },
    "reading_comprehension_dialogue_4_lines": {
        "prompt_file": "hsk2_dialogue_comprehension_prompt.txt",
        "schema_path": "hsk2_dialogue_comprehension_schema.json",
        "builder": build_hsk2_dialogue_comprehension_prompt,
        "sheet_name": "TN PA đúng_v2 (HSK5)",
        "renderer": render_hsk2_dialogue_comprehension_explanation
    },
    "listening_comprehension": {
        "prompt_file": "hsk4_listening_comprehension.txt",
        "schema_path": "hsk4_listening_comprehension_schema.json",
        "builder": build_hsk4_listening_comprehension_prompt,
        "sheet_name": "TN Nghe hiểu (HSK5)",
        "renderer": render_hsk4_listening_comprehension_explanation
    },
    "passage_cloze": {
        "prompt_file": "hsk5_passage_cloze.txt",
        "schema_path": "hsk5_passage_cloze_schema.json",
        "builder": build_hsk5_passage_cloze_prompt,
        "sheet_name": "Điền từ đoạn văn (HSK5)",
        "renderer": render_hsk5_passage_cloze_explanation
    },
    "main_idea_comprehension": {
        "prompt_file": "hsk5_main_idea_comprehension.txt",
        "schema_path": "hsk5_main_idea_comprehension_schema.json",
        "builder": build_hsk5_main_idea_comprehension_prompt,
        "sheet_name": "Chọn chủ đề đoạn văn (HSK5)",
        "renderer": render_hsk5_main_idea_comprehension_explanation
    },
    "long_passage_comprehension": {
        "prompt_file": "hsk5_long_passage_comprehension.txt",
        "schema_path": "hsk5_long_passage_comprehension_schema.json",
        "builder": build_hsk5_long_passage_comprehension_prompt,
        "sheet_name": "TN Đọc hiểu (img) (HSK5)",
        "renderer": render_hsk5_long_passage_comprehension_explanation
    },
    "sentence_reordering": {
        "prompt_file": "hsk3_sentence_reordering_prompt.txt",
        "schema_path": "hsk3_sentence_reordering_schema.json",
        "builder": build_hsk3_sentence_reordering_prompt,
        "sheet_name": "Sắp xếp câu (HSK5)",
        "renderer": render_hsk3_sentence_reordering_explanation
    },
    "writing_from_keywords": {
        "sheet_name": "Viết dựa vào từ (HSK5)",
        "renderer": render_hsk5_writing_from_keywords
    },
    "writing_from_image": {
        "sheet_name": "Viết dựa vào ảnh (img) (HSK5)",
        "renderer": render_hsk5_writing_from_image
    },
}


def get_explanation_config(level: str):
    configs = {
        "hsk1": HSK1_EXPLANATION_CONFIGS,
        "hsk2": HSK2_EXPLANATION_CONFIGS,
        "hsk3": HSK3_EXPLANATION_CONFIGS,
        "hsk4": HSK4_EXPLANATION_CONFIGS,
        "hsk5": HSK5_EXPLANATION_CONFIGS,
    }
    return configs.get(level.lower())