from docx import Document
from services.callAPI import VertexClient
from docx.shared import Inches
from io import BytesIO
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt
import mimetypes
import os
import json


def response2docx(file_path, prompt, file_name, project_id, creds, model_name):
    client = VertexClient(project_id, creds, model_name)

    with open(file_path, "rb") as f:
        pdf_data = f.read()
    mime_type = mimetypes.guess_type(file_path)[0] or "application/pdf"
    
    # Đọc Schema JSON
    schema_path = "resources/schema/summary_schema.json"
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Không tìm thấy file schema tại {schema_path}")
        
    with open(schema_path, 'r', encoding='utf-8') as f:
        response_schema = json.load(f)

    # Gửi yêu cầu với JSON Schema
    AIresponse_text = client.send_data_to_AI(
        prompt,
        data=pdf_data, 
        mime_type=mime_type,
        response_mime_type="application/json",
        response_schema=response_schema
    )
    print("Đã nhận phản hồi từ AI (JSON).")
    
    # Parse JSON
    try:
        data = json.loads(AIresponse_text)
    except json.JSONDecodeError as e:
        print(f"Lỗi phân tích JSON: {e}")
        print("Phản hồi thô:", AIresponse_text)
        raise ValueError("AI không trả về JSON hợp lệ.")
    
    doc = Document()
    
    # 1. Phần Mở đầu
    if "document_title_cn" in data and "document_title_vn" in data:
        p_title = doc.add_paragraph()
        run_title = p_title.add_run(f"Tóm tắt Bài học – {data['document_title_cn']} ({data['document_title_vn']})")
        run_title.bold = True
        
    if "lesson_summary" in data:
        doc.add_paragraph(data['lesson_summary'])
        doc.add_paragraph() # Dòng trống
        
    # 2. Phần Từ mới
    if data.get("vocabulary_list"):
        p_vocab_title = doc.add_paragraph()
        run_vocab_title = p_vocab_title.add_run("I. Từ Mới")
        run_vocab_title.bold = True
        
        for idx, vocab in enumerate(data['vocabulary_list'], 1):
            p = doc.add_paragraph()
            p.add_run(f"{idx}.  ") # Text thường
            
            run_hanzi = p.add_run(vocab.get('hanzi', ''))
            run_hanzi.bold = True # In đậm chữ Hán
            
            p.add_run(f" /{vocab.get('pinyin', '')}/ ({vocab.get('type', '')}): {vocab.get('meaning', '')}")
            
        doc.add_paragraph() # Dòng trống

    # 3. Phần Nội dung bài khóa
    if data.get("lessons"):
        p_lesson_title = doc.add_paragraph()
        run_lesson_title = p_lesson_title.add_run("II. Nội dung bài khóa")
        run_lesson_title.bold = True
        
        for idx, lesson in enumerate(data['lessons'], 1):
            p_lesson_name = doc.add_paragraph()
            run_lesson_name = p_lesson_name.add_run(f"Bài khóa {idx}")
            run_lesson_name.bold = True
            
            # Tiếng Trung
            if lesson.get('content_cn'):
                for line in lesson['content_cn'].split('\n'):
                    if line.strip():
                        doc.add_paragraph(line.strip())
            
            # Tiếng Việt (In nghiêng)
            if lesson.get('content_vn'):
                for line in lesson['content_vn'].split('\n'):
                    if line.strip():
                        p_vn = doc.add_paragraph()
                        run_vn = p_vn.add_run(line.strip())
                        run_vn.italic = True
            
            # Lưu ý quan trọng
            notes = lesson.get('important_notes', [])
            if notes:
                p_note_title = doc.add_paragraph()
                p_note_title.add_run("* ").bold = False
                run_note_title = p_note_title.add_run("Lưu ý quan trọng:")
                run_note_title.bold = True
                
                for note in notes:
                    p_note = doc.add_paragraph()
                    p_note.add_run("-   ")
                    
                    run_note_cn = p_note.add_run(note.get('hanzi_pinyin', ''))
                    run_note_cn.bold = True
                    
                    p_note.add_run(f": {note.get('explanation', '')}")
                    
            doc.add_paragraph() # Dòng trống giữa các bài khóa

    output_dir = "output/summary"
    os.makedirs(output_dir, exist_ok=True)
    doc.save(os.path.join(output_dir, f"{file_name}.docx"))
    print(f"Đã lưu file Word tại: {output_dir}/{file_name}.docx")