# process.py
from PyQt5.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QLabel, QListWidget, QFileDialog, QMessageBox, QSplitter, QProgressBar
)
import os
import sys
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from services.response2docx import response2docx
from services.CompressPDF import compress_pdf_ghostscript

def resource_path(relative_path):
    """Lấy đường dẫn tuyệt đối đến file resource khi chạy bằng PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)
class ProcessingThread(QThread):
    """Luồng xử lý PDF trong nền."""
    progress = pyqtSignal(str)  # Tín hiệu để cập nhật giao diện với thông báo tiến độ
    error = pyqtSignal(str)     # Tín hiệu để báo lỗi
    finished = pyqtSignal(list) # Tín hiệu để gửi danh sách file DOCX đã tạo

    def __init__(self, pdf_file, prompt_path, project_id, creds):
        super().__init__()
        self.pdf_file = pdf_file
        self.prompt_path = prompt_path
        self.project_id = project_id
        self.creds = creds
        
    def run(self):
        generated_files = []
        try:
            os.makedirs("output", exist_ok=True)
            # Đọc các file prompt
            with open(resource_path(self.prompt_path), 'r', encoding='utf-8') as f:
                prompt_gen_answer = f.read()

            pdf_path = self.pdf_file
            file_name = os.path.splitext(os.path.basename(pdf_path))[0]

            self.progress.emit(f"Nén PDF: {pdf_path}")
            compressed_pdf_path = f"output/{file_name}_compressed.pdf"
            compress_pdf_ghostscript(pdf_path, compressed_pdf_path, 'ebook')
            if not os.path.exists(compressed_pdf_path):
                self.progress.emit(f"Đã nén PDF thất bại {compressed_pdf_path}")
                return
            
            self.progress.emit(f"Đang xử lý: {compressed_pdf_path}")
            docx_path = f"output/summary/{file_name}.docx"
            response2docx(compressed_pdf_path, prompt_gen_answer, file_name, self.project_id , self.creds, "gpt-5.4")
            generated_files.append(docx_path)
        except Exception as e:
            self.error.emit(f"Lỗi trong quá trình xử lý: {str(e)}")
        self.finished.emit(generated_files)