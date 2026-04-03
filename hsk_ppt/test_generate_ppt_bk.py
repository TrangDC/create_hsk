import json
import math
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Pt, Inches, Cm
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE
import os
import re

class PPTGenerator:
    def __init__(self, template_path: str, json_path: str):
        self.prs = Presentation(template_path)

        with open(json_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

        # Template có 41 slides (index 0–40):
        #   [0]      → add_cover_slide()        (edit in-place)
        #   [1]      → add_table_of_content()   (edit in-place)
        #   [2..39]  → content slides           (lấy tuần tự qua _next_slide())
        #   [40]     → add_end_slide()          (edit in-place)

        # Con trỏ slide content — bắt đầu từ index 2
        self._slide_cursor = 2

        # Màu chủ đạo
        self.primary_red = RGBColor(0xB5, 0x1F, 0x09)

    # ================================================================
    # UTIL
    # ================================================================

    def _auto_fit_text(self, shape):
        if not shape.has_text_frame:
            return
        tf = shape.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE

    def _next_slide(self):
        """Trả về slide tiếp theo trong vùng content (index 2 → 39), tự tăng cursor."""
        idx = self._slide_cursor
        if idx > 39:
            raise IndexError(
                f"Đã dùng hết slide template content (cursor={idx}). "
                "Tăng số slide trong template hoặc giảm dữ liệu."
            )
        self._slide_cursor += 1
        return self.prs.slides[idx]

    def _get_all_shapes(self, shapes):
        all_shapes = []
        for shape in shapes:
            all_shapes.append(shape)
            if shape.shape_type == 6:  # GROUP
                for sub in self._get_all_shapes(shape.shapes):
                    all_shapes.append(sub)
        return all_shapes

    def _find_shape_by_name(self, shapes, name: str):
        for shape in shapes:
            if shape.name == name:
                return shape
        return None

    def hex_to_rgb(self, hex_color: str):
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def hex_to_rgb_color(self, hex_color: str):
        hex_color = hex_color.lstrip("#")
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return RGBColor(r, g, b)

    def _bring_to_front(self, shape):
        sp = shape._element
        parent = sp.getparent()
        parent.remove(sp)
        parent.append(sp)

    def _set_text_exact_style(
        self, shape, text: str,
        font_name: str = "Arial", font_size: int = 40,
        bold: bool = True, italic: bool = False,
        color: str | None = None, align: str = "center"
    ):
        if not shape or not shape.has_text_frame:
            return
        tf = shape.text_frame
        tf.clear()
        p = tf.paragraphs[0]
        align_map = {
            "left":    PP_ALIGN.LEFT,
            "center":  PP_ALIGN.CENTER,
            "right":   PP_ALIGN.RIGHT,
            "justify": PP_ALIGN.JUSTIFY,
        }
        p.alignment = align_map.get(align.lower(), PP_ALIGN.CENTER)
        run = p.add_run()
        run.text = text
        font = run.font
        font.name = font_name
        font.size = Pt(font_size)
        font.bold = bold
        font.italic = italic
        if color:
            rgb = self.hex_to_rgb(color)
            font.color.rgb = RGBColor(*rgb)

    def add_text(
        self, slide, text: str,
        left: float, top: float, width: float, height: float,
        font_size: int = 24,
        bold: bool = False,
        color=None,
        align=PP_ALIGN.LEFT,
        italic: bool = False,
        font_name: str = "Arial"
    ):
        """
        Thêm textbox lên slide.
        color: str hex ("B51F09") hoặc RGBColor.
        align: PP_ALIGN enum hoặc str ("left"/"center"/"right").
        """
        box = slide.shapes.add_textbox(
            Inches(left), Inches(top), Inches(width), Inches(height)
        )
        tf = box.text_frame
        tf.word_wrap = True
        tf.clear()

        align_map = {
            "left":    PP_ALIGN.LEFT,
            "center":  PP_ALIGN.CENTER,
            "right":   PP_ALIGN.RIGHT,
            "justify": PP_ALIGN.JUSTIFY,
        }
        if isinstance(align, str):
            align = align_map.get(align.lower(), PP_ALIGN.LEFT)

        for idx, line in enumerate(str(text).split("\n")):
            para = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
            para.alignment = align
            run = para.add_run()
            run.text        = line
            run.font.size   = Pt(font_size)
            run.font.bold   = bold
            run.font.italic = italic
            run.font.name   = font_name
            if color is not None:
                if isinstance(color, RGBColor):
                    run.font.color.rgb = color
                elif isinstance(color, str):
                    run.font.color.rgb = RGBColor(*self.hex_to_rgb(color))

        self._bring_to_front(box)
        return box

    def get_text_height(self, text: str, font_size: int, width_inches: float) -> float:
        """Ước tính chiều cao (inches) cho một đoạn text, hỗ trợ CJK full-width."""
        SLIDE_HEIGHT   = 7.5
        width_pt       = width_inches * 72
        char_width_pt  = font_size * 0.6
        units_per_line = width_pt / char_width_pt

        def char_units(ch):
            cp = ord(ch)
            if (0x4E00 <= cp <= 0x9FFF or
                    0x3000 <= cp <= 0x303F or
                    0xFF00 <= cp <= 0xFFEF or
                    0x3040 <= cp <= 0x30FF):
                return 1.0
            return 0.5

        total_lines = 0
        for raw_line in str(text).split("\n"):
            if raw_line.strip() == "":
                total_lines += 1
                continue
            line_units = sum(char_units(c) for c in raw_line)
            total_lines += max(1, math.ceil(line_units / units_per_line))

        line_height_pt  = font_size * 1.2
        total_height_pt = total_lines * line_height_pt + 8
        return (total_height_pt / (SLIDE_HEIGHT * 72)) * SLIDE_HEIGHT

    def _apply_title_styling(self, shape, text: str, max_font=135, min_font=40):
        """
        Căn chỉnh font-size tự động để title dài vừa vặn trên 1 dòng
        mà không bị vượt quá chiều rộng và chiều cao của khung Textbox.
        """
        if not text:
            return

        # Ép chữ nằm trên 1 dòng
        tf = shape.text_frame
        tf.word_wrap = False
        
        # 1 point (pt) = 12700 EMUs trong thư viện python-pptx
        # Tính toán kích thước thực tế của text box (theo đơn vị Point)
        shape_width_pt = shape.width / 12700.0
        shape_height_pt = shape.height / 12700.0
        
        # Lấy thông số lề (margin) của Textbox. Nếu PPT không set thì lấy giá trị mặc định
        margin_left = tf.margin_left / 12700.0 if tf.margin_left is not None else 7.2
        margin_right = tf.margin_right / 12700.0 if tf.margin_right is not None else 7.2
        margin_top = tf.margin_top / 12700.0 if tf.margin_top is not None else 3.6
        margin_bottom = tf.margin_bottom / 12700.0 if tf.margin_bottom is not None else 3.6
        
        # Không gian thực tế an toàn được phép chứa chữ (đã trừ lề)
        available_width_pt = shape_width_pt - margin_left - margin_right
        available_height_pt = shape_height_pt - margin_top - margin_bottom
        
        # Tính "đơn vị" bề rộng (1 chữ Hán/Full-width = 1 unit, 1 chữ Latinh/Số = 0.55 unit)
        units = 0.0
        for ch in text:
            cp = ord(ch)
            if (0x4E00 <= cp <= 0x9FFF or 0x3000 <= cp <= 0x303F or 
                0xFF00 <= cp <= 0xFFEF or 0x3040 <= cp <= 0x30FF):
                units += 1.0
            else:
                units += 0.55

        if units == 0:
            optimal_font = max_font
        else:
            # 1. Ràng buộc Chiều rộng: Size chữ tối đa để dàn đủ số ký tự trên bề ngang
            max_font_by_width = (available_width_pt / units) * 0.95 # Nhân 0.95 để trừ hao an toàn 5%
            
            # 2. Ràng buộc Chiều cao: Size chữ tối đa không được lớn hơn chiều cao Textbox
            max_font_by_height = available_height_pt * 0.90 # Trừ hao 10% cho khoảng cách dòng (line spacing)
            
            # Lấy size chữ thoả mãn CẢ 2 ĐIỀU KIỆN (Không tràn ngang, không tràn dọc)
            calculated_font = min(max_font_by_width, max_font_by_height)
            
            # Chốt font size cuối cùng nằm trong khoảng giới hạn cho phép
            optimal_font = int(min(max_font, max(min_font, calculated_font)))

        self._set_text_exact_style(
            shape, text, font_size=optimal_font, color="B51F09", align="center"
        )

    def _replace_subtitle_with_rounded_rect(self, slide, old_shape, text: str, font_size: int = 50):
        """Thay thế textbox cũ bằng khối bo tròn màu đỏ có chữ trắng căn giữa."""
        
        center_x = old_shape.left + old_shape.width / 2.0
        center_y = old_shape.top + old_shape.height / 2.0
        
        # Ước tính chiều rộng cần thiết: mỗi ký tự tốn khoảng (0.4 * font_size) points
        # Cộng thêm padding ~ 1.5 inches để nhìn cân đối
        est_width_in = len(text) * (font_size * 0.4 / 72) + 1.5
        new_width = int(Inches(est_width_in))
        new_height = int(Inches(1.2))  # Chiều cao cố định (1.2") đủ rộng cho text 50pt
        
        new_left = int(center_x - new_width / 2.0)
        new_top = int(center_y - new_height / 2.0)
        
        # Xóa shape cũ (ẩn đi bằng cách gỡ khỏi XML element tree)
        old_element = old_shape._element
        old_element.getparent().remove(old_element)
        
        # Tạo shape bo tròn mới
        new_shape = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, new_left, new_top, new_width, new_height
        )
        
        # Pill shape (bo tròn hoàn toàn hai đầu)
        new_shape.adjustments[0] = 0.5 
        
        # Định dạng màu đỏ cho fill và tắt viền
        new_shape.fill.solid()
        new_shape.fill.fore_color.rgb = RGBColor(0xB5, 0x1F, 0x09)
        new_shape.line.fill.background()
        
        # Căn giữa chữ theo chiều dọc và ngang
        tf = new_shape.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        
        self._set_text_exact_style(
            new_shape, text, font_size=font_size, color="FFFFFF", align="center"
        )
        self._bring_to_front(new_shape)

    def _add_hl_text(self, paragraph, text, default_font, default_size, default_color, hl_color="29741D"):
        """
        Hàm hỗ trợ bóc tách thẻ <hl>...</hl> và add vào paragraph với định dạng khác nhau.
        """
        # Tách chuỗi dựa trên thẻ <hl> và </hl>
        parts = re.split(r'(<hl>.*?</hl>)', text)
        
        for part in parts:
            run = paragraph.add_run()
            if part.startswith('<hl>') and part.endswith('</hl>'):
                # Phần nằm trong thẻ highlight: In đậm và màu xanh lá
                content = part[4:-5]
                run.text = content
                run.font.bold = True
                run.font.color.rgb = self.hex_to_rgb_color(hl_color)
            else:
                # Phần text bình thường: Không đậm và màu mặc định
                run.text = part
                run.font.bold = False
                run.font.color.rgb = self.hex_to_rgb_color(default_color)
            
            run.font.name = default_font
            run.font.size = Pt(default_size)

    def _render_vocab_layout(self, title_text, category_desc, items):
        """
        Hàm render layout 4 cột kèm ảnh cho Extra Knowledge.
        Cập nhật: Font size mô tả động và cho phép xuống dòng.
        """
        # Giới hạn tối đa 4 từ
        display_items = items[:4]
        if not display_items:
            return

        slide = self._next_slide()
        import sys; base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        flower_icon_path = os.path.join(base_dir, "resources", "images", "ppt", "flower_point.png")

        # 1. TIÊU ĐỀ CHÍNH
        title_width, title_height = Cm(20.14), Cm(2.67)
        title_left, title_top = (self.prs.slide_width - title_width) / 2, Cm(1.26)
        title_box = slide.shapes.add_textbox(title_left, title_top, title_width, title_height)
        title_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        self._set_text_exact_style(
            title_box, title_text, font_name="Fraunces", font_size=57, 
            color="FCF1D4", bold=False, align="center"
        )

        # 2. CATEGORY DESCRIPTION (Xử lý font size động và xuống dòng)
        num_items = len(display_items)
        # Logic: 4 từ -> 30pt. Dưới 4 từ -> 35.8pt
        desc_font_size = 30 if num_items == 4 else 35.8

        desc_left, desc_top = Inches(3.94), Inches(2.33)
        desc_width, desc_height = Inches(13.19), Inches(0.57)

        # Chèn bông hoa
        if os.path.exists(flower_icon_path):
            icon_size = Cm(0.8)
            slide.shapes.add_picture(flower_icon_path, desc_left - icon_size - Cm(0.2), desc_top + Cm(0.15), icon_size, icon_size)

        desc_box = slide.shapes.add_textbox(desc_left, desc_top, desc_width, desc_height)
        # Thiết lập Text Frame cho phép xuống dòng
        tf_desc = desc_box.text_frame
        tf_desc.word_wrap = True 
        
        self._set_text_exact_style(
            desc_box, category_desc, font_name="Muli Bold", font_size=desc_font_size, 
            color="000000", bold=True, align="left"
        )
        # Đảm bảo word_wrap vẫn bật sau khi set style
        desc_box.text_frame.word_wrap = True

        # 3. RENDER 4 CỘT (Ảnh + Chữ)
        word_x_start, word_y = Inches(1.17), Inches(7.14)
        img_x_start, img_y = Inches(1.52), Inches(3.57)
        
        word_step = Inches(4.62)
        img_step = Inches(4.68)

        for i, item in enumerate(display_items):
            curr_word_x = word_x_start + (i * word_step)
            curr_img_x = img_x_start + (i * img_step)

            # --- A. Textbox Placeholder cho Ảnh ---
            local_img = item.get("local_image_path")
            img_desc = item.get("image_description", f"Mô tả ảnh {i+1}")
            
            if local_img and os.path.exists(local_img):
                slide.shapes.add_picture(local_img, curr_img_x, img_y, Inches(3.1), Inches(3.1))
            else:
                img_box = slide.shapes.add_textbox(curr_img_x, img_y, Inches(3.1), Inches(3.1))
                img_box.line.color.rgb = self.hex_to_rgb_color("CCCCCC")
                img_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
                self._set_text_exact_style(
                    img_box, img_desc, font_name="Arial", font_size=14,
                    color="999999", bold=False, align="center"
                )
            # --- B. Textbox Nội dung từ (HZ, PY, VI) ---
            word_box = slide.shapes.add_textbox(curr_word_x, word_y, Inches(3.81), Inches(1.82))
            tf = word_box.text_frame
            tf.word_wrap = True
            tf.margin_top = tf.margin_bottom = tf.margin_left = tf.margin_right = 0
            
            # Paragraph 1: Hán tự
            p_hz = tf.paragraphs[0]
            run_hz = p_hz.add_run()
            run_hz.text = item.get("hz", "")
            run_hz.font.name = "字由点字云霆楷体"
            run_hz.font.size = Pt(41.8)
            run_hz.font.color.rgb = self.hex_to_rgb_color("000000")
            p_hz.alignment = PP_ALIGN.CENTER

            # Paragraph 2: Pinyin
            p_py = tf.add_paragraph()
            run_py = p_py.add_run()
            py_val = item.get("py") or item.get("pinyin") or ""
            run_py.text = f"/{py_val}/"
            run_py.font.name = "Muli"
            run_py.font.size = Pt(26)
            run_py.font.color.rgb = self.hex_to_rgb_color("545454")
            p_py.alignment = PP_ALIGN.CENTER

            # Paragraph 3: Tiếng Việt
            p_vi = tf.add_paragraph()
            run_vi = p_vi.add_run()
            run_vi.text = item.get("vi", "")
            run_vi.font.name = "Muli Italics"
            run_vi.font.size = Pt(26)
            run_vi.font.italic = True
            run_vi.font.color.rgb = self.hex_to_rgb_color("A23131")
            p_vi.alignment = PP_ALIGN.CENTER

    def _render_grammar_formula_layout(self, title_text, data):
        """
        Render layout cho cấu trúc ngữ pháp có công thức (grammar_formula).
        """
        slide = self._next_slide()
        import sys; base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        flower_icon_path = os.path.join(base_dir, "resources", "images", "ppt", "flower_point.png")
        
        # 1. TIÊU ĐỀ CHÍNH (Hội thoại X / Đoạn văn Y)
        title_width, title_height = Cm(20.14), Cm(2.67)
        title_left, title_top = (self.prs.slide_width - title_width) / 2, Cm(1.26)
        title_box = slide.shapes.add_textbox(title_left, title_top, title_width, title_height)
        title_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        self._set_text_exact_style(
            title_box, title_text, font_name="Fraunces", font_size=57, 
            color="FCF1D4", bold=False, align="center"
        )

        # Thông số chung
        box_left = Inches(2.61)
        box_width = Inches(15.27)
        font_size_main = 32 # 406400 EMUs
        
        # 2. KHỐI TITLE & FORMULA (Cấu trúc... + Công thức)
        formula_start_top = Inches(2.2)
        
        # Ước tính chiều cao dựa trên text (Title + Formula là 2 dòng)
        # 1 dòng 32pt ~ 0.5 inch. 2 dòng + padding ~ 1.19 inch
        formula_text = f"{data.get('title', '')}\n{data.get('formula', '')}"
        est_height_formula = self.get_text_height(formula_text, font_size_main, 15.27)
        # Đảm bảo tối thiểu 1.19"
        final_h_formula = max(Inches(1.19), Inches(est_height_formula))

        # Chèn hoa cho khối Formula
        if os.path.exists(flower_icon_path):
            slide.shapes.add_picture(flower_icon_path, box_left - Cm(1.2), formula_start_top + Cm(0.15), Cm(0.8), Cm(0.8))

        formula_box = slide.shapes.add_textbox(box_left, formula_start_top, box_width, final_h_formula)
        tf_f = formula_box.text_frame
        tf_f.word_wrap = True
        
        # Paragraph 1: Title (Black)
        p1 = tf_f.paragraphs[0]
        p1.space_after = Pt(2)
        run1 = p1.add_run()
        run1.text = data.get('title', '')
        run1.font.name, run1.font.size, run1.font.bold = "Muli Bold", Pt(font_size_main), True
        run1.font.color.rgb = self.hex_to_rgb_color("000000")

        # Paragraph 2: Formula (Red)
        p2 = tf_f.add_paragraph()
        run2 = p2.add_run()
        run2.text = data.get('formula', '')
        run2.font.name, run2.font.size, run2.font.bold = "Muli Bold", Pt(font_size_main), True
        run2.font.color.rgb = self.hex_to_rgb_color("A40400")

        # 3. KHỐI USAGE (Cách dùng)
        # Tính vị trí Top dựa vào khối phía trên (cách ra 0.2 inch)
        usage_start_top = formula_start_top + final_h_formula + Inches(0.15)
        usage_text = f"Cách dùng: {data.get('usage', '')}"
        est_height_usage = self.get_text_height(usage_text, font_size_main, 15.27)
        final_h_usage = max(Inches(1.19), Inches(est_height_usage))

        # Chèn hoa cho khối Usage
        if os.path.exists(flower_icon_path):
            slide.shapes.add_picture(flower_icon_path, box_left - Cm(1.2), usage_start_top + Cm(0.15), Cm(0.8), Cm(0.8))

        usage_box = slide.shapes.add_textbox(box_left, usage_start_top, box_width, final_h_usage)
        tf_u = usage_box.text_frame
        tf_u.word_wrap = True
        p_u = tf_u.paragraphs[0]
        
        # Tách "Cách dùng:" để in đậm
        run_u_label = p_u.add_run()
        run_u_label.text = "Cách dùng: "
        run_u_label.font.name, run_u_label.font.size, run_u_label.font.bold = "Muli Bold", Pt(font_size_main), True
        
        run_u_content = p_u.add_run()
        run_u_content.text = data.get('usage', '')
        run_u_content.font.name, run_u_content.font.size = "Muli", Pt(font_size_main)

        # 4. RENDER 2 VÍ DỤ CÓ ẢNH (Nằm ngang ở dưới)
        examples = data.get("examples", [])[:2]
        
        img_y = Inches(5.54)
        txt_y = Inches(8.98)
        img_w_h = Inches(3.2)
        
        # Tọa độ ngang của 2 ẢNH cố định
        img_left_configs = [Inches(3.33), Inches(12.75)]

        for i, ex in enumerate(examples):
            l_img = img_left_configs[i]
            
            # --- A. Placeholder cho Ảnh ---
            local_img = ex.get("local_image_path")
            img_desc = ex.get("image_description", f"Mô tả ảnh {i+1}")
            
            if local_img and os.path.exists(local_img):
                slide.shapes.add_picture(local_img, l_img, img_y, img_w_h, img_w_h)
            else:
                img_box = slide.shapes.add_textbox(l_img, img_y, img_w_h, img_w_h)
                img_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
                self._set_text_exact_style(
                    img_box, img_desc, font_name="Arial", font_size=14,
                    color="999999", align="center"
                )
            # --- B. Xử lý Textbox Ví dụ (Căn giữa theo ảnh) ---
            hz_text = ex.get('hz', '')
            
            # Kiểm tra nếu câu Hán tự dài (>10 chữ) thì dùng Wide Layout, không thì dùng Normal
            if len(hz_text) > 10:
                w_txt = Inches(9.0)
                h_txt = Inches(2.05)
            else:
                w_txt = Inches(6.44)
                h_txt = Inches(1.73)
            
            # TOÁN HỌC: Tính Left để Textbox luôn nằm chính giữa dưới Ảnh
            # L_txt = L_img + (W_img/2) - (W_txt/2)
            l_txt = l_img + (img_w_h / 2.0) - (w_txt / 2.0)

            txt_box = slide.shapes.add_textbox(l_txt, txt_y, w_txt, h_txt)
            tf_ex = txt_box.text_frame
            tf_ex.word_wrap = True
            tf_ex.vertical_anchor = MSO_ANCHOR.MIDDLE # Giúp text luôn cân đối trong box
            
            # P1: Hán tự (39.5pt)
            p_hz = tf_ex.paragraphs[0]
            run_hz = p_hz.add_run()
            run_hz.text = hz_text
            run_hz.font.name, run_hz.font.size = "字由点字云霆楷体", Pt(39.5)
            run_hz.font.color.rgb = self.hex_to_rgb_color("000000")
            p_hz.alignment = PP_ALIGN.CENTER

            # P2: Pinyin (24.6pt)
            p_py = tf_ex.add_paragraph()
            run_py = p_py.add_run()
            run_py.text = f"/{ex.get('py', '')}/"
            run_py.font.name, run_py.font.size = "Muli", Pt(24.6)
            run_py.font.color.rgb = self.hex_to_rgb_color("545454")
            p_py.alignment = PP_ALIGN.CENTER

            # P3: Tiếng Việt (24.6pt, Red A23131)
            p_vi = tf_ex.add_paragraph()
            run_vi = p_vi.add_run()
            run_vi.text = ex.get('vi', '')
            run_vi.font.name, run_vi.font.size = "Muli", Pt(24.6)
            run_vi.font.color.rgb = self.hex_to_rgb_color("A23131")
            p_vi.alignment = PP_ALIGN.CENTER

    def _render_grammar_advanced_layout(self, title_text, data):
        """
        Render layout cho Ngữ pháp nâng cao (grammar_advanced).
        Chia làm 3 slide: 
        - Slide 1: Giải thích & Cách dùng
        - Slide 2: Bảng so sánh
        - Slide 3: Lưu ý & Ví dụ
        """
        import sys; base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        flower_icon_path = os.path.join(base_dir, "resources", "images", "ppt", "flower_point.png")
        font_size_main = 32 # 406400 EMUs

        # Hàm bổ trợ: In đậm phần trước dấu hai chấm (:)
        def add_colon_bold_para(tf, text, is_bullet=False):
            p = tf.add_paragraph() if len(tf.paragraphs[0].runs) > 0 else tf.paragraphs[0]
            p.space_after = Pt(6)
            
            # Nếu là list lưu ý thì thêm dấu chấm tròn
            prefix = "• " if is_bullet else ""
            
            if ":" in text:
                parts = text.split(":", 1)
                run1 = p.add_run()
                run1.text = prefix + parts[0] + ":"
                run1.font.name, run1.font.size, run1.font.bold = "Muli Bold", Pt(font_size_main), True
                run1.font.color.rgb = self.hex_to_rgb_color("000000")
                
                run2 = p.add_run()
                run2.text = parts[1]
                run2.font.name, run2.font.size, run2.font.bold = "Muli", Pt(font_size_main), False
                run2.font.color.rgb = self.hex_to_rgb_color("000000")
            else:
                run = p.add_run()
                run.text = prefix + text
                run.font.name, run.font.size, run.font.bold = "Muli", Pt(font_size_main), False
                run.font.color.rgb = self.hex_to_rgb_color("000000")

        # Hàm bổ trợ: Vẽ Title màu đỏ chuẩn
        def draw_main_title(slide):
            title_width, title_height = Cm(20.14), Cm(2.67)
            title_left, title_top = (self.prs.slide_width - title_width) / 2, Cm(1.26)
            title_box = slide.shapes.add_textbox(title_left, title_top, title_width, title_height)
            title_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
            self._set_text_exact_style(
                title_box, title_text, font_name="Fraunces", font_size=57, 
                color="FCF1D4", bold=False, align="center"
            )

        # =========================================================
        # SLIDE 1: GIẢI THÍCH & CÁCH DÙNG
        # =========================================================
        slide1 = self._next_slide()
        draw_main_title(slide1)

        box_left = Inches(2.82)
        box_width = Inches(14.07)

        # 1A. Textbox Title Cấu trúc
        t1_top = Inches(2.43)
        t1_text = data.get("title", "")
        est_h1 = self.get_text_height(t1_text, font_size_main, 14.07)
        h1 = max(Inches(1.81), Inches(est_h1))
        
        if os.path.exists(flower_icon_path):
            slide1.shapes.add_picture(flower_icon_path, box_left - Cm(1.2), t1_top + Cm(0.15), Cm(0.8), Cm(0.8))

        box1 = slide1.shapes.add_textbox(box_left, t1_top, box_width, h1)
        tf1 = box1.text_frame
        tf1.word_wrap = True
        add_colon_bold_para(tf1, t1_text)

        # 1B. Textbox Ý nghĩa & Cách dùng
        t2_top = t1_top + h1 + Inches(0.2)
        explanation = data.get("explanation", "")
        est_h2 = self.get_text_height(explanation, font_size_main, 14.07)
        h2 = max(Inches(4.27), Inches(est_h2))

        if os.path.exists(flower_icon_path):
            slide1.shapes.add_picture(flower_icon_path, box_left - Cm(1.2), t2_top + Cm(0.15), Cm(0.8), Cm(0.8))

        box2 = slide1.shapes.add_textbox(box_left, t2_top, box_width, h2)
        tf2 = box2.text_frame
        tf2.word_wrap = True
        # Tách các dòng \n để in đậm phần nhãn (Ý nghĩa, Sắc thái...)
        for line in explanation.split("\n"):
            if line.strip():
                add_colon_bold_para(tf2, line.strip())

        # =========================================================
        # SLIDE 2: BẢNG SO SÁNH
        # =========================================================
        table_data = data.get("comparison_table")
        if table_data and table_data.get("headers") and table_data.get("rows"):
            slide2 = self._next_slide()
            draw_main_title(slide2)

            # Intro text cho bảng
            intro_top = Inches(2.43)
            if os.path.exists(flower_icon_path):
                slide2.shapes.add_picture(flower_icon_path, box_left - Cm(1.2), intro_top + Cm(0.15), Cm(0.8), Cm(0.8))
            
            intro_box = slide2.shapes.add_textbox(box_left, intro_top, box_width, Inches(0.8))
            self._set_text_exact_style(
                intro_box, "Một số ví dụ phổ biến:", font_name="Muli Bold", 
                font_size=font_size_main, color="000000", bold=True, align="left"
            )

            # Vẽ bảng
            headers = table_data.get("headers")
            rows = table_data.get("rows")
            
            tb_left, tb_top = Inches(3.12), Inches(3.56)
            tb_width, tb_height = Inches(13.75), Inches(5.9)
            
            num_cols = len(headers)
            num_rows = len(rows) + 1
            
            # Tạo table shape
            table_shape = slide2.shapes.add_table(num_rows, num_cols, tb_left, tb_top, tb_width, tb_height)
            table = table_shape.table

            # Định dạng helper cho cell
            def format_cell(cell, text, is_header=False):
                cell.text_frame.word_wrap = True
                cell.vertical_anchor = MSO_ANCHOR.MIDDLE
                p = cell.text_frame.paragraphs[0]
                p.alignment = PP_ALIGN.CENTER
                run = p.runs[0] if p.runs else p.add_run()
                run.text = text
                run.font.name = "Muli Bold" if is_header else "Muli"
                run.font.size = Pt(28) # Size chữ trong bảng nhỏ hơn một chút cho gọn
                run.font.color.rgb = self.hex_to_rgb_color("000000")

            # Fill Header
            for col_idx, h_text in enumerate(headers):
                format_cell(table.cell(0, col_idx), h_text, is_header=True)

            # Fill Rows
            for row_idx, row_data in enumerate(rows):
                for col_idx, cell_text in enumerate(row_data):
                    if col_idx < num_cols:
                        format_cell(table.cell(row_idx + 1, col_idx), cell_text, is_header=False)

        # =========================================================
        # SLIDE 3: LƯU Ý & VÍ DỤ
        # =========================================================
        slide3 = self._next_slide()
        draw_main_title(slide3)

        notes = data.get("important_notes",[])
        box_left = Inches(2.61)
        box_width = Inches(15.27)
        note_top = Inches(2.2)

        # Tính toán chiều cao khối Notes
        full_note_text = "Lưu ý quan trọng:\n" + "\n".join(notes)
        est_note_h = self.get_text_height(full_note_text, font_size_main, 15.27)
        note_height = max(Inches(3.65), Inches(est_note_h))

        if os.path.exists(flower_icon_path):
            slide3.shapes.add_picture(flower_icon_path, box_left - Cm(1.2), note_top + Cm(0.15), Cm(0.8), Cm(0.8))

        note_box = slide3.shapes.add_textbox(box_left, note_top, box_width, note_height)
        tf_note = note_box.text_frame
        tf_note.word_wrap = True
        
        # Tiêu đề Note
        p_n1 = tf_note.paragraphs[0]
        r_n1 = p_n1.add_run()
        r_n1.text = "Lưu ý quan trọng:"
        r_n1.font.name, r_n1.font.size, r_n1.font.bold = "Muli Bold", Pt(font_size_main), True
        
        # Các dòng note (Bullet point + Bold nhãn)
        for note in notes:
            add_colon_bold_para(tf_note, note, is_bullet=True)

        # --- Vẽ Ảnh & Ví dụ (Bám theo khối Note) ---
        examples = data.get("examples", [])[:2]
        
        # Kích thước cố định mới
        img_w_h = Inches(2.7)
        w_txt, h_txt = Inches(9.13), Inches(1.97)
        
        # Tọa độ ngang (Left) của Textbox chữ (Cố định theo thông số bạn cung cấp)
        txt_left_configs =[Inches(0.51), Inches(10.6)]
        
        # Tọa độ dọc (Top) linh hoạt bám theo khối Note ở trên
        # (Nếu khối Note bình thường, txt_y sẽ rơi vào đúng ~9.09" như bạn tính toán)
        img_y = note_top + note_height + Inches(0.3)
        txt_y = img_y + img_w_h + Inches(0.24) 

        for i, ex in enumerate(examples):
            # Lấy tọa độ Left của Textbox
            l_txt = txt_left_configs[i]
            
            # TOÁN HỌC: Tính Left của Ảnh để Ảnh nằm chính giữa Textbox chữ
            # L_img = L_txt + (W_txt / 2) - (W_img / 2)
            l_img = l_txt + (w_txt / 2.0) - (img_w_h / 2.0)
            
            # 1. Vẽ Placeholder cho Ảnh
            local_img = ex.get("local_image_path")
            img_desc = ex.get("image_description", f"Mô tả ảnh {i+1}")
            
            if local_img and os.path.exists(local_img):
                slide3.shapes.add_picture(local_img, l_img, img_y, img_w_h, img_w_h)
            else:
                img_box = slide3.shapes.add_textbox(l_img, img_y, img_w_h, img_w_h)
                img_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
                self._set_text_exact_style(
                    img_box, img_desc, font_name="Arial", font_size=14,
                    color="999999", align="center"
                )
            # 2. Vẽ Textbox Ví dụ (Kích thước max 9.13" x 1.97")
            txt_box = slide3.shapes.add_textbox(l_txt, txt_y, w_txt, h_txt)
            tf_ex = txt_box.text_frame
            tf_ex.word_wrap = True
            tf_ex.vertical_anchor = MSO_ANCHOR.MIDDLE
            
            # P1: Hán tự (39.5pt)
            p_hz = tf_ex.paragraphs[0]
            run_hz = p_hz.add_run()
            run_hz.text = ex.get('hz', '')
            run_hz.font.name, run_hz.font.size = "字由点字云霆楷体", Pt(39.5)
            run_hz.font.color.rgb = self.hex_to_rgb_color("000000")
            p_hz.alignment = PP_ALIGN.CENTER

            # P2: Pinyin (24.6pt)
            p_py = tf_ex.add_paragraph()
            run_py = p_py.add_run()
            run_py.text = f"/{ex.get('py', '')}/"
            run_py.font.name, run_py.font.size = "Muli", Pt(24.6)
            run_py.font.color.rgb = self.hex_to_rgb_color("545454")
            p_py.alignment = PP_ALIGN.CENTER

            # P3: Tiếng Việt (24.6pt, Màu Đỏ)
            p_vi = tf_ex.add_paragraph()
            run_vi = p_vi.add_run()
            run_vi.text = ex.get('vi', '')
            run_vi.font.name, run_vi.font.size = "Muli", Pt(24.6)
            run_vi.font.color.rgb = self.hex_to_rgb_color("A23131")
            p_vi.alignment = PP_ALIGN.CENTER

    def _render_word_comparison_layout(self, title_text, data):
        """
        Render layout So sánh từ (word_comparison).
        Tích hợp Type Checking để chống lỗi AI trả về chuỗi (str) thay vì object (dict).
        """
        import sys; base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        flower_icon_path = os.path.join(base_dir, "resources", "images", "ppt", "flower_point.png")
        font_size_main = 32 # 406400 EMUs
        
        # --- HÀM BỔ TRỢ ---
        def draw_main_title(slide):
            title_width, title_height = Cm(20.14), Cm(2.67)
            title_left, title_top = (self.prs.slide_width - title_width) / 2, Cm(1.26)
            title_box = slide.shapes.add_textbox(title_left, title_top, title_width, title_height)
            title_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
            self._set_text_exact_style(title_box, title_text, font_name="Fraunces", font_size=57, color="FCF1D4", align="center")

        def draw_sub_title(slide, text):
            sub_width, sub_height = Inches(14.0), Inches(0.8)
            sub_left, sub_top = (self.prs.slide_width / 914400.0 - 14.0)/2, Inches(2.3)
            sub_box = slide.shapes.add_textbox(Inches(sub_left), sub_top, sub_width, sub_height)
            self._set_text_exact_style(sub_box, text, font_name="Muli Bold", font_size=37, color="000000", bold=True, align="center")

        def add_colon_bold_para(tf, text, is_bullet=False):
            p = tf.add_paragraph() if len(tf.paragraphs[0].runs) > 0 else tf.paragraphs[0]
            p.space_after = Pt(6)
            prefix = "• " if is_bullet else ""
            
            if ":" in text:
                parts = text.split(":", 1)
                run1 = p.add_run()
                run1.text = prefix + parts[0] + ":"
                run1.font.name, run1.font.size, run1.font.bold = "Muli Bold", Pt(font_size_main), True
                run2 = p.add_run()
                run2.text = parts[1]
                run2.font.name, run2.font.size, run2.font.bold = "Muli", Pt(font_size_main), False
            else:
                run = p.add_run()
                run.text = prefix + text
                run.font.name, run.font.size, run.font.bold = "Muli", Pt(font_size_main), False

        sub_title_text = data.get("title", "")

        # =========================================================
        # SLIDE 1: ĐIỂM GIỐNG NHAU (Fix lỗi Type)
        # =========================================================
        sim_data = data.get("similarities", {})
        if sim_data:
            slide1 = self._next_slide()
            draw_main_title(slide1)
            draw_sub_title(slide1, sub_title_text)

            box_left, box_top, box_width = Inches(1.79), Inches(3.52), Inches(17.34)
            if os.path.exists(flower_icon_path):
                slide1.shapes.add_picture(flower_icon_path, box_left - Cm(1.2), box_top + Cm(0.15), Cm(0.8), Cm(0.8))

            sim_box = slide1.shapes.add_textbox(box_left, box_top, box_width, Inches(4.88))
            tf1 = sim_box.text_frame
            tf1.word_wrap = True

            r_s1 = tf1.paragraphs[0].add_run()
            r_s1.text = "Điểm giống nhau:"
            r_s1.font.name, r_s1.font.size, r_s1.font.bold = "Muli Bold", Pt(font_size_main), True
            
            # --- KIỂM TRA KIỂU DỮ LIỆU AN TOÀN ---
            if isinstance(sim_data, str):
                explanation_text = sim_data
                examples_list =[]
            else:
                explanation_text = sim_data.get("explanation", "")
                examples_list = sim_data.get("examples",[])

            p_s2 = tf1.add_paragraph()
            r_s2 = p_s2.add_run()
            r_s2.text = "• " + explanation_text.replace("\n", "\n• ")
            r_s2.font.name, r_s2.font.size = "Muli", Pt(font_size_main)

            if examples_list:
                p_s3 = tf1.add_paragraph()
                r_s3 = p_s3.add_run()
                r_s3.text = "Ví dụ:"
                r_s3.font.name, r_s3.font.size = "Muli", Pt(font_size_main)

                for ex in examples_list:
                    p_ex = tf1.add_paragraph()
                    r_ex = p_ex.add_run()
                    r_ex.text = f"+ {ex.get('hz', '')} /{ex.get('py', '')}/: {ex.get('vi', '')}"
                    r_ex.font.name, r_ex.font.size = "Muli", Pt(font_size_main)

        # =========================================================
        # SLIDE 2: ĐIỂM KHÁC NHAU (Khái quát)
        # =========================================================
        diff_ov_data = data.get("differences_overview", {})
        # Đảm bảo diff_ov_data là dict, nếu là chuỗi thì bỏ qua để tránh lỗi
        if diff_ov_data and isinstance(diff_ov_data, dict):
            slide2 = self._next_slide()
            draw_main_title(slide2)

            box_left, box_top, box_width = Inches(1.79), Inches(2.6), Inches(17.34)
            diff_explanations = diff_ov_data.get("explanations",[])
            
            full_diff_text = "Điểm khác nhau:\n" + "\n".join([f"• {item.get('word', '')}: {item.get('explanation', '')}" for item in diff_explanations])
            diff_height = max(Inches(2.5), Inches(self.get_text_height(full_diff_text, font_size_main, 17.34)))

            if os.path.exists(flower_icon_path):
                slide2.shapes.add_picture(flower_icon_path, box_left - Cm(1.2), box_top + Cm(0.15), Cm(0.8), Cm(0.8))

            diff_box = slide2.shapes.add_textbox(box_left, box_top, box_width, diff_height)
            tf2 = diff_box.text_frame
            tf2.word_wrap = True

            r_d1 = tf2.paragraphs[0].add_run()
            r_d1.text = "Điểm khác nhau:"
            r_d1.font.name, r_d1.font.size, r_d1.font.bold = "Muli Bold", Pt(font_size_main), True

            for item in diff_explanations:
                p = tf2.add_paragraph()
                p.space_before = Pt(6)
                r_word = p.add_run()
                r_word.text = f"• {item.get('word', '')}: "
                r_word.font.name, r_word.font.size, r_word.font.bold = "Muli Bold", Pt(font_size_main), True
                r_exp = p.add_run()
                r_exp.text = item.get('explanation', '')
                r_exp.font.name, r_exp.font.size = "Muli", Pt(font_size_main)

            examples = diff_ov_data.get("examples",[])
            if len(examples) > 0:
                img_w_h = Inches(2.5) 
                img_y = box_top + diff_height + Inches(0.2)
                txt_y = img_y + img_w_h + Inches(0.1) 
                
                col_width = (self.prs.slide_width / 914400.0) / len(examples)
                w_txt, h_txt = Inches(col_width - 0.5), Inches(1.8)
                
                for i, ex in enumerate(examples):
                    col_center = (i * col_width) + (col_width / 2.0)
                    l_img, l_txt = Inches(col_center) - (img_w_h / 2.0), Inches(col_center) - (w_txt / 2.0)

                    local_img = ex.get("local_image_path")
                    img_desc = ex.get("image_description", f"Mô tả ảnh {i+1}")
                    
                    if local_img and os.path.exists(local_img):
                        slide2.shapes.add_picture(local_img, l_img, img_y, img_w_h, img_w_h)
                    else:
                        img_box = slide2.shapes.add_textbox(l_img, img_y, img_w_h, img_w_h)
                        img_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
                        img_box.line.color.rgb = self.hex_to_rgb_color("CCCCCC")
                        self._set_text_exact_style(img_box, img_desc, font_name="Arial", font_size=14, color="999999", align="center")

                    txt_box = slide2.shapes.add_textbox(l_txt, txt_y, w_txt, h_txt)
                    tf_ex = txt_box.text_frame
                    tf_ex.word_wrap, tf_ex.vertical_anchor = True, MSO_ANCHOR.TOP
                    
                    p_hz = tf_ex.paragraphs[0]
                    r_hz = p_hz.add_run()
                    r_hz.text = ex.get('hz', '')
                    r_hz.font.name, r_hz.font.size = "字由点字云霆楷体", Pt(44)
                    p_hz.alignment = PP_ALIGN.CENTER

                    p_py = tf_ex.add_paragraph()
                    r_py = p_py.add_run()
                    r_py.text = f"/{ex.get('py', '')}/"
                    r_py.font.name, r_py.font.size = "Muli", Pt(27)
                    r_py.font.color.rgb = self.hex_to_rgb_color("545454")
                    p_py.alignment = PP_ALIGN.CENTER

                    p_vi = tf_ex.add_paragraph()
                    r_vi = p_vi.add_run()
                    r_vi.text = ex.get('vi', '')
                    r_vi.font.name, r_vi.font.size, r_vi.font.italic = "Muli Italics", Pt(31), True
                    r_vi.font.color.rgb = self.hex_to_rgb_color("A23131")
                    p_vi.alignment = PP_ALIGN.CENTER

        # =========================================================
        # SLIDE 3 (Và 4): CHI TIẾT ĐIỂM KHÁC NHAU & MẸO NHỚ
        # =========================================================
        # Bổ sung thêm ảnh do differences bây giờ cũng có local_image_path, image_description để tăng tính trực quan
        differences = data.get("differences",[])
        memory_tip = data.get("memory_tip", "")
        num_diffs = len(differences)

        if differences or memory_tip:
            slide3 = self._next_slide()
            draw_main_title(slide3)

            # --- 1. MẸO NHỚ ---
            tip_top = Inches(2.2)
            tip_height = Inches(0) 
            if memory_tip:
                tip_left, tip_width = Inches(2.62), Inches(15.42)
                est_tip_h = self.get_text_height(f"Mẹo nhớ: {memory_tip}", font_size_main, 15.42)
                tip_height = max(Inches(1.19), Inches(est_tip_h))

                if os.path.exists(flower_icon_path):
                    slide3.shapes.add_picture(flower_icon_path, tip_left - Cm(1.2), tip_top + Cm(0.15), Cm(0.8), Cm(0.8))

                tip_box = slide3.shapes.add_textbox(tip_left, tip_top, tip_width, tip_height)
                tf_tip = tip_box.text_frame
                tf_tip.word_wrap = True
                add_colon_bold_para(tf_tip, f"Mẹo nhớ: {memory_tip}")

            # --- HÀM BỔ TRỢ 4 ---
            def render_diff_detail_block(slide, diff_data, l_txt, t_txt, w_txt, h_txt, l_img, t_img, img_size):
                box = slide.shapes.add_textbox(l_txt, t_txt, w_txt, h_txt)
                tf = box.text_frame
                tf.word_wrap = True

                p_title = tf.paragraphs[0]
                run_title = p_title.add_run()
                run_title.text = f"{diff_data.get('word', '')} ({diff_data.get('pinyin', '')}):"
                run_title.font.name, run_title.font.size, run_title.font.bold = "Muli Bold", Pt(font_size_main), True

                for key in ['focus', 'context', 'word_type']:
                    val = diff_data.get(key)
                    if val:
                        add_colon_bold_para(tf, val, is_bullet=True)

                local_img = diff_data.get("local_image_path")
                img_desc = diff_data.get("image_description", "Mô tả ảnh")
                
                if local_img and os.path.exists(local_img):
                    slide.shapes.add_picture(local_img, l_img, t_img, img_size, img_size)
                else:
                    img_box = slide.shapes.add_textbox(l_img, t_img, img_size, img_size)
                    img_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
                    img_box.line.color.rgb = self.hex_to_rgb_color("CCCCCC")
                    self._set_text_exact_style(img_box, img_desc, font_name="Arial", font_size=14, color="999999", align="center")

            # --- 2. VẼ CHI TIẾT ---
            if num_diffs == 2:
                diff_top = max(Inches(4.05), tip_top + tip_height + Inches(0.2))
                w_txt, h_txt = Inches(9.28), Inches(4.27)
                img_size = Inches(2.6)
                
                txt_left_configs =[Inches(0.32), Inches(10.37)]
                img_top = diff_top + h_txt 

                for i, diff in enumerate(differences):
                    l_txt = txt_left_configs[i]
                    l_img = l_txt + (w_txt / 2.0) - (img_size / 2.0)
                    render_diff_detail_block(slide3, diff, l_txt, diff_top, w_txt, h_txt, l_img, img_top, img_size)

            elif num_diffs >= 3:
                w1_top = max(Inches(4.04), tip_top + tip_height + Inches(0.2))
                w_txt_1, h_txt_1 = Inches(15.42), Inches(3.5)
                img_size = Inches(2.6)
                l_img_1 = Inches(2.5) + (w_txt_1 / 2.0) - (img_size / 2.0) 
                img_top_1 = w1_top + h_txt_1
                
                render_diff_detail_block(slide3, differences[0], Inches(2.5), w1_top, w_txt_1, h_txt_1, l_img_1, img_top_1, img_size)

                slide4 = self._next_slide()
                draw_main_title(slide4)
                
                diff_top = Inches(3.5) 
                w_txt, h_txt = Inches(9.28), Inches(4.27)
                txt_left_configs =[Inches(0.32), Inches(10.37)]
                img_top = diff_top + h_txt

                for i, diff in enumerate(differences[1:3]):
                    l_txt = txt_left_configs[i]
                    l_img = l_txt + (w_txt / 2.0) - (img_size / 2.0)
                    render_diff_detail_block(slide4, diff, l_txt, diff_top, w_txt, h_txt, l_img, img_top, img_size)
    
    # ================================================================
    # FIXED SLIDES — edit in-place
    # ================================================================

    def add_cover_slide(self):
        """Slide [0] — edit in-place."""
        lesson = self.data.get("lesson_info", {})
        slide  = self.prs.slides[0]
        shapes = self._get_all_shapes(slide.shapes)

        title_shape    = self._find_shape_by_name(shapes, "TextBox 18")
        subtitle_shape = self._find_shape_by_name(shapes, "TextBox 30")

        if title_shape:
            # Chiều cao box template của bạn là ~2.78 inches (7.06cm)
            self._apply_title_styling(
                title_shape, lesson.get("title_cn", ""),
                max_font=135, min_font=75
            )
        if subtitle_shape:
            self._replace_subtitle_with_rounded_rect(
                slide, subtitle_shape,
                f"Bài Khóa - Bài {lesson.get('number', '')}",
                font_size=50
            )

    def add_table_of_content(self):
        """Slide [1] — edit in-place."""
        slide  = self.prs.slides[1]
        shapes = self._get_all_shapes(slide.shapes)

        left_shape  = self._find_shape_by_name(shapes, "TextBox 16")
        title_shape = self._find_shape_by_name(shapes, "TextBox 17")
        right_shape = self._find_shape_by_name(shapes, "TextBox 18")

        if left_shape:
            self._set_text_exact_style(left_shape,  "01. TỪ VỰNG", "Anton",  font_size=56, color="FCF1D4")
        if title_shape:
            self._set_text_exact_style(title_shape, "目录",                 font_size=90, color="B02012")
        if right_shape:
            self._set_text_exact_style(right_shape, "02. BÀI KHÓA", "Anton", font_size=56, color="FCF1D4")

    def add_end_slide(self):
        """Slide [40] — edit in-place."""
        lesson = self.data.get("lesson_info", {})
        slide  = self.prs.slides[40]
        shapes = self._get_all_shapes(slide.shapes)

        title_shape    = self._find_shape_by_name(shapes, "TextBox 10")
        subtitle_shape = self._find_shape_by_name(shapes, "TextBox 21")

        if title_shape:
            # Tương tự như slide cover, sử dụng min_font là 75
            self._apply_title_styling(
                title_shape, lesson.get("title_cn", ""),
                max_font=126, min_font=75
            )
        if subtitle_shape:
            self._replace_subtitle_with_rounded_rect(
                slide, subtitle_shape,
                f"Bài Khóa - Bài {lesson.get('number', '')}",
                font_size=50
            )

    # ================================================================
    # CONTENT SLIDES — Lập trình các hàm chèn nội dung vào đây
    # ================================================================

    def add_dialogue_slide(self, sec: dict, force_simple: bool = False):
        import re
        
        # 1. Lấy dữ liệu
        if force_simple:
            dialogue_data = sec.get("simple_dialogue")
            has_pinyin = False
        else:
            dialogue_data = sec.get("full_dialogue")
            has_pinyin = True

        if not dialogue_data: return  

        hz_list = dialogue_data.get("hz",[])
        py_list = dialogue_data.get("py", []) if has_pinyin else []
        vi_list = dialogue_data.get("vi",[])
        
        if len(hz_list) == 0: return

        import sys; base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        flower_icon_path = os.path.join(base_dir, "resources", "images", "ppt", "flower_point.png")
        section_title = sec.get("section_title", "Hội thoại")
        
        # 2. KIỂM TRA CHẾ ĐỘ: LÀ ĐOẠN VĂN HAY HỘI THOẠI?
        is_passage = "đoạn văn" in section_title.lower()

        if is_passage:
            # =========================================================
            # CHẾ ĐỘ: ĐOẠN VĂN (READING PASSAGE)
            # =========================================================
            def split_passage(text_list, lang='hz'):
                text = " ".join(text_list)
                if not text: return[]
                # Cắt theo dấu chấm kết thúc câu
                if lang == 'hz':
                    sents = re.split(r'([。！？\n])', text)
                else:
                    sents = re.split(r'([.!?]\s+|\n)', text)
                
                result, temp =[], ""
                for part in sents:
                    temp += part
                    if (lang=='hz' and re.search(r'[。！？\n]', part)) or (lang!='hz' and re.search(r'[.!?]\s+|\n', part)):
                        result.append(temp.strip())
                        temp = ""
                if temp.strip(): result.append(temp.strip())
                return[s for s in result if s]

            # Chia đoạn văn thành các câu để phân trang
            hz_sents = split_passage(hz_list, 'hz')
            py_sents = split_passage(py_list, 'py') if has_pinyin else[]
            vi_sents = split_passage(vi_list, 'vi')
            
            # Đồng bộ độ dài mảng (tránh lỗi nếu AI dịch thiếu/thừa câu)
            max_len = max(len(hz_sents), len(py_sents) if has_pinyin else 0, len(vi_sents))
            hz_sents += [""] * (max_len - len(hz_sents))
            if has_pinyin: py_sents += [""] * (max_len - len(py_sents))
            vi_sents += [""] * (max_len - len(vi_sents))

            # Giới hạn 3 câu / Slide để tránh tràn khung 5.47 inch
            MAX_SENTS = 3
            chunks = [ (hz_sents[i:i+MAX_SENTS], py_sents[i:i+MAX_SENTS] if has_pinyin else [], vi_sents[i:i+MAX_SENTS])
                       for i in range(0, max_len, MAX_SENTS) ]

            for chunk_idx, (chunk_hz, chunk_py, chunk_vi) in enumerate(chunks):
                slide = self._next_slide()

                # --- Vẽ Textbox/Ảnh Minh Họa ---
                img_desc = sec.get("image_description", "Mô tả ảnh")
                local_img = sec.get("local_image_path")
                img_w_h = Cm(7.31)
                
                # Tọa độ thay đổi tùy theo slide đầu tiên hay các slide tiếp theo của đoạn văn
                if chunk_idx == 0:
                    # Dịch ảnh sang trái khỏi vùng chữ
                    img_left, img_top = Inches(3.78) - Cm(7.31) - Cm(0.8), Cm(6.63)
                else:
                    img_left, img_top = Cm(21.28), Cm(20.52)
                    
                if local_img and os.path.exists(local_img):
                    slide.shapes.add_picture(local_img, img_left, img_top, img_w_h, img_w_h)
                else:
                    img_box = slide.shapes.add_textbox(img_left, img_top, img_w_h, img_w_h)
                    img_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
                    img_box.line.color.rgb = self.hex_to_rgb_color("CCCCCC")
                    self._set_text_exact_style(
                        img_box, img_desc, font_name="Arial", font_size=14, 
                        color="999999", align="center"
                    )

                # A. Vẽ Title
                title_width, title_height = Cm(20.14), Cm(2.67)
                title_left, title_top = (self.prs.slide_width - title_width) / 2, Cm(1.26)
                title_box = slide.shapes.add_textbox(title_left, title_top, title_width, title_height)
                title_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
                self._set_text_exact_style(title_box, section_title, font_name="Fraunces", font_size=57, color="FCF1D4", align="center")

                # B. Thông số Khung chứa Text (Dùng Inches theo yêu cầu)
                box_left = Inches(3.78)
                box_top = Inches(2.61)
                box_width = Inches(13.21)
                box_height = Inches(5.47) if has_pinyin else Inches(3.95)

                # Vẽ Icon hoa (Đặt ở Top-Left của đoạn văn)
                if os.path.exists(flower_icon_path):
                    icon_left = box_left - Cm(1.2)
                    icon_top = box_top + Pt(6) # Neo thẳng hàng với dòng chữ đầu tiên
                    slide.shapes.add_picture(flower_icon_path, icon_left, icon_top, Cm(0.8), Cm(0.8))

                textbox = slide.shapes.add_textbox(box_left, box_top, box_width, box_height)
                tf = textbox.text_frame
                tf.word_wrap = True
                tf.vertical_anchor = MSO_ANCHOR.TOP # Đoạn văn nên căn TOP cho tự nhiên
                tf.margin_top = tf.margin_bottom = tf.margin_left = tf.margin_right = 0

                # 1. Render Hán tự (Mỗi câu 1 dòng/paragraph)
                for hz_text in chunk_hz:
                    if not hz_text: continue
                    p = tf.add_paragraph() if len(tf.paragraphs[0].runs) > 0 else tf.paragraphs[0]
                    p.space_after = Pt(4)
                    run = p.add_run()
                    run.text = hz_text
                    run.font.name, run.font.size, run.font.bold = "字由点字典楷", Pt(38.4), True # 487680 EMU
                    run.font.color.rgb = self.hex_to_rgb_color("000000")

                # 2. Render Pinyin (Gộp chung thành 1 paragraph lớn bên dưới)
                if has_pinyin:
                    py_text = " ".join([p for p in chunk_py if p])
                    if py_text:
                        p = tf.add_paragraph()
                        p.space_before = Pt(14) # Cách xa khối HZ một chút
                        p.space_after = Pt(6)
                        p.line_spacing = Pt(30)
                        run = p.add_run()
                        run.text = py_text
                        run.font.name, run.font.size = "Muli", Pt(23.8) # 302641 EMU
                        run.font.color.rgb = self.hex_to_rgb_color("545454")

                # 3. Render Tiếng Việt (Gộp chung thành 1 paragraph lớn dưới cùng)
                vi_text = " ".join([v for v in chunk_vi if v])
                if vi_text:
                    p = tf.add_paragraph()
                    p.space_before = Pt(0) if has_pinyin else Pt(14)
                    p.line_spacing = Pt(30)
                    run = p.add_run()
                    run.text = vi_text
                    run.font.name, run.font.size = "Muli", Pt(23.8) # 302641 EMU
                    run.font.color.rgb = self.hex_to_rgb_color("A40400")

        else:
            # =========================================================
            # CHẾ ĐỘ: HỘI THOẠI NGẮN (DIALOGUE) - (Giữ nguyên code cũ)
            # =========================================================
            num_sentences = len(hz_list)
            chunks = [ (hz_list[i:i+6], py_list[i:i+6], vi_list[i:i+6]) for i in range(0, num_sentences, 6)]

            for chunk_idx, (chunk_hz, chunk_py, chunk_vi) in enumerate(chunks):
                slide = self._next_slide()
                num_items = len(chunk_hz)

                # --- Vẽ Textbox/Ảnh Minh Họa ---
                img_desc = sec.get("image_description", "Mô tả ảnh")
                local_img = sec.get("local_image_path")
                img_w_h = Cm(7.31)
                img_left, img_top = Cm(38.72), Cm(8.73)
                
                if local_img and os.path.exists(local_img):
                    slide.shapes.add_picture(local_img, img_left, img_top, img_w_h, img_w_h)
                else:
                    img_box = slide.shapes.add_textbox(img_left, img_top, img_w_h, img_w_h)
                    img_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
                    img_box.line.color.rgb = self.hex_to_rgb_color("CCCCCC")
                    self._set_text_exact_style(
                        img_box, img_desc, font_name="Arial", font_size=14, 
                        color="999999", align="center"
                    )

                # A. TITLE
                title_width, title_height = Cm(20.14), Cm(2.67)
                title_left, title_top = (self.prs.slide_width - title_width) / 2, Cm(1.26)
                title_box = slide.shapes.add_textbox(title_left, title_top, title_width, title_height)
                title_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
                self._set_text_exact_style(title_box, section_title, font_name="Fraunces", font_size=57, color="FCF1D4", align="center")

                # B. CONFIG DYNAMIC SPACING
                slide_width_cm = self.prs.slide_width / 360000.0 
                
                if num_items >= 5: 
                    start_left, start_top = 7.95, 5.56
                    box_width = slide_width_cm - start_left - 1.0 
                    box_height = 3.19  
                    hz_size, hz_font = 29.3, "字由点字典楷"  
                    py_size, py_font = 18.2, "Muli"         
                    vi_size, vi_font, vi_italic = 18.2, "Muli", False
                    y_step = 3.7 
                    line_spacing_val = Pt(28.5) 
                else: 
                    start_left, start_top = 11.95, 7.24
                    box_width = slide_width_cm - start_left - 1.5
                    box_height = 4.27  
                    hz_size, hz_font = 39.5, "字由点字典楷" 
                    py_size, py_font = 23.5, "Muli"         
                    vi_size, vi_font, vi_italic = 24.5, "Muli", True
                    y_step = 4.72 
                    line_spacing_val = Pt(33) 

                # C. RENDER
                line_spacing_cm = (line_spacing_val.pt / 72.0) * 2.54

                for i in range(num_items):
                    current_top = start_top + (i * y_step)
                    
                    offset = line_spacing_cm if has_pinyin else (line_spacing_cm * 0.5)
                    icon_top_val = current_top + (box_height / 2.0) - offset - 0.4
                    
                    if os.path.exists(flower_icon_path):
                        slide.shapes.add_picture(flower_icon_path, Cm(start_left - 1.2), Cm(icon_top_val), Cm(0.8), Cm(0.8))

                    textbox = slide.shapes.add_textbox(Cm(start_left), Cm(current_top), Cm(box_width), Cm(box_height))
                    tf = textbox.text_frame
                    tf.word_wrap = True
                    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
                    tf.margin_bottom = tf.margin_top = tf.margin_left = tf.margin_right = 0
                    
                    def add_para(text, font, size, color, is_bold=False, is_italic=False):
                        p = tf.add_paragraph() if len(tf.paragraphs[0].runs) > 0 else tf.paragraphs[0]
                        p.space_before = p.space_after = Pt(0)
                        p.line_spacing = line_spacing_val
                        run = p.add_run()
                        run.text = text
                        run.font.name, run.font.size, run.font.bold, run.font.italic = font, Pt(size), is_bold, is_italic
                        run.font.color.rgb = self.hex_to_rgb_color(color)

                    add_para(chunk_hz[i], hz_font, hz_size, "000000", is_bold=True)
                    if has_pinyin: add_para(chunk_py[i], py_font, py_size, "545454")
                    add_para(chunk_vi[i], vi_font, vi_size, "A40400", is_italic=vi_italic)

    def add_vocab_slides(self, sec: dict):
        """
        Sinh các slide Từ vựng. 3 từ vựng / 1 slide.
        Dữ liệu lấy từ slide content của template.
        """
        vocab_list = sec.get("vocabulary", [])
        if not vocab_list:
            return

        # 1. Chia cụm 3 từ / slide
        MAX_PER_SLIDE = 3
        chunks = [vocab_list[i : i + MAX_PER_SLIDE] for i in range(0, len(vocab_list), MAX_PER_SLIDE)]

        for chunk in chunks:
            # Lấy slide content tiếp theo từ template
            slide = self._next_slide()

            # ==========================================
            # A. TEXTBOX TITLE "Từ vựng"
            # ==========================================
            title_width = Cm(20.14)
            title_height = Cm(2.67)
            title_left = Cm(15.28)
            title_top = Cm(1.26)
            
            title_box = slide.shapes.add_textbox(title_left, title_top, title_width, title_height)
            title_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
            self._set_text_exact_style(
                title_box, "Từ vựng", font_name="Fraunces", font_size=57, 
                color="FCF1D4", bold=False, align="center"
            )

            # ==========================================
            # B. THÔNG SỐ VỊ TRÍ & BƯỚC NHẢY
            # ==========================================
            # Thông số Word Box (Cột trái)
            word_left = 2.86
            word_start_top = 6.71
            word_width = 8.69
            word_height = 5.54
            word_y_step = 6.73 # 13.44 - 6.71

            # Thông số Detail Box (Cột phải)
            detail_left = 15.28
            detail_start_top = 7.30
            # Chiều rộng động: slide_width - detail_left - lề phải (1cm)
            slide_width_cm = self.prs.slide_width / 360000.0
            detail_width = slide_width_cm - detail_left - 1.0
            detail_height = 4.59
            detail_y_step = 6.87 # 14.17 - 7.30

            # Màu sắc
            color_gray = "545454"
            color_red = "A40400"
            color_green = "29741D" # Màu xanh lá highlight
            color_black = "000000"

            import sys; base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            flower_icon_path = os.path.join(base_dir, "resources", "images", "ppt", "flower_point.png")

            # ==========================================
            # C. RENDER TỪNG TỪ VỰNG TRONG CHUNK
            # ==========================================
            for i, item in enumerate(chunk):
                # --- 1. Vẽ Word Box (Hán tự to bên trái) ---
                curr_word_top = word_start_top + (i * word_y_step)
                hz_text = item.get("hz", "")
                
                # Quyết định font size dựa trên độ dài từ
                hz_font_size = 116.5 if len(hz_text) < 4 else 94
                
                word_box = slide.shapes.add_textbox(
                    Cm(word_left), Cm(curr_word_top), Cm(word_width), Cm(word_height)
                )
                word_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
                self._set_text_exact_style(
                    word_box, hz_text, font_name="字由点字云霆楷体", 
                    font_size=hz_font_size, color=color_black, bold=False, align="center"
                )

                # --- 2. Vẽ Detail Box (Pinyin, Nghĩa, Ví dụ bên phải) ---
                curr_detail_top = detail_start_top + (i * detail_y_step)
                detail_box = slide.shapes.add_textbox(
                    Cm(detail_left), Cm(curr_detail_top), Cm(detail_width), Cm(detail_height)
                )
                tf = detail_box.text_frame
                tf.word_wrap = True
                # Tắt margin để text sát lề chuẩn
                tf.margin_top = tf.margin_bottom = tf.margin_left = tf.margin_right = 0

                # Paragraph 1: /pinyin/ (loại từ): nghĩa
                p1 = tf.paragraphs[0]
                p1.space_after = Pt(0)
                
                # Run: Pinyin (Xám)
                run_py = p1.add_run()
                run_py.text = f"/{item.get('pinyin', '')}/ "
                run_py.font.name = "Muli"
                run_py.font.size = Pt(32)
                run_py.font.color.rgb = self.hex_to_rgb_color(color_gray)
                
                # Run: Loại từ & Nghĩa (Đỏ)
                run_type_vi = p1.add_run()
                type_str = f"({item.get('type', '')}): " if item.get('type') else ""
                run_type_vi.text = f"{type_str}{item.get('vi', '')}"
                run_type_vi.font.name = "Muli"
                run_type_vi.font.size = Pt(32)
                run_type_vi.font.color.rgb = self.hex_to_rgb_color(color_red)

                # Lấy dữ liệu ví dụ
                example = item.get("example", {})
                ex_hz = example.get("hz", "")
                ex_py = example.get("py", "")
                ex_vi = example.get("vi", "")

                # Paragraph 2: VD: Hán tự /Pinyin/
                if ex_hz or ex_py:
                    p2 = tf.add_paragraph()
                    p2.space_after = Pt(0)
                    
                    # Run: Chữ "VD: " (Đen, Size 32)
                    run_vd = p2.add_run()
                    run_vd.text = "VD: "
                    run_vd.font.name = "Muli"
                    run_vd.font.size = Pt(32)
                    run_vd.font.color.rgb = self.hex_to_rgb_color(color_black)
                    
                    # Chèn Hán tự ví dụ (Highlight thẻ <hl>) - Size 32
                    self._add_hl_text(p2, ex_hz, "Muli", 32, color_black, color_green)
                    
                    # Chèn Pinyin ví dụ bọc trong dấu / / - Phải gán size cho cả dấu gạch
                    if ex_py:
                        # Dấu "/" mở đầu
                        run_slash_start = p2.add_run()
                        run_slash_start.text = " /"
                        run_slash_start.font.name = "Muli"
                        run_slash_start.font.size = Pt(32)
                        run_slash_start.font.color.rgb = self.hex_to_rgb_color(color_black)

                        # Pinyin chính (có highlight) - Size 32
                        self._add_hl_text(p2, ex_py, "Muli", 32, color_black, color_green)

                        # Dấu "/:" kết thúc
                        run_slash_end = p2.add_run()
                        run_slash_end.text = "/:"
                        run_slash_end.font.name = "Muli"
                        run_slash_end.font.size = Pt(32)
                        run_slash_end.font.color.rgb = self.hex_to_rgb_color(color_black)

                # Paragraph 3: Dịch nghĩa ví dụ (Đã có size 32 trong hàm _add_hl_text)
                if ex_vi:
                    p3 = tf.add_paragraph()
                    p3.space_after = Pt(0)
                    self._add_hl_text(p3, ex_vi, "Muli", 32, color_black, color_green)

    def add_extra_slide(self, sec: dict):
        """
        Hàm điều phối chính cho các slide Kiến thức mở rộng.
        """
        extra_data_list = sec.get("extra_knowledge", [])
        if not extra_data_list:
            return

        section_title = sec.get("section_title", "Kiến thức")

        for extra in extra_data_list:
            ex_type = extra.get("type")
            
            # Xử lý dạng vocab_list hoặc word_derivatives (dùng chung layout 4 cột)
            if ex_type == "vocab_list":
                data = extra.get("vocab_list", {})
                self._render_vocab_layout(
                    section_title, 
                    data.get("category_desc", ""), 
                    data.get("items", [])
                )
            elif ex_type == "word_derivatives":
                data = extra.get("word_derivatives", {})
                # Biến đổi dữ liệu word_derivatives thành cấu trúc giống vocab_list để tái sử dụng layout
                desc = f"“{data.get('root_word')}” ({data.get('pinyin')}): {data.get('meaning')}"
                self._render_vocab_layout(
                    section_title, 
                    desc, 
                    data.get("derived_words", [])
                )
            elif ex_type == "grammar_formula":
                data = extra.get("grammar_formula", {})
                self._render_grammar_formula_layout(section_title, data)
            elif ex_type == "grammar_advanced":
                data = extra.get("grammar_advanced", {})
                self._render_grammar_advanced_layout(section_title, data)
            elif ex_type == "word_comparison":
                data = extra.get("word_comparison", {})
                self._render_word_comparison_layout(section_title, data)            
            
    def add_exercise_slide(self, sec: dict):
        """
        Sinh các slide Luyện tập dựa trên mảng exercise trong JSON.
        Mỗi dạng bài tập (multiple_choice, true_false, fill_in_the_blanks) sẽ nằm trên 1 slide riêng.
        """
        exercises = sec.get("exercise", [])
        if not exercises:
            return

        for ex in exercises:
            ex_type = ex.get("type")
            slide = self._next_slide()

            # ==========================================
            # A. TEXTBOX TITLE "Luyện tập"
            # ==========================================
            title_width, title_height = Cm(20.14), Cm(2.67)
            title_left, title_top = (self.prs.slide_width - title_width) / 2, Cm(1.26)
            
            title_box = slide.shapes.add_textbox(title_left, title_top, title_width, title_height)
            title_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
            self._set_text_exact_style(
                title_box, "Luyện tập", font_name="Fraunces", font_size=57, 
                color="FCF1D4", bold=False, align="center"
            )

            def add_ex_para(text, is_bold=False, color="000000"):
                p = tf.add_paragraph() if len(tf.paragraphs[0].runs) > 0 else tf.paragraphs[0]
                p.space_after = Pt(9) # Khoảng cách giữa các dòng bài tập
                run = p.add_run()
                run.text = text
                run.font.name = "Muli Bold" if is_bold else "Muli"
                run.font.size = Pt(main_font_size)
                run.font.bold = is_bold
                run.font.color.rgb = self.hex_to_rgb_color(color)
                return p

            # ==========================================
            # B. KHUNG NỘI DUNG CHÍNH (Textbox chung cho cả 3 dạng)
            # ==========================================
            box_left = Inches(2.71)
            box_top = Inches(3.81)      # Đẩy box lên trên để tận dụng khoảng trống
            box_width = Inches(15.07)
            box_height = Inches(5)   # Tăng chiều cao box để chứa được nhiều nội dung hơn

            textbox = slide.shapes.add_textbox(box_left, box_top, box_width, box_height)
            tf = textbox.text_frame
            tf.word_wrap = True
            tf.vertical_anchor = MSO_ANCHOR.TOP # Bài tập thường bắt đầu từ trên xuống
            tf.margin_top = tf.margin_bottom = tf.margin_left = tf.margin_right = 0

            # Giảm nhẹ font size và khoảng cách dòng để đảm bảo không bị tràn chữ
            main_font_size = 28
            color_black = "000000"
            color_red = "A40400"
            color_green = "29741D" # Màu xanh lá (dành cho chữ Hán ví dụ)

            import sys; base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            flower_icon_path = os.path.join(base_dir, "resources", "images", "ppt", "flower_point.png")


            # ==========================================
            # C. XỬ LÝ THEO TỪNG DẠNG BÀI TẬP
            # ==========================================
            
            # 1. DẠNG TRẮC NGHIỆM (Multiple Choice)
            if ex_type == "multiple_choice":
                data = ex.get("multiple_choice", {})
                # Dòng 1: Câu hỏi:
                add_ex_para("Câu hỏi: ", is_bold=True)
                
                # Dòng 2: Nội dung câu hỏi (có thể kèm pinyin)
                q_text = data.get("question", "")
                # Nếu câu hỏi là dạng hội thoại 2 lượt lời thì tách thành 2 dòng để dễ đọc
                # Nếu có B: trong câu hỏi thì tách theo đó,
                if "B:" in q_text:
                    parts = q_text.split("B:", 1)
                    q_text = parts[0].strip() + "\nB: " + parts[1].strip()
                add_ex_para(q_text, is_bold=True)

                # Dòng 3, 4, 5...: Các đáp án
                options = data.get("options", [])
                correct_label = data.get("answer", "") # VD: "A"
                
                for opt in options:
                    label = opt.get("label", "")
                    hz = opt.get("hz", "")
                    py = opt.get("py", "")
                    
                    # Format: A. Hán tự /pinyin/
                    opt_line = f"{label}. {hz}"
                    if py: opt_line += f" /{py}/"
                    
                    # Nếu nhãn trùng với đáp án đúng thì tô đỏ
                    txt_color = color_red if label == correct_label else color_black
                    add_ex_para(opt_line, is_bold=False, color=txt_color)

            # 2. DẠNG ĐIỀN VÀO CHỖ TRỐNG (Fill in the blanks)
            elif ex_type == "fill_in_the_blanks":
                data = ex.get("fill_in_the_blanks", {})
                # Dòng 1: Yêu cầu
                add_ex_para(data.get("instruction", "Điền các từ sau vào chỗ trống:"), is_bold=True)
                
                # Dòng 2: Danh sách từ cho sẵn
                words_line = ", ".join(data.get("given_words", []))
                add_ex_para(words_line, is_bold=True)

                # Dòng 3...: Các câu hỏi
                for item in data.get("sentences", []):
                    add_ex_para(item.get("full_sentence", ""), is_bold=False)

            # 3. DẠNG ĐÚNG SAI (True/False)
            elif ex_type == "true_false":
                data = ex.get("true_false", {})
                # Dòng 1: Phán đoán đúng sai + Câu nhận định
                statement = f"Phán đoán đúng sai: {data.get('statement', '')}"
                add_ex_para(statement, is_bold=True)

                # Dòng 2: Hiển thị Đúng hoặc Sai
                ans_text = "Đúng" if data.get("answer") is True else "Sai"
                add_ex_para(ans_text, is_bold=False)

        # Tự động căn lại width height cua textbox để nội dung nằm cân trong text box
        # Lưu ý: Không nên căn lại font size vì có thể gây tràn nếu nội dung quá dài, chỉ căn chỉnh vị trí để đẹp hơn
        for shape in slide.shapes:
            if shape.has_text_frame:
                self._auto_fit_text(shape)            

    # ================================================================
    # BUILD & SAVE
    # ================================================================

    def build(self):
        """
        Build toàn bộ presentation theo thứ tự:
        [0] cover → [1] TOC → [2..39] dialogue/vocab/extra/exercise × n → [40] end
        """
        self.add_cover_slide()
        self.add_table_of_content()

        for sec in self.data["sections"]:
            # --- Phần 1: Hội thoại (Có Pinyin) ---
            self.add_dialogue_slide(sec, force_simple=False)
            
            # --- Phần 2: Từ vựng (3 từ/slide) ---
            self.add_vocab_slides(sec)
            
            # --- Phần 3: Kiến thức liên quan ---
            self.add_extra_slide(sec) 
            
            # --- Phần 4: Hội thoại (KHÔNG Pinyin) ---
            self.add_dialogue_slide(sec, force_simple=True)
            
            # --- Phần 5: Luyện tập ---
            self.add_exercise_slide(sec)

        # [TODO: Gọi các hàm vẽ nội dung (dialogue, vocab...) ở đây]

        self.add_end_slide()

        # Xóa các slide content thừa (từ _slide_cursor đến 39)
        # Lưu ý: Cần xóa ngược từ dưới lên để không làm sai lệch index của các slide còn lại
        for i in range(39, self._slide_cursor - 1, -1):
            rId = self.prs.slides._sldIdLst[i].rId
            self.prs.part.drop_rel(rId)
            del self.prs.slides._sldIdLst[i]

        used = self._slide_cursor - 2
        print(f"✅ Đã dùng {used} / 38 slide content "
              f"(index 2–{self._slide_cursor - 1}). "
              f"Đã xóa {38 - used} slide thừa.")

    def save(self, output_path: str):
        self.prs.save(output_path)
        print(f"✅ Saved: {output_path}")

# ================================================================
# MAIN
# ================================================================
if __name__ == "__main__":
    import sys; base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # template_path = os.path.join(base_dir, "resources", "ppt_templates", "HSK1 Bài Khóa template.pptx")
    # json_path     = os.path.join(base_dir, "hsk_ppt", "HSK2_BK_test_output.json")
    template_path = r"D:\Edmicro\Tools\create_hsk\dist\resources\ppt_templates\HSK Bài Khóa template.pptx"
    json_path = r"D:\Edmicro\Tools\create_hsk\dist\output\ppt_hsk\Bài 1_她请我们吃了北京烤鸭_bk.json"
    output_path   = os.path.join(base_dir, "hsk_ppt", "HSK2_BK_test_output.pptx")

    gen = PPTGenerator(template_path, json_path)
    gen.build()
    gen.save(output_path)
