import json
import math
import os
import re
import sys
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Pt, Inches, Cm
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE

class GrammarPPTGenerator:
    def __init__(self, template_path: str, json_path: str):
        self.prs = Presentation(template_path)

        with open(json_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

        # Cấu trúc Template Ngữ Pháp:
        #   [0]      → add_cover_slide()        (edit in-place)
        #   [1]      → add_table_of_content()   (Tạo động nhiều textbox mục lục)
        #   [2..N]   → Các slide tiêu đề chủ điểm (Sẽ được move đến vị trí tương ứng)
        #   [N+1..M] → Các slide content (lấy tuần tự qua _next_slide())
        #   [M+1]    → add_end_slide()          (edit in-place, nằm cuối cùng)

        # Đếm số lượng chủ điểm ngữ pháp
        self.grammar_points = self.data.get("grammar_points", [])
        self.MAX_TITLE_SLIDES = 5
        # Giới hạn số lượng chủ điểm tối đa bằng với số slide tiêu đề template có sẵn
        self.grammar_points = self.grammar_points[:self.MAX_TITLE_SLIDES]
        self.num_topics = len(self.grammar_points)
        
        # Con trỏ slide content (Bỏ qua Bìa [0], Mục lục [1], và 5 Slide Tiêu đề [2..6])
        self.first_content_idx = 2 + self.MAX_TITLE_SLIDES
        self._slide_cursor = self.first_content_idx

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
        """Trả về slide tiếp theo trong vùng content, tự tăng cursor."""
        # Trừ đi slide kết thúc (cuối cùng)
        max_idx = len(self.prs.slides) - 2 
        idx = self._slide_cursor
        if idx > max_idx:
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
            return 0.65 # Tăng hệ số cho ký tự Latinh để trừ hao font Muli

        total_lines = 0
        for raw_line in str(text).split("\n"):
            if raw_line.strip() == "":
                total_lines += 1
                continue
            line_units = sum(char_units(c) for c in raw_line)
            # Hệ số 1.15 để trừ hao việc word wrap (xuống dòng ở khoảng trắng)
            total_lines += max(1, math.ceil((line_units * 1.15) / units_per_line))

        line_height_pt  = font_size * 1.3
        total_height_pt = total_lines * line_height_pt + 12 # cộng thêm margin bù
        return (total_height_pt / 72)

    def _apply_title_styling(self, shape, text: str, max_font=135, min_font=40):
        if not text:
            return
        tf = shape.text_frame
        tf.word_wrap = False
        shape_width_pt = shape.width / 12700.0
        shape_height_pt = shape.height / 12700.0
        margin_left = tf.margin_left / 12700.0 if tf.margin_left is not None else 7.2
        margin_right = tf.margin_right / 12700.0 if tf.margin_right is not None else 7.2
        margin_top = tf.margin_top / 12700.0 if tf.margin_top is not None else 3.6
        margin_bottom = tf.margin_bottom / 12700.0 if tf.margin_bottom is not None else 3.6
        available_width_pt = shape_width_pt - margin_left - margin_right
        available_height_pt = shape_height_pt - margin_top - margin_bottom
        
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
            max_font_by_width = (available_width_pt / units) * 0.95 
            max_font_by_height = available_height_pt * 0.90 
            calculated_font = min(max_font_by_width, max_font_by_height)
            optimal_font = int(min(max_font, max(min_font, calculated_font)))

        self._set_text_exact_style(shape, text, font_size=optimal_font, color="B51F09", align="center")

    def _replace_subtitle_with_rounded_rect(self, slide, old_shape, text: str, font_size: int = 50):
        center_x = old_shape.left + old_shape.width / 2.0
        center_y = old_shape.top + old_shape.height / 2.0
        est_width_in = len(text) * (font_size * 0.4 / 72) + 2
        new_width = int(Inches(est_width_in))
        new_height = int(Inches(1.2))  
        new_left = int(center_x - new_width / 2.0)
        new_top = int(center_y - new_height / 2.0)
        
        old_element = old_shape._element
        old_element.getparent().remove(old_element)
        
        new_shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, new_left, new_top, new_width, new_height)
        new_shape.adjustments[0] = 0.5 
        new_shape.fill.solid()
        new_shape.fill.fore_color.rgb = RGBColor(0xB5, 0x1F, 0x09)
        new_shape.line.fill.background()
        
        tf = new_shape.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        self._set_text_exact_style(new_shape, text, font_size=font_size, color="FFFFFF", align="center")
        self._bring_to_front(new_shape)

    def _move_slide(self, slide_index, new_index):
        """Di chuyển một slide từ vị trí slide_index sang new_index bằng cách can thiệp vào XML"""
        xml_slides = self.prs.slides._sldIdLst
        slides = list(xml_slides)
        if 0 <= slide_index < len(slides) and 0 <= new_index < len(slides):
            xml_slides.remove(slides[slide_index])
            xml_slides.insert(new_index, slides[slide_index])

    # ================================================================
    # FIXED SLIDES — edit in-place
    # ================================================================

    def add_cover_slide(self):
        """Slide [0] — Bìa bài học"""
        lesson = self.data.get("lesson_info", {})
        slide  = self.prs.slides[0]
        shapes = self._get_all_shapes(slide.shapes)

        title_shape    = self._find_shape_by_name(shapes, "TextBox 18")
        subtitle_shape = self._find_shape_by_name(shapes, "TextBox 30")

        if title_shape:
            self._apply_title_styling(title_shape, lesson.get("title_cn", ""), max_font=135, min_font=75)
        if subtitle_shape:
            self._replace_subtitle_with_rounded_rect(
                slide, subtitle_shape,
                f"Ngữ Pháp - Bài {lesson.get('number', '')}",
                font_size=50
            )

    def add_table_of_content(self):
        """
        Slide [1] — Mục lục. Tự động dàn dọc các textbox theo số lượng grammar_points.
        """
        slide  = self.prs.slides[1]
        shapes = self._get_all_shapes(slide.shapes)
        title_shape = self._find_shape_by_name(shapes, "TextBox 17")
        if title_shape:
            self._set_text_exact_style(title_shape, "目录", font_size=90, color="B02012")

        # Xóa các TextBox phụ gốc (VD TextBox 16, TextBox 18) nếu có
        for shape_name in ["TextBox 16", "TextBox 18"]:
            shape = self._find_shape_by_name(shapes, shape_name)
            if shape:
                sp = shape._element
                sp.getparent().remove(sp)

        # Tính toán để dàn các Item ra giữa màn hình
        num_items = self.num_topics
        if num_items == 0: return

        # Kích thước mặc định của khung ảnh TOC (dùng cho 4 hoặc 5 chủ điểm)
        default_box_w, default_box_h = Cm(19.25), Cm(5.3)
        default_box_left = Cm(15.56)
        
        # Đường dẫn tới file ảnh khung (Sẽ báo lỗi nếu chưa có)
        base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        img_path = os.path.join(base_dir, "resources", "images", "ppt", "title_box_image.png")
        print(f"Đang kiểm tra ảnh TOC tại: {img_path}")
        has_img = os.path.exists(img_path)
        print(f"Ảnh TOC tồn tại: {has_img}")

        # Cấu hình riêng cho từng trường hợp số lượng chủ điểm
        if num_items == 4:
            start_top = Cm(4.6)
            step_y = Cm(5.03)
            box_w, box_h, box_left = default_box_w, default_box_h, default_box_left
            f_size = 30
        elif num_items == 3:
            start_top = Cm(6.5)
            step_y = Cm(6.5)
            # Khung to hơn, nên đẩy lùi left sang trái khoảng (20.32 - 19.25)/2 = 0.53 cm để giữ cân giữa
            box_w, box_h = Cm(20.32), Cm(5.79)
            box_left = Cm(15.56 - 0.53) 
            f_size = 32
        elif num_items == 2:
            start_top = Cm(8.0)
            step_y = Cm(8.0)
            # Dùng size to cho 2 chủ điểm để nhìn hoành tráng
            box_w, box_h = Cm(20.32), Cm(5.79)
            box_left = Cm(15.56 - 0.53)
            f_size = 50
        elif num_items == 1:
            start_top = Cm(11.6)
            step_y = Cm(0)
            box_w, box_h = Cm(20.32), Cm(5.79)
            box_left = Cm(15.56 - 0.53)
            f_size = 50
        else: # Dự phòng cho 5 items
            start_top = Cm(3.5)
            step_y = Cm(4.5)
            box_w, box_h, box_left = default_box_w, default_box_h, default_box_left
            f_size = 30

        for i, point in enumerate(self.grammar_points):
            curr_top = start_top + (i * step_y)
            text_val = f"{i+1:02d} {point.get('grammar_name', '').upper()}"
            
            # 1. Chèn khung ảnh
            if has_img:
                slide.shapes.add_picture(img_path, box_left, curr_top, box_w, box_h)
            else:
                # Fallback nền đỏ nếu không thấy ảnh
                bg = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, box_left, curr_top, box_w, box_h)
                bg.fill.solid()
                bg.fill.fore_color.rgb = RGBColor(0xB5, 0x1F, 0x09)
                bg.line.fill.background()
            
            # 2. Chèn TextBox đè lên khung ảnh
            # Đặt khít bằng khung để dễ căn Center/Middle, dùng margin lùi text vào để không đè lên mây
            box = slide.shapes.add_textbox(box_left, curr_top, box_w, box_h)
            tf = box.text_frame
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf.word_wrap = True
            
            # Canh lề trái phải (Margin) để text lọt lòng vùng màu đỏ
            tf.margin_left = Cm(1.5)
            tf.margin_right = Cm(1.5)
            tf.margin_top = Cm(0.5)
            tf.margin_bottom = Cm(0.5)

            # Font size động theo cấu hình (Auto_fit shape)
            tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
            
            self._set_text_exact_style(box, text_val, font_name="Anton", font_size=f_size, color="FCF1D4", align="center")

    def edit_section_title_slides(self):
        """
        Chỉnh sửa text cho các Slide Tiêu đề (nằm ở Index 2 đến 1+MAX_TITLE_SLIDES).
        Sau này các slide này sẽ được di chuyển xen kẽ vào đầu mỗi nội dung.
        """
        for i, point in enumerate(self.grammar_points):
            slide_idx = 2 + i
            slide = self.prs.slides[slide_idx]
            shapes = self._get_all_shapes(slide.shapes)
            
            # Xóa các shape TextBox (nếu có sẵn từ template) để tránh đụng độ
            for shape_name in ["TextBox 17", "TextBox 16"]:
                shape = self._find_shape_by_name(shapes, shape_name)
                if shape:
                    sp = shape._element
                    sp.getparent().remove(sp)

            # Tính toán độ dài từ (tách theo khoảng trắng cho Tiếng Việt)
            title_text = point.get("grammar_name", "").strip()
            words = title_text.split()
            word_count = len(words)

            # Cấu hình kích thước textbox trung tâm mặc định
            box_w = Cm(17.35) 
            box_h = Cm(3.87)
            
            # Kích thước khung gốc (Dựa vào width 17.35, left 16.72 tức là căn phải một chút)
            # Center X của textbox gốc là: 16.72 + (17.35/2) = 25.395 cm
            center_x = Cm(25.395)
            center_y = Cm(10.83 + (3.87/2)) # = 12.765 cm

            # Logic điều chỉnh Width và Font size: Ưu tiên giảm font size thay vì xuống dòng.
            # Chỉ cho phép xuống dòng nếu có 6 chữ trở lên
            if word_count < 6:
                # Dưới 6 chữ: Tuyệt đối không xuống dòng. Cho phép box dài ra 22 cm (gần hết slide).
                box_w = Cm(22.0)
                allow_wrap = False
                
                # Giảm font size dần đều nếu ký tự quá dài để vừa 1 dòng
                char_count = len(title_text)
                if char_count < 20:
                    f_size = 81.7
                elif char_count < 30:
                    f_size = 70.0
                else:
                    f_size = 60.0
            else:
                # 6 chữ trở lên: Cho phép xuống dòng (tối đa 2 dòng). Width mở rộng chút xíu.
                box_w = Cm(20.0) 
                allow_wrap = True
                f_size = 70.0 # Bắt đầu ở size nhỏ hơn để tránh dòng 2 bị tràn

            # Tính lại Left, Top để Textbox vẫn căn giữa tọa độ center ban đầu dù Width đã thay đổi
            box_left = center_x - (box_w / 2)
            box_top = center_y - (box_h / 2)
            
            box = slide.shapes.add_textbox(box_left, box_top, box_w, box_h)
            tf = box.text_frame
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf.word_wrap = allow_wrap
            tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE

            # Màu đỏ Primary của Slide bìa (Hex B51F09)
            self._set_text_exact_style(
                box, title_text, 
                font_name="Anton", font_size=f_size, color="B51F09", align="center"
            )
                
        # Xóa các slide tiêu đề thừa nếu số lượng chủ điểm < MAX_TITLE_SLIDES
        for i in range(self.MAX_TITLE_SLIDES - 1, self.num_topics - 1, -1):
            slide_idx = 2 + i
            rId = self.prs.slides._sldIdLst[slide_idx].rId
            self.prs.part.drop_rel(rId)
            del self.prs.slides._sldIdLst[slide_idx]
            
    def add_end_slide(self):
        """Slide Cuối cùng — edit in-place."""
        lesson = self.data.get("lesson_info", {})
        # Lấy slide cuối cùng
        last_idx = len(self.prs.slides) - 1
        slide  = self.prs.slides[last_idx]
        shapes = self._get_all_shapes(slide.shapes)

        title_shape    = self._find_shape_by_name(shapes, "TextBox 10")
        subtitle_shape = self._find_shape_by_name(shapes, "TextBox 21")

        if title_shape:
            self._apply_title_styling(title_shape, lesson.get("title_cn", ""), max_font=126, min_font=75)
        if subtitle_shape:
            self._replace_subtitle_with_rounded_rect(
                slide, subtitle_shape,
                f"Ngữ Pháp - Bài {lesson.get('number', '')}",
                font_size=50
            )

    def _add_hl_text(self, paragraph, text, default_font, default_size, default_color, hl_color="29741D"):
        parts = re.split(r'(<hl>.*?</hl>)', text)
        for part in parts:
            run = paragraph.add_run()
            if part.startswith('<hl>') and part.endswith('</hl>'):
                run.text = part[4:-5]
                run.font.bold = True
                run.font.color.rgb = self.hex_to_rgb_color(hl_color)
            else:
                run.text = part
                run.font.bold = False
                run.font.color.rgb = self.hex_to_rgb_color(default_color)
            run.font.name = default_font
            run.font.size = Pt(default_size)

    def _render_multiple_choice_layout(self, data):
        slide = self._next_slide()
        title_width, title_height = Cm(20.14), Cm(2.67)
        title_left, title_top = (self.prs.slide_width - title_width) / 2, Cm(1.26)
        title_box = slide.shapes.add_textbox(title_left, title_top, title_width, title_height)
        title_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        self._set_text_exact_style(title_box, "Luyện tập", font_name="Fraunces", font_size=57, color="FCF1D4", bold=False, align="center")

        box_left, box_top, box_width, box_height = Inches(2.71), Inches(3.81), Inches(15.07), Inches(5)
        textbox = slide.shapes.add_textbox(box_left, box_top, box_width, box_height)
        tf = textbox.text_frame
        tf.word_wrap, tf.vertical_anchor = True, MSO_ANCHOR.TOP
        tf.margin_top = tf.margin_bottom = tf.margin_left = tf.margin_right = 0
        
        main_font_size = 36 
        color_black, color_red = "000000", "A40400"

        def add_ex_para(text, is_bold=False, color="000000"):
            p = tf.add_paragraph() if len(tf.paragraphs[0].runs) > 0 else tf.paragraphs[0]
            p.space_after = Pt(9) 
            run = p.add_run()
            run.text = text
            run.font.name = "Muli Bold" if is_bold else "Muli"
            run.font.size, run.font.bold = Pt(main_font_size), is_bold
            run.font.color.rgb = self.hex_to_rgb_color(color)

        add_ex_para("Câu hỏi: ", is_bold=True)
        q_text = data.get("question", "")
        if "B:" in q_text:
            parts = q_text.split("B:", 1)
            q_text = parts[0].strip() + "\nB: " + parts[1].strip()
        add_ex_para(q_text, is_bold=True)

        options = data.get("options", [])
        correct_label = data.get("answer", "") 
        for opt in options:
            label, hz, py = opt.get("label", ""), opt.get("hz", ""), opt.get("py", "")
            opt_line = f"{label}. {hz}"
            if py: opt_line += f" /{py}/"
            txt_color = color_red if label == correct_label else color_black
            add_ex_para(opt_line, is_bold=False, color=txt_color)
            
        self._auto_fit_text(textbox)

    def _render_true_false_layout(self, data):
        slide = self._next_slide()
        title_width, title_height = Cm(20.14), Cm(2.67)
        title_left, title_top = (self.prs.slide_width - title_width) / 2, Cm(1.26)
        title_box = slide.shapes.add_textbox(title_left, title_top, title_width, title_height)
        title_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        self._set_text_exact_style(title_box, "Luyện tập", font_name="Fraunces", font_size=57, color="FCF1D4", bold=False, align="center")

        box_left, box_top, box_width, box_height = Inches(2.71), Inches(3.81), Inches(15.07), Inches(5)
        textbox = slide.shapes.add_textbox(box_left, box_top, box_width, box_height)
        tf = textbox.text_frame
        tf.word_wrap, tf.vertical_anchor = True, MSO_ANCHOR.TOP
        tf.margin_top = tf.margin_bottom = tf.margin_left = tf.margin_right = 0
        main_font_size = 36 

        def add_ex_para(text, is_bold=False):
            p = tf.add_paragraph() if len(tf.paragraphs[0].runs) > 0 else tf.paragraphs[0]
            p.space_after = Pt(9) 
            run = p.add_run()
            run.text = text
            run.font.name = "Muli Bold" if is_bold else "Muli"
            run.font.size, run.font.bold = Pt(main_font_size), is_bold
            run.font.color.rgb = self.hex_to_rgb_color("000000")

        statement = f"Phán đoán đúng sai: {data.get('statement', '')}"
        add_ex_para(statement, is_bold=True)
        ans_text = "Đúng" if data.get("answer") is True else "Sai"
        add_ex_para(ans_text, is_bold=False)
        
        self._auto_fit_text(textbox)

    def _render_fill_in_the_blanks_layout(self, data):
        slide = self._next_slide()
        title_width, title_height = Cm(20.14), Cm(2.67)
        title_left, title_top = (self.prs.slide_width - title_width) / 2, Cm(1.26)
        title_box = slide.shapes.add_textbox(title_left, title_top, title_width, title_height)
        title_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        self._set_text_exact_style(title_box, "Luyện tập", font_name="Fraunces", font_size=57, color="FCF1D4", bold=False, align="center")

        box_left, box_top, box_width, box_height = Inches(2.71), Inches(3.81), Inches(15.07), Inches(5)
        textbox = slide.shapes.add_textbox(box_left, box_top, box_width, box_height)
        tf = textbox.text_frame
        tf.word_wrap, tf.vertical_anchor = True, MSO_ANCHOR.TOP
        tf.margin_top = tf.margin_bottom = tf.margin_left = tf.margin_right = 0
        main_font_size = 36 

        def add_ex_para(text, is_bold=False):
            p = tf.add_paragraph() if len(tf.paragraphs[0].runs) > 0 else tf.paragraphs[0]
            p.space_after = Pt(9) 
            run = p.add_run()
            run.text = text
            run.font.name = "Muli Bold" if is_bold else "Muli"
            run.font.size, run.font.bold = Pt(main_font_size), is_bold
            run.font.color.rgb = self.hex_to_rgb_color("000000")

        add_ex_para(data.get("instruction", "Điền các từ sau vào chỗ trống:"), is_bold=True)
        words_line = ", ".join(data.get("given_words", []))
        add_ex_para(words_line, is_bold=True)

        for item in data.get("sentences", []):
            add_ex_para(item.get("full_sentence", ""), is_bold=False)
            
        self._auto_fit_text(textbox)

    # ================================================================
    # CONTENT SLIDES — Lập trình các hàm chèn nội dung vào đây
    # ================================================================

    def add_grammar_content_slide(self, point: dict):
        """
        Xử lý render các thành phần của điểm ngữ pháp (structures, notes, exercises).
        """
        section_title = point.get("grammar_name", "")
        structures = point.get("structures", [])
        notes = point.get("notes", [])
        exercises = point.get("exercises", [])

        # Định nghĩa path ảnh hoa
        # Define base directory correctly by walking up from this script
        base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        flower_icon_path = os.path.join(base_dir, "resources", "images", "ppt", "flower_point.png")

        # --- 1. RENDER STRUCTURES (CẤU TRÚC/CÁCH DÙNG/VÍ DỤ) ---
        for struct in structures:
            slide = self._next_slide()
            
            # 1. Vẽ Tiêu đề phụ (VD: Dạng khẳng định)
            title_width, title_height = Cm(20.14), Cm(2.67)
            title_left, title_top = (self.prs.slide_width - title_width) / 2, Cm(1.26)
            title_box = slide.shapes.add_textbox(title_left, title_top, title_width, title_height)
            title_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
            
            sub_title_text = struct.get("sub_title", section_title)
            # Tính toán font size theo độ dài text
            char_count = len(sub_title_text)
            f_size = 57
            allow_wrap = False
            if char_count > 25:
                f_size = 38
                allow_wrap = True
            elif char_count > 15:
                f_size = 48
                allow_wrap = True
                
            title_box.text_frame.word_wrap = allow_wrap
            title_box.text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE

            self._set_text_exact_style(
                title_box, sub_title_text, 
                font_name="Fraunces", font_size=f_size, color="FCF1D4", align="center"
            )

            # 2. Textbox: Cấu trúc (Formula)
            box_left = Inches(2.61)
            formula_top = Inches(2.2)
            box_width = Inches(15.27)
            font_size_main = 32

            formula_text = struct.get("formula", "").strip()
            est_h_form = self.get_text_height(f"Cấu Trúc:\n{formula_text}", font_size_main, 15.27) if formula_text else 0
            h_form = max(Inches(1.0), Inches(est_h_form))

            if formula_text:
                if os.path.exists(flower_icon_path):
                    slide.shapes.add_picture(flower_icon_path, box_left - Cm(1.2), formula_top + Cm(0.15), Cm(0.8), Cm(0.8))
                
                f_box = slide.shapes.add_textbox(box_left, formula_top, box_width, h_form)
                tf_f = f_box.text_frame
                tf_f.word_wrap = True
                
                p_f1 = tf_f.paragraphs[0]
                p_f1.space_after = Pt(2)
                r_f1 = p_f1.add_run()
                r_f1.text = "Cấu Trúc: "
                r_f1.font.name, r_f1.font.size, r_f1.font.bold = "Muli Bold", Pt(font_size_main), True
                r_f1.font.color.rgb = self.hex_to_rgb_color("000000")
                
                p_f2 = tf_f.add_paragraph()
                r_f2 = p_f2.add_run()
                r_f2.text = formula_text
                r_f2.font.name, r_f2.font.size, r_f2.font.bold = "Muli Bold", Pt(font_size_main), True
                r_f2.font.color.rgb = self.hex_to_rgb_color("A40400") # Màu đỏ cho công thức

            # 3. Textbox: Cách dùng (Usage)
            usage_text = struct.get("usage", "").strip()
            usage_top = formula_top + h_form + Inches(0.15) if formula_text else formula_top
            
            est_h_use = self.get_text_height(f"Cách dùng: {usage_text}", font_size_main, 15.27) if usage_text else 0
            # Nới lỏng max height để đảm bảo text không bị tràn ra ngoài textbox nếu có nhiều dòng
            h_use = max(Inches(1.0), Inches(est_h_use))

            if usage_text:
                if os.path.exists(flower_icon_path):
                    slide.shapes.add_picture(flower_icon_path, box_left - Cm(1.2), usage_top + Cm(0.15), Cm(0.8), Cm(0.8))
                    
                u_box = slide.shapes.add_textbox(box_left, usage_top, box_width, h_use)
                tf_u = u_box.text_frame
                tf_u.word_wrap = True
                # Để textbox tự động điều chỉnh nếu text bị thừa ra
                tf_u.auto_size = MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT
                
                p_u = tf_u.paragraphs[0]
                r_u1 = p_u.add_run()
                r_u1.text = "Cách dùng: "
                r_u1.font.name, r_u1.font.size, r_u1.font.bold = "Muli Bold", Pt(font_size_main), True
                r_u1.font.color.rgb = self.hex_to_rgb_color("000000")
                
                r_u2 = p_u.add_run()
                r_u2.text = usage_text
                r_u2.font.name, r_u2.font.size = "Muli", Pt(font_size_main)
                r_u2.font.color.rgb = self.hex_to_rgb_color("000000")

            # 4. Textbox: Ví dụ (Trái) & Ảnh (Phải)
            examples = struct.get("examples", [])
            if examples:
                ex_top = usage_top + h_use + Inches(0.2)
                # Chia đôi không gian: Text (trái), Hình (phải)
                txt_w, txt_h = Inches(10), Inches(3.0)
                img_size = Inches(2.8)
                img_l = box_left + txt_w + Inches(0.5) # Khoảng cách 0.5 inch
                
                # Bóc ví dụ đầu tiên để render
                ex = examples[0]
                
                txt_box = slide.shapes.add_textbox(box_left, ex_top, txt_w, txt_h)
                tf_ex = txt_box.text_frame
                tf_ex.word_wrap = True
                tf_ex.vertical_anchor = MSO_ANCHOR.MIDDLE

                # P1: Hán tự (39.5pt)
                p_hz = tf_ex.paragraphs[0]
                self._add_hl_text(p_hz, ex.get('hz', ''), "字由点字云霆楷体", 39.5, "000000", "29741D")
                
                # P2: Pinyin (24.6pt)
                p_py = tf_ex.add_paragraph()
                self._add_hl_text(p_py, f"/{ex.get('py', '')}/", "Muli", 24.6, "545454", "29741D")
                
                # P3: Tiếng Việt (24.6pt, Màu Đỏ)
                p_vi = tf_ex.add_paragraph()
                self._add_hl_text(p_vi, ex.get('vi', ''), "Muli Italics", 24.6, "A23131", "29741D")

                # Box Ảnh (Bên phải)
                # Căn giữa theo chiều dọc của Textbox Ví dụ:
                img_t = ex_top + (txt_h / 2.0) - (img_size / 2.0)
                
                local_img = ex.get("local_image_path")
                img_desc = ex.get("image_description", "Mô tả ảnh")
                
                if local_img and os.path.exists(local_img):
                    slide.shapes.add_picture(local_img, img_l, img_t, img_size, img_size)
                else:
                    img_box = slide.shapes.add_textbox(img_l, img_t, img_size, img_size)
                    img_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
                    img_box.line.color.rgb = self.hex_to_rgb_color("CCCCCC") 
                    self._set_text_exact_style(
                        img_box, img_desc, font_name="Arial", font_size=14, color="999999", align="center"
                    )

        # --- 2. RENDER NOTES (LƯU Ý QUAN TRỌNG) ---
        if notes:
            slide = self._next_slide()
            
            # Tiêu đề phụ (Bê lại tên chủ điểm)
            title_width, title_height = Cm(20.14), Cm(2.67)
            title_left, title_top = (self.prs.slide_width - title_width) / 2, Cm(1.26)
            title_box = slide.shapes.add_textbox(title_left, title_top, title_width, title_height)
            title_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
            
            # Tính toán font size theo độ dài text
            char_count = len(section_title)
            f_size = 57
            allow_wrap = False
            if char_count > 25:
                f_size = 38
                allow_wrap = True
            elif char_count > 15:
                f_size = 48
                allow_wrap = True
                
            title_box.text_frame.word_wrap = allow_wrap
            title_box.text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE

            self._set_text_exact_style(
                title_box, section_title, 
                font_name="Fraunces", font_size=f_size, color="FCF1D4", align="center"
            )

            box_left, box_top = Inches(2.61), Inches(2.5)
            box_width, box_height = Inches(15.27), Inches(5.0)
            
            note_box = slide.shapes.add_textbox(box_left, box_top, box_width, box_height)
            tf_n = note_box.text_frame
            tf_n.word_wrap = True
            
            p_n_title = tf_n.paragraphs[0]
            p_n_title.space_after = Pt(12)
            run_n_title = p_n_title.add_run()
            run_n_title.text = "Lưu ý quan trọng:"
            run_n_title.font.name, run_n_title.font.size, run_n_title.font.bold = "Muli Bold", Pt(38), True
            run_n_title.font.color.rgb = self.hex_to_rgb_color("000000")

            for note_str in notes:
                p_n = tf_n.add_paragraph()
                p_n.space_after = Pt(6)
                
                # In đậm cụm từ trước dấu hai chấm
                if ":" in note_str:
                    parts = note_str.split(":", 1)
                    r1 = p_n.add_run()
                    r1.text = f"• {parts[0]}:"
                    r1.font.name, r1.font.size, r1.font.bold = "Muli Bold", Pt(32), True
                    
                    r2 = p_n.add_run()
                    r2.text = parts[1]
                    r2.font.name, r2.font.size, r2.font.bold = "Muli", Pt(32), False
                else:
                    r = p_n.add_run()
                    r.text = f"• {note_str}"
                    r.font.name, r.font.size, r.font.bold = "Muli", Pt(32), False

        # --- 3. RENDER EXERCISES (BÀI TẬP) ---
        for ex in exercises:
            ex_type = ex.get("type")
            if ex_type == "multiple_choice":
                self._render_multiple_choice_layout(ex.get("multiple_choice", {}))
            elif ex_type == "true_false":
                self._render_true_false_layout(ex.get("true_false", {}))
            elif ex_type == "fill_in_the_blanks":
                self._render_fill_in_the_blanks_layout(ex.get("fill_in_the_blanks", {}))

    # ================================================================
    # BUILD & SAVE
    # ================================================================

    def build(self):
        """
        Build toàn bộ presentation.
        Luồng:
        1. Bìa & Mục lục
        2. Sửa text 5 Slide Tiêu đề (Nằm sẵn ở index 2,3,4,5,6) và xóa slide thừa.
        3. Duyệt qua từng chủ điểm ngữ pháp:
            - Bốc 1 Slide Tiêu đề tương ứng (từ trên đầu) di chuyển (move_slide) đến vị trí cursor hiện tại.
            - Gọi hàm add_grammar_content_slide để sinh các slide content.
        4. Dọn dẹp slide thừa.
        5. Xử lý slide cuối.
        """
        self.add_cover_slide()
        self.add_table_of_content()
        self.edit_section_title_slides()

        # Cập nhật lại con trỏ sau khi xóa slide tiêu đề thừa
        self.first_content_idx = 2 + self.num_topics
        self._slide_cursor = self.first_content_idx

        # Lưu lại danh sách vị trí gốc của các Slide Tiêu đề (vd: 2)
        # Chúng ta sẽ rút dần từ index 2 (Vì khi rút 1 slide, các slide sau sẽ dồn lên index 2)
        section_slide_pool_idx = 2

        for point in self.grammar_points:
            # 1. Bốc slide tiêu đề (đang nằm ở index 2) di chuyển xuống vị trí cursor hiện tại
            # Lưu ý: Hàm _move_slide(old_idx, new_idx). Khi ta di chuyển slide 2 xuống dưới (vd index 8), 
            # slide 3 cũ sẽ tự động trồi lên thành index 2.
            
            start_content_idx = self._slide_cursor
            
            # --- Sinh content ---
            self.add_grammar_content_slide(point)
            # -------------------------------
            
            # 2. Di chuyển slide tiêu đề (đang đợi ở vị trí section_slide_pool_idx)
            # đến vị trí bắt đầu của cụm content này.
            self._move_slide(section_slide_pool_idx, start_content_idx - 1)
            
            # Không cần tăng cursor ở hàm move, vì số lượng tổng slide trước cursor không đổi,
            # chỉ là đảo vị trí. Nhưng ta cần bù trừ 1 khoảng cho cursor vì slide tiêu đề đã chiếm 1 slot.
            # (Thực chất con trỏ _slide_cursor tự động chạy theo hàm _next_slide trong add_grammar_content_slide)

        # 3. Dọn dẹp các slide content thừa (Tương tự code bài khóa)
        last_slide_idx = len(self.prs.slides) - 1
        for i in range(last_slide_idx - 1, self._slide_cursor - 1, -1):
            rId = self.prs.slides._sldIdLst[i].rId
            self.prs.part.drop_rel(rId)
            del self.prs.slides._sldIdLst[i]

        # 4. Sửa slide cuối (Lúc này đã bị dồn lên sát cursor)
        self.add_end_slide()

        used = self._slide_cursor - self.first_content_idx
        print(f"✅ Đã dùng {used} slide content.")

    def save(self, output_path: str):
        self.prs.save(output_path)
        print(f"✅ Saved: {output_path}")

# ================================================================
# MAIN
# ================================================================
if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_path = os.path.join(base_dir, "resources", "ppt_templates", "HSK1 Ngữ pháp template.pptx")
    # json_path     = os.path.join(base_dir, "hsk_ppt", "HSK2_Grammar_test_output.json")
    json_path = r"E:\Edmicro\create_hsk\output\ppt_hsk\Bài 1 我们去机场接你们_grammar.json"
    output_path   = os.path.join(base_dir, "hsk_ppt", "HSK2_Grammar_generated.pptx")

    gen = GrammarPPTGenerator(template_path, json_path)
    gen.build()
    gen.save(output_path)
