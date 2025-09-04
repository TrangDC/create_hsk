import os
import re
from PIL import Image, ImageDraw, ImageFont
import openpyxl
from pathlib import Path

class ImageMerger:
    def __init__(self, excel_file, images_folder, output_folder="IMAGES_MERGED"):
        self.excel_file = excel_file
        self.images_folder = Path(images_folder)
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(exist_ok=True)
        
        # Tạo font hỗ trợ tiếng Trung
        self.font = self._load_chinese_font(24)
        self.small_font = self._load_chinese_font(16)
        self.medium_font = self._load_chinese_font(20)
    
    def _load_chinese_font(self, size):
        """Tải font hỗ trợ tiếng Trung"""
        # Danh sách font hỗ trợ tiếng Trung trên các hệ điều hành khác nhau
        chinese_fonts = [
            # Windows
            "C:/Windows/Fonts/simsun.ttc",
            "C:/Windows/Fonts/msyh.ttc", 
            "C:/Windows/Fonts/simhei.ttf",
            # macOS
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            # Linux
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            # Font có sẵn
            "arial.ttf",
            "Times New Roman.ttf"
        ]
        
        for font_path in chinese_fonts:
            try:
                return ImageFont.truetype(font_path, size)
            except:
                continue
        
        # Nếu không tìm thấy font nào, sử dụng font mặc định
        try:
            return ImageFont.load_default()
        except:
            return ImageFont.load_default()
    
    def load_excel_data(self):
        """Đọc dữ liệu từ file Excel"""
        workbook = openpyxl.load_workbook(self.excel_file)
        sheet = workbook.active
        data = []
        
        for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            if len(row) >= 11:  # Đảm bảo có đủ cột K (index 10)
                k_value = row[10]  # Cột K (index 10)
                f_value = row[5] if len(row) > 5 else ""  # Cột F (index 5)
                e_value = row[4] if len(row) > 4 else ""  # Cột E (index 4)
                
                if k_value:  # Chỉ xử lý nếu cột K có giá trị
                    data.append({
                        'row_number': row_idx,
                        'k_value': str(k_value).strip(),
                        'f_value': str(f_value) if f_value else "",
                        'e_value': str(e_value) if e_value else ""
                    })
        
        return data
    
    def parse_k_value(self, k_value):
        """Phân tích giá trị cột K"""
        if ',' in k_value:
            # Trường hợp "number,tên ảnh"
            parts = k_value.split(',', 1)
            number = parts[0].strip()
            image_names = parts[1].strip().split('-')
            return 'with_number', number, image_names
        else:
            # Trường hợp "tên ảnh"
            image_names = k_value.split('-')
            return 'without_number', None, image_names
    
    def load_image(self, image_name):
        """Tải ảnh từ thư mục"""
        # Thử các extension phổ biến
        extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
        
        for ext in extensions:
            image_path = self.images_folder / f"{image_name}{ext}"
            if image_path.exists():
                return Image.open(image_path)
        
        # Nếu không tìm thấy, tạo ảnh placeholder
        placeholder = Image.new('RGB', (200, 200), color='lightgray')
        draw = ImageDraw.Draw(placeholder)
        draw.text((10, 70), f"Missing:\n{image_name}", fill='black', font=self.small_font)
        return placeholder
    
    def resize_image(self, image, max_width=200, max_height=200):
        """Resize ảnh giữ tỷ lệ"""
        image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        return image
    
    def extract_text_after_keywords(self, text, keywords):
        """Trích xuất text sau các từ khóa đến khi gặp enter xuống dòng"""
        result = {}
        
        for keyword in keywords:
            # Tìm text sau keyword đến khi gặp xuống dòng hoặc keyword khác
            pattern = f"{keyword}\\s*(.*?)(?=\\n|Từ vựng:|Pinyin:|$)"
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                extracted = match.group(1).strip()
                # Loại bỏ các ký tự xuống dòng thừa
                extracted = re.sub(r'\n+', ' ', extracted)
                result[keyword] = extracted
        
        return result
    
    def draw_multiline_text(self, draw, text, x, y, font, fill='black', max_width=300):
        """Vẽ text nhiều dòng với độ rộng tối đa"""
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            bbox = draw.textbbox((0, 0), test_line, font=font)
            line_width = bbox[2] - bbox[0]
            
            if line_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                    current_line = word
                else:
                    lines.append(word)
        
        if current_line:
            lines.append(current_line)
        
        # Vẽ từng dòng
        line_height = font.size + 5
        for i, line in enumerate(lines):
            draw.text((x, y + i * line_height), line, fill=fill, font=font)
        
        return len(lines) * line_height
    
    def create_background(self, width=800, height=600):
        """Tạo background trắng"""
        return Image.new('RGB', (width, height), color='white')
    
    def process_with_number_and_keywords(self, number, image_names, f_value, output_path):
        """Xử lý trường hợp có number và có từ khóa trong cột F"""
        background = self.create_background()
        draw = ImageDraw.Draw(background)
        
        # 1. Vẽ number ở giữa bên trái
        number_bbox = draw.textbbox((0, 0), number, font=self.font)
        number_width = number_bbox[2] - number_bbox[0]
        number_height = number_bbox[3] - number_bbox[1]
        number_x = 50
        number_y = (600 - number_height) // 2
        draw.text((number_x, number_y), number, fill='black', font=self.font)
        
        # 2. Ghép ảnh tiếp theo
        current_x = number_x + number_width + 30
        images_total_width = 0
        processed_images = []
        
        for img_name in image_names:
            img = self.load_image(img_name.strip())
            img = self.resize_image(img, max_width=180, max_height=180)
            processed_images.append(img)
            images_total_width += img.width + 10
        
        # Căn giữa các ảnh theo chiều dọc
        images_y = (600 - 120) // 2
        for img in processed_images:
            background.paste(img, (current_x, images_y))
            current_x += img.width + 10
        
        # 3. Trích xuất và vẽ text từ cột F
        keywords = ["Pinyin:", "Từ vựng:"]
        extracted_text = self.extract_text_after_keywords(f_value, keywords)
        
        text_x = current_x + 20
        text_y = 250
        
        # Vẽ Pinyin trước (ở trên)
        if "Pinyin:" in extracted_text:
            pinyin_text = extracted_text["Pinyin:"]
            text_height = self.draw_multiline_text(
                draw, pinyin_text, text_x, text_y, 
                self.medium_font, fill='black', max_width=250
            )
            text_y += text_height + 20
        
        # Vẽ Từ vựng sau (ở dưới)
        if "Từ vựng:" in extracted_text:
            vocab_text = extracted_text["Từ vựng:"]
            self.draw_multiline_text(
                draw, vocab_text, text_x, text_y, 
                self.font, fill='black', max_width=250
            )
        
        background.save(output_path)

    def process_with_number_and_vocab_from_e(self, number, image_names, e_value, output_path):
        """Xử lý trường hợp có number và có từ khóa 'Từ vựng:' trong cột E"""
        background = self.create_background()
        draw = ImageDraw.Draw(background)
        
        # 1. Vẽ number ở giữa bên trái
        number_bbox = draw.textbbox((0, 0), number, font=self.font)
        number_width = number_bbox[2] - number_bbox[0]
        number_height = number_bbox[3] - number_bbox[1]
        number_x = 50
        number_y = (600 - number_height) // 2
        draw.text((number_x, number_y), number, fill='black', font=self.font)
        
        # 2. Ghép ảnh tiếp theo
        current_x = number_x + number_width + 30
        processed_images = []
        
        for img_name in image_names:
            img = self.load_image(img_name.strip())
            img = self.resize_image(img, max_width=180, max_height=180)
            processed_images.append(img)
        
        # Căn giữa các ảnh theo chiều dọc
        images_y = (600 - 120) // 2
        for img in processed_images:
            background.paste(img, (current_x, images_y))
            current_x += img.width + 10
        
        # 3. Trích xuất và vẽ text từ cột E (chỉ Từ vựng:)
        keywords = ["Từ vựng:"]
        extracted_text = self.extract_text_after_keywords(e_value, keywords)
        
        text_x = current_x + 20
        text_y = 250
        
        # Vẽ Từ vựng
        if "Từ vựng:" in extracted_text:
            vocab_text = extracted_text["Từ vựng:"]
            self.draw_multiline_text(
                draw, vocab_text, text_x, text_y, 
                self.font, fill='black', max_width=250
            )
        
        background.save(output_path)
    
    def process_with_number_no_keywords(self, number, image_names, output_path):
        """Xử lý trường hợp có number nhưng không có từ khóa trong cột F"""
        background = self.create_background()
        draw = ImageDraw.Draw(background)
        
        # Vẽ number ở bên trái
        draw.text((50, 50), number, fill='black', font=self.font)
        
        # Tải và ghép ảnh
        current_x = 150
        current_y = 50
        
        if len(image_names) == 1:
            # Chỉ có 1 ảnh
            img = self.load_image(image_names[0].strip())
            img = self.resize_image(img)
            background.paste(img, (current_x, current_y))
        else:
            # Nhiều ảnh với chữ A, B, C...
            for i, img_name in enumerate(image_names):
                if current_x + 170 > 800:  # Xuống dòng nếu không đủ chỗ
                    current_x = 150
                    current_y += 250
                
                img = self.load_image(img_name.strip())
                img = self.resize_image(img)
                background.paste(img, (current_x, current_y))
                
                # Vẽ chữ A, B, C... dưới ảnh
                letter = chr(ord('A') + i)
                letter_x = current_x + img.width // 2 - 10
                letter_y = current_y + img.height + 10
                draw.text((letter_x, letter_y), letter, fill='black', font=self.font)
                
                current_x += img.width + 20
        
        background.save(output_path)
    
    def process_without_number(self, image_names, output_path):
        """Xử lý trường hợp không có number"""
        background = self.create_background()
        draw = ImageDraw.Draw(background)
        
        current_x = 80
        current_y = 100
        
        for i, img_name in enumerate(image_names):
            if current_x + 250 > 800:  # Xuống dòng nếu không đủ chỗ
                current_x = 80
                current_y += 200
            
            # Vẽ chữ A, B, C... trước ảnh
            letter = chr(ord('A') + i)
            draw.text((current_x, current_y + 60), letter, fill='black', font=self.font)
            
            # Tải và ghép ảnh
            img = self.load_image(img_name.strip())
            img = self.resize_image(img)
            img_x = current_x + 30
            background.paste(img, (img_x, current_y))
            
            current_x += img.width + 50
        
        background.save(output_path)
    
    def process_all(self):
        """Xử lý toàn bộ dữ liệu"""
        data = self.load_excel_data()
        
        print(f"Tìm thấy {len(data)} dòng cần xử lý")
        
        for item in data:
            try:
                row_number = item['row_number']
                k_value = item['k_value']
                f_value = item['f_value']
                e_value = item['e_value']

                # Phân tích k_value
                parse_type, number, image_names = self.parse_k_value(k_value)
                
                # Tạo tên file output
                output_filename = f"row{row_number}.png"
                output_path = self.output_folder / output_filename
                
                print(f"Đang xử lý dòng {row_number}: {k_value}")
                
                if parse_type == 'with_number':
                    # Kiểm tra từ khóa trong cột E trước
                    if "Từ vựng:" in e_value:
                        self.process_with_number_and_vocab_from_e(number, image_names, e_value, output_path)
                    # Kiểm tra có từ khóa trong cột F không
                    elif "Từ vựng:" in f_value and "Pinyin:" in f_value:
                        self.process_with_number_and_keywords(number, image_names, f_value, output_path)
                    else:
                        self.process_with_number_no_keywords(number, image_names, output_path)
                else:
                    # Trường hợp không có number
                    self.process_without_number(image_names, output_path)
                
                print(f"Đã tạo: {output_filename}")
                
            except Exception as e:
                print(f"Lỗi khi xử lý dòng {item['row_number']}: {str(e)}")
        
        print(f"\nHoàn thành! Kết quả được lưu trong thư mục: {self.output_folder}")

# Sử dụng chương trình
if __name__ == "__main__":
    # Cấu hình đường dẫn
    EXCEL_FILE = r"C:\Users\EdmicroUser\Desktop\create_hsk\output\hsk1_20250822_132340\hsk1_output.xlsx"  # Đường dẫn đến file Excel
    IMAGES_FOLDER = r"C:\Users\EdmicroUser\Desktop\create_hsk\IMG_CREATE_BY_AI"   # Thư mục chứa ảnh đầu vào
    OUTPUT_FOLDER = "IMAGES_MERGED"  # Thư mục đầu ra
    
    # Kiểm tra file tồn tại
    if not os.path.exists(EXCEL_FILE):
        print(f"Không tìm thấy file Excel: {EXCEL_FILE}")
        print("Vui lòng đặt file Excel với tên 'input.xlsx' trong cùng thư mục với script")
        exit(1)
    
    if not os.path.exists(IMAGES_FOLDER):
        print(f"Không tìm thấy thư mục ảnh: {IMAGES_FOLDER}")
        print("Vui lòng tạo thư mục 'images' và đặt các ảnh vào đó")
        exit(1)
    
    # Khởi tạo và chạy
    merger = ImageMerger(EXCEL_FILE, IMAGES_FOLDER, OUTPUT_FOLDER)
    merger.process_all()