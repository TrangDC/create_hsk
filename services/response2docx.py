from docx import Document
from services.callAPI import VertexClient
from docx.shared import Inches
from io import BytesIO
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt
import mimetypes
import os


def response2docx(file_path, prompt, file_name, project_id, creds, model_name):
    client = VertexClient(project_id, creds, model_name)

    with open(file_path, "rb") as f:
        pdf_data = f.read()
    mime_type = mimetypes.guess_type(file_path)[0] or "application/pdf"
    AIresponse = AIresponse = client.send_data_to_AI(prompt,data=pdf_data, mime_type=mime_type)
    print("Đã nhận phản hồi từ AI.")
    
    doc = Document()
    parts = AIresponse.split("\n")
    
    for part in parts:
        part = part.strip()
        print(f"Đang xử lí: {part}")
        
        if "Hình ảnh:" in part:
            paragraph = doc.add_paragraph()
            # Xử lý hình ảnh
            if "**" in part:
                # Tách các phần văn bản để xử lý in đậm
                current_text = part
                while "**" in current_text:
                    # Tìm vị trí ** đầu tiên
                    start_bold = current_text.find("**")
                    end_bold = current_text.find("**", start_bold + 2)
                    
                    if start_bold == -1 or end_bold == -1:
                        paragraph.add_run(current_text)
                        break
                    
                    # Thêm phần văn bản trước ** (nếu có)
                    if start_bold > 0:
                        paragraph.add_run(current_text[:start_bold])
                    
                    # Thêm phần in đậm
                    bold_text = current_text[start_bold + 2:end_bold]
                    run = paragraph.add_run(bold_text)
                    run.bold = True
                    
                    # Cập nhật chuỗi còn lại
                    current_text = current_text[end_bold + 2:]
                
                # Thêm phần văn bản còn lại sau ** cuối cùng
                if current_text:
                    paragraph.add_run(current_text)

        elif part.startswith("### "):
            heading_text = part.replace("### ", "").strip()
            paragraph = doc.add_heading(heading_text, level=3)
            print("Đã thêm heading.")

        elif part.startswith("## "):
            # Xử lý heading
            heading_text = part.replace("## ", "").strip()
            paragraph = doc.add_heading(heading_text, level=2)
            print("Đã thêm heading.")
        
        elif part.startswith("# "):
            heading_text = part.replace("# ", "").strip()
            paragraph = doc.add_heading(heading_text, level=1)
            print("Đã thêm heading.")
        
        else:
            # Xử lý văn bản thông thường và in đậm
            paragraph = doc.add_paragraph()
            if "**" in part:
                # Tách các phần văn bản để xử lý in đậm
                current_text = part
                while "**" in current_text:
                    # Tìm vị trí ** đầu tiên
                    start_bold = current_text.find("**")
                    end_bold = current_text.find("**", start_bold + 2)
                    
                    if start_bold == -1 or end_bold == -1:
                        paragraph.add_run(current_text)
                        break
                    
                    # Thêm phần văn bản trước ** (nếu có)
                    if start_bold > 0:
                        paragraph.add_run(current_text[:start_bold])
                    
                    # Thêm phần in đậm
                    bold_text = current_text[start_bold + 2:end_bold]
                    run = paragraph.add_run(bold_text)
                    run.bold = True
                    
                    # Cập nhật chuỗi còn lại
                    current_text = current_text[end_bold + 2:]
                
                # Thêm phần văn bản còn lại sau ** cuối cùng
                if current_text:
                    paragraph.add_run(current_text)
            else:
                # Thêm văn bản bình thường
                paragraph.add_run(part)

    doc.save(f"output/summary/{file_name}.docx")