import sys
import os
import traceback
from dotenv import load_dotenv

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QComboBox, QPlainTextEdit, QFileDialog, QMessageBox,
    QTabWidget
)
from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QFont
from processor import run_full_pipeline
from image_generator import process_excel_file
from merge_image import ImageMerger  

# Lớp để chuyển hướng stdout sang GUI
class StreamRedirector(QObject):
    stringWritten = pyqtSignal(str)

    def write(self, text):
        self.stringWritten.emit(str(text))

    def flush(self):
        pass

# Lớp Worker để chạy pipeline trong một luồng riêng
class PipelineWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, pdf_folder, hsk_level):
        super().__init__()
        self.pdf_folder = pdf_folder
        self.hsk_level = hsk_level

    def run(self):
        try:
            result_path = run_full_pipeline(self.pdf_folder, self.hsk_level)
            if result_path:
                self.finished.emit(result_path)
            else:
                self.error.emit("Pipeline đã chạy xong nhưng không trả về kết quả thành công. Vui lòng kiểm tra log.")
        except Exception:
            error_details = traceback.format_exc()
            self.error.emit(error_details)

# Lớp Worker để tạo ảnh trong một luồng riêng
class ImageGeneratorWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, excel_path):
        super().__init__()
        self.excel_path = excel_path

    def run(self):
        try:
            result_path = process_excel_file(self.excel_path)
            if result_path:
                self.finished.emit(result_path)
            else:
                self.error.emit("Quá trình tạo ảnh không thành công. Vui lòng kiểm tra log.")
        except Exception:
            error_details = traceback.format_exc()
            self.error.emit(error_details)

# Lớp Worker để ghép ảnh trong một luồng riêng
class ImageMergerWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, excel_path, images_folder, output_folder="IMAGES_MERGED"):
        super().__init__()
        self.excel_path = excel_path
        self.images_folder = images_folder
        self.output_folder = output_folder

    def run(self):
        try:
            merger = ImageMerger(self.excel_path, self.images_folder, self.output_folder)
            merger.process_all()
            result_path = os.path.abspath(self.output_folder)
            self.finished.emit(result_path)
        except Exception:
            error_details = traceback.format_exc()
            self.error.emit(error_details)

# Lớp Giao diện chính với Tab
class HSKGeneratorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.redirect_stdout()
        self.setup_styles()

    def initUI(self):
        self.setWindowTitle('HSK Auto-Generator Pipeline')
        self.setGeometry(200, 200, 900, 700)

        # Layout chính
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Tạo TabWidget
        self.tab_widget = QTabWidget()
        
        # Tab 1: Pipeline HSK
        self.pipeline_tab = self.create_pipeline_tab()
        self.tab_widget.addTab(self.pipeline_tab, "HSK Pipeline")
        
        # Tab 2: Tạo ảnh
        self.image_tab = self.create_image_tab()
        self.tab_widget.addTab(self.image_tab, "Tạo ảnh AI")

        # Tab 3: Ghép ảnh
        self.merge_tab = self.create_merge_tab()
        self.tab_widget.addTab(self.merge_tab, "Ghép ảnh AI")

        main_layout.addWidget(self.tab_widget)
        self.setLayout(main_layout)

    def setup_styles(self):
        """Thiết lập style chung cho ứng dụng"""
        # Font chính cho toàn bộ ứng dụng
        font = QFont("Arial", 11)
        self.setFont(font)
        
        # Style cho toàn bộ ứng dụng
        app_style = """
        QWidget {
            background-color: #f5f5f5;
            color: #333333;
            font-size: 11pt;
        }
        
        QTabWidget::pane {
            border: 2px solid #c0c0c0;
            border-radius: 10px;
            background-color: white;
        }
        
        QTabWidget::tab-bar {
            left: 5px;
        }
        
        QTabBar::tab {
            background-color: #e1e1e1;
            color: #333333;
            border: 2px solid #c0c0c0;
            border-bottom-color: #C2C7CB;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            min-width: 120px;
            padding: 10px 20px;
            font-size: 12pt;
            font-weight: bold;
        }
        
        QTabBar::tab:selected {
            background-color: white;
            border-color: #0078d4;
            border-bottom-color: white;
            color: #0078d4;
        }
        
        QTabBar::tab:hover {
            background-color: #f0f0f0;
        }
        
        QLabel {
            color: #333333;
            font-size: 12pt;
            font-weight: bold;
        }
        
        QLineEdit {
            padding: 8px 12px;
            border: 2px solid #cccccc;
            border-radius: 8px;
            background-color: white;
            font-size: 11pt;
            min-height: 20px;
        }
        
        QLineEdit:focus {
            border-color: #0078d4;
        }
        
        QComboBox {
            padding: 8px 12px;
            border: 2px solid #cccccc;
            border-radius: 8px;
            background-color: white;
            font-size: 11pt;
            min-height: 20px;
        }
        
        QComboBox:focus {
            border-color: #0078d4;
        }
        
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 25px;
            border-left-width: 1px;
            border-left-color: #cccccc;
            border-left-style: solid;
            border-top-right-radius: 6px;
            border-bottom-right-radius: 6px;
        }
        
        QPushButton {
            background-color: #0078d4;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 12px 24px;
            font-size: 12pt;
            font-weight: bold;
            min-height: 25px;
        }
        
        QPushButton:hover {
            background-color: #106ebe;
        }
        
        QPushButton:pressed {
            background-color: #005a9e;
        }
        
        QPushButton:disabled {
            background-color: #cccccc;
            color: #666666;
        }
        
        QPlainTextEdit {
            background-color: #fafafa;
            color: #333333;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 10pt;
            border: 2px solid #ddd;
            border-radius: 8px;
            padding: 10px;
        }
        """
        
        self.setStyleSheet(app_style)

    def create_pipeline_tab(self):
        """Tạo tab cho HSK Pipeline (chức năng cũ)."""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # 1. Phần chọn thư mục
        path_layout = QHBoxLayout()
        path_layout.setSpacing(15)
        self.path_label = QLabel('Thư mục PDF:')
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Chọn thư mục chứa các file PDF...")
        self.browse_button = QPushButton('Duyệt...')
        self.browse_button.setStyleSheet("background-color: #28a745; min-width: 100px;")
        self.browse_button.clicked.connect(self._browse_folder)
        path_layout.addWidget(self.path_label, 0)
        path_layout.addWidget(self.path_input, 1)
        path_layout.addWidget(self.browse_button, 0)
        layout.addLayout(path_layout)

        # 2. Phần chọn HSK Level
        hsk_layout = QHBoxLayout()
        hsk_layout.setSpacing(15)
        self.hsk_label = QLabel('Cấp độ HSK:')
        self.hsk_combo = QComboBox()
        self.hsk_combo.addItems([f'hsk{i}' for i in range(1, 6)])
        self.hsk_combo.setMinimumWidth(150)
        hsk_layout.addWidget(self.hsk_label, 0)
        hsk_layout.addWidget(self.hsk_combo, 0)
        hsk_layout.addStretch(1)
        layout.addLayout(hsk_layout)
        
        # 3. Nút chạy
        self.run_button = QPushButton('🚀 Bắt đầu chạy Pipeline')
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                font-size: 14pt;
                padding: 15px 30px;
                min-height: 35px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        self.run_button.clicked.connect(self._start_pipeline)
        layout.addWidget(self.run_button)

        # 4. Khung hiển thị log
        log_label = QLabel('📋 Nhật ký hoạt động:')
        layout.addWidget(log_label)
        
        self.log_display = QPlainTextEdit()
        self.log_display.setReadOnly(True)
        layout.addWidget(self.log_display)

        tab.setLayout(layout)
        return tab

    def create_image_tab(self):
        """Tạo tab cho chức năng tạo ảnh AI."""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # 1. Phần chọn file Excel
        excel_layout = QHBoxLayout()
        excel_layout.setSpacing(15)
        self.excel_label = QLabel('File Excel:')
        self.excel_input = QLineEdit()
        self.excel_input.setPlaceholderText("Chọn file Excel chứa dữ liệu...")
        self.browse_excel_button = QPushButton('Duyệt...')
        self.browse_excel_button.setStyleSheet("background-color: #28a745; min-width: 100px;")
        self.browse_excel_button.clicked.connect(self._browse_excel_file)
        excel_layout.addWidget(self.excel_label, 0)
        excel_layout.addWidget(self.excel_input, 1)
        excel_layout.addWidget(self.browse_excel_button, 0)
        layout.addLayout(excel_layout)

        # 2. Nút tạo ảnh
        self.generate_button = QPushButton('🎨 Bắt đầu tạo ảnh AI')
        self.generate_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                font-size: 14pt;
                padding: 15px 30px;
                min-height: 35px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.generate_button.clicked.connect(self._start_image_generation)
        layout.addWidget(self.generate_button)

        # 3. Khung hiển thị log cho tab ảnh
        image_log_label = QLabel('📋 Nhật ký tạo ảnh:')
        layout.addWidget(image_log_label)
        
        self.image_log_display = QPlainTextEdit()
        self.image_log_display.setReadOnly(True)
        layout.addWidget(self.image_log_display)

        tab.setLayout(layout)
        return tab

    def create_merge_tab(self):
        """Tạo tab cho chức năng ghép ảnh AI."""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # 1. Phần chọn file Excel
        excel_merge_layout = QHBoxLayout()
        excel_merge_layout.setSpacing(15)
        self.excel_merge_label = QLabel('File Excel:')
        self.excel_merge_input = QLineEdit()
        self.excel_merge_input.setPlaceholderText("Chọn file Excel chứa thông tin ghép...")
        self.browse_excel_merge_button = QPushButton('Duyệt...')
        self.browse_excel_merge_button.setStyleSheet("background-color: #28a745; min-width: 100px;")
        self.browse_excel_merge_button.clicked.connect(self._browse_excel_merge_file)
        excel_merge_layout.addWidget(self.excel_merge_label, 0)
        excel_merge_layout.addWidget(self.excel_merge_input, 1)
        excel_merge_layout.addWidget(self.browse_excel_merge_button, 0)
        layout.addLayout(excel_merge_layout)

        # 2. Phần chọn thư mục ảnh
        images_layout = QHBoxLayout()
        images_layout.setSpacing(15)
        self.images_label = QLabel('Thư mục ảnh:')
        self.images_input = QLineEdit()
        self.images_input.setPlaceholderText("Chọn thư mục chứa ảnh cần ghép...")
        self.browse_images_button = QPushButton('Duyệt...')
        self.browse_images_button.setStyleSheet("background-color: #28a745; min-width: 100px;")
        self.browse_images_button.clicked.connect(self._browse_images_folder)
        images_layout.addWidget(self.images_label, 0)
        images_layout.addWidget(self.images_input, 1)
        images_layout.addWidget(self.browse_images_button, 0)
        layout.addLayout(images_layout)

        # 3. Nút ghép ảnh
        self.merge_button = QPushButton('🔄 Bắt đầu ghép ảnh AI')
        self.merge_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                font-size: 14pt;
                padding: 15px 30px;
                min-height: 35px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.merge_button.clicked.connect(self._start_image_merge)
        layout.addWidget(self.merge_button)

        # 4. Khung hiển thị log cho tab ghép ảnh
        merge_log_label = QLabel('📋 Nhật ký ghép ảnh:')
        layout.addWidget(merge_log_label)
        
        self.merge_log_display = QPlainTextEdit()
        self.merge_log_display.setReadOnly(True)
        layout.addWidget(self.merge_log_display)

        tab.setLayout(layout)
        return tab

    def redirect_stdout(self):
        """Chuyển hướng tất cả output từ print() vào khung log."""
        self.stream_redirector = StreamRedirector()
        self.stream_redirector.stringWritten.connect(self._update_log)
        sys.stdout = self.stream_redirector

    def _update_log(self, text):
        """Cập nhật văn bản vào khung log hiện tại và tự động cuộn xuống."""
        current_tab_index = self.tab_widget.currentIndex()
        
        if current_tab_index == 0:  # Tab Pipeline
            self.log_display.insertPlainText(text)
            self.log_display.verticalScrollBar().setValue(self.log_display.verticalScrollBar().maximum())
        elif current_tab_index == 1:  # Tab Image
            self.image_log_display.insertPlainText(text)
            self.image_log_display.verticalScrollBar().setValue(self.image_log_display.verticalScrollBar().maximum())
        elif current_tab_index == 2:  # Tab Merge
            self.merge_log_display.insertPlainText(text)
            self.merge_log_display.verticalScrollBar().setValue(self.merge_log_display.verticalScrollBar().maximum())

    def _browse_folder(self):
        """Mở dialog để chọn thư mục."""
        folder_path = QFileDialog.getExistingDirectory(self, 'Chọn thư mục chứa file PDF')
        if folder_path:
            self.path_input.setText(folder_path)

    def _browse_excel_file(self):
        """Mở dialog để chọn file Excel."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            'Chọn file Excel', 
            '', 
            'Excel Files (*.xlsx *.xls)'
        )
        if file_path:
            self.excel_input.setText(file_path)

    def _browse_excel_merge_file(self):
        """Mở dialog để chọn file Excel cho ghép ảnh."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            'Chọn file Excel cho ghép ảnh', 
            '', 
            'Excel Files (*.xlsx *.xls)'
        )
        if file_path:
            self.excel_merge_input.setText(file_path)

    def _browse_images_folder(self):
        """Mở dialog để chọn thư mục ảnh."""
        folder_path = QFileDialog.getExistingDirectory(self, 'Chọn thư mục chứa ảnh cần ghép')
        if folder_path:
            self.images_input.setText(folder_path)

    def _start_pipeline(self):
        """Bắt đầu chạy pipeline trong một luồng riêng."""
        pdf_folder = self.path_input.text()
        hsk_level = self.hsk_combo.currentText()

        if not pdf_folder or not os.path.isdir(pdf_folder):
            QMessageBox.warning(self, 'Lỗi đầu vào', 'Vui lòng chọn một thư mục PDF hợp lệ.')
            return

        # Vô hiệu hóa nút chạy và xóa log cũ
        self.run_button.setEnabled(False)
        self.run_button.setText('⏳ Đang xử lý...')
        self.log_display.clear()
        
        # Tạo và khởi chạy thread
        self.thread = QThread()
        self.worker = PipelineWorker(pdf_folder, hsk_level)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._pipeline_finished)
        self.worker.error.connect(self._pipeline_error)

        # Dọn dẹp sau khi thread kết thúc
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def _start_image_generation(self):
        """Bắt đầu tạo ảnh trong một luồng riêng."""
        excel_path = self.excel_input.text()

        if not excel_path or not os.path.isfile(excel_path):
            QMessageBox.warning(self, 'Lỗi đầu vào', 'Vui lòng chọn một file Excel hợp lệ.')
            return

        # Load .env file
        load_dotenv()

        # Kiểm tra credentials
        if not os.getenv("PROJECT_ID"):
            QMessageBox.warning(self, 'Lỗi cấu hình', 'Không tìm thấy thông tin credentials trong file .env.')
            return

        # Vô hiệu hóa nút tạo ảnh và xóa log cũ
        self.generate_button.setEnabled(False)
        self.generate_button.setText('⏳ Đang tạo ảnh...')
        self.image_log_display.clear()
        
        # Tạo và khởi chạy thread
        self.image_thread = QThread()
        self.image_worker = ImageGeneratorWorker(excel_path)
        self.image_worker.moveToThread(self.image_thread)

        self.image_thread.started.connect(self.image_worker.run)
        self.image_worker.finished.connect(self._image_generation_finished)
        self.image_worker.error.connect(self._image_generation_error)

        # Dọn dẹp sau khi thread kết thúc
        self.image_worker.finished.connect(self.image_thread.quit)
        self.image_worker.finished.connect(self.image_worker.deleteLater)
        self.image_thread.finished.connect(self.image_thread.deleteLater)

        self.image_thread.start()

    def _start_image_merge(self):
        """Bắt đầu ghép ảnh trong một luồng riêng."""
        excel_path = self.excel_merge_input.text()
        images_folder = self.images_input.text()

        if not excel_path or not os.path.isfile(excel_path):
            QMessageBox.warning(self, 'Lỗi đầu vào', 'Vui lòng chọn một file Excel hợp lệ.')
            return

        if not images_folder or not os.path.isdir(images_folder):
            QMessageBox.warning(self, 'Lỗi đầu vào', 'Vui lòng chọn một thư mục ảnh hợp lệ.')
            return

        # Vô hiệu hóa nút ghép ảnh và xóa log cũ
        self.merge_button.setEnabled(False)
        self.merge_button.setText('⏳ Đang ghép ảnh...')
        self.merge_log_display.clear()
        
        # Tạo và khởi chạy thread
        self.merge_thread = QThread()
        self.merge_worker = ImageMergerWorker(excel_path, images_folder)
        self.merge_worker.moveToThread(self.merge_thread)

        self.merge_thread.started.connect(self.merge_worker.run)
        self.merge_worker.finished.connect(self._image_merge_finished)
        self.merge_worker.error.connect(self._image_merge_error)

        # Dọn dẹp sau khi thread kết thúc
        self.merge_worker.finished.connect(self.merge_thread.quit)
        self.merge_worker.finished.connect(self.merge_worker.deleteLater)
        self.merge_thread.finished.connect(self.merge_thread.deleteLater)

        self.merge_thread.start()

    def _pipeline_finished(self, result_path):
        """Xử lý khi pipeline chạy thành công."""
        self.run_button.setEnabled(True)
        self.run_button.setText('🚀 Bắt đầu chạy Pipeline')
        QMessageBox.information(self, '✅ Hoàn thành', f'Pipeline đã chạy thành công!\n\nKết quả được lưu tại:\n{os.path.abspath(result_path)}')

    def _pipeline_error(self, error_message):
        """Xử lý khi pipeline gặp lỗi."""
        self.run_button.setEnabled(True)
        self.run_button.setText('🚀 Bắt đầu chạy Pipeline')
        QMessageBox.critical(self, '❌ Lỗi Pipeline', f'Đã xảy ra lỗi trong quá trình chạy:\n\n{error_message}')

    def _image_generation_finished(self, result_path):
        """Xử lý khi tạo ảnh thành công."""
        self.generate_button.setEnabled(True)
        self.generate_button.setText('🎨 Bắt đầu tạo ảnh AI')
        QMessageBox.information(self, '✅ Hoàn thành', f'Tạo ảnh đã hoàn thành!\n\nCác ảnh được lưu tại:\n{os.path.abspath(result_path)}')

    def _image_generation_error(self, error_message):
        """Xử lý khi tạo ảnh gặp lỗi."""
        self.generate_button.setEnabled(True)
        self.generate_button.setText('🎨 Bắt đầu tạo ảnh AI')
        QMessageBox.critical(self, '❌ Lỗi tạo ảnh', f'Đã xảy ra lỗi trong quá trình tạo ảnh:\n\n{error_message}')

    def _image_merge_finished(self, result_path):
        """Xử lý khi ghép ảnh thành công."""
        self.merge_button.setEnabled(True)
        self.merge_button.setText('🔄 Bắt đầu ghép ảnh AI')
        QMessageBox.information(self, '✅ Hoàn thành', f'Ghép ảnh đã hoàn thành!\n\nCác ảnh đã ghép được lưu tại:\n{result_path}')

    def _image_merge_error(self, error_message):
        """Xử lý khi ghép ảnh gặp lỗi."""
        self.merge_button.setEnabled(True)
        self.merge_button.setText('🔄 Bắt đầu ghép ảnh AI')
        QMessageBox.critical(self, '❌ Lỗi ghép ảnh', f'Đã xảy ra lỗi trong quá trình ghép ảnh:\n\n{error_message}')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Thiết lập font mặc định cho toàn bộ ứng dụng
    font = QFont("Arial", 10)
    app.setFont(font)
    
    ex = HSKGeneratorApp()
    ex.show()
    sys.exit(app.exec_())