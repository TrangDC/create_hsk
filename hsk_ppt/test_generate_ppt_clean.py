import json
import math
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Pt, Inches
from pptx.enum.text import PP_ALIGN


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

    def _apply_title_styling(self, shape, text: str, max_font=135, min_font=75):
        """
        Căn chỉnh font-size tự động để title dài vừa vặn trên 1 dòng
        và không bị vượt quá chiều rộng của khung Textbox.
        """
        # Đảm bảo chữ luôn nằm trên 1 dòng bằng cách cấm wrap text
        tf = shape.text_frame
        tf.word_wrap = False
        
        # Chiều rộng tối đa của Textbox (tính bằng inch)
        max_width_inch = shape.width / 914400.0 # 1 inch = 914400 EMUs
        
        # Hàm tính toán bề rộng của text dựa trên font size (tương tự logic trong get_text_height)
        def _get_text_width_inch(text: str, font_size: int) -> float:
            char_width_inch = (font_size * 0.6) / 72.0 # 1 point = 1/72 inch
            
            units = 0.0
            for ch in text:
                cp = ord(ch)
                # Ký tự CJK full-width tính là 1 unit, các ký tự Latinh/số tính 0.5 unit
                if (0x4E00 <= cp <= 0x9FFF or
                    0x3000 <= cp <= 0x303F or
                    0xFF00 <= cp <= 0xFFEF or
                    0x3040 <= cp <= 0x30FF):
                    units += 1.0
                else:
                    units += 0.5
            
            return units * char_width_inch

        # Tìm font size tối ưu nhất bằng cách thử lùi dần từ max_font xuống min_font
        optimal_font = max_font
        for fs in range(max_font, min_font - 1, -1):
            est_width = _get_text_width_inch(text, fs)
            # Nếu bề rộng ước tính nhỏ hơn hoặc bằng bề rộng khung shape
            # (trừ hao đi 5% margin an toàn) thì chọn font này
            if est_width <= (max_width_inch * 0.95):
                optimal_font = fs
                break
        else:
            # Nếu vòng lặp chạy hết mà không break (text quá dài kể cả với min_font)
            optimal_font = min_font

        self._set_text_exact_style(
            shape, text, font_size=optimal_font, color="B51F09", align="center"
        )

    def _replace_subtitle_with_rounded_rect(self, slide, old_shape, text: str, font_size: int = 50):
        """Thay thế textbox cũ bằng khối bo tròn màu đỏ có chữ trắng căn giữa."""
        from pptx.enum.shapes import MSO_SHAPE
        from pptx.enum.text import MSO_ANCHOR
        
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

    def add_dialogue_slide(self, sec: dict):
        pass

    def add_vocab_slides(self, sec: dict):
        pass

    def add_extra_slide(self, extra: dict):
        pass

    def add_exercise_slide(self, sec: dict):
        pass

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
    template_path = r"D:\Edmicro\Tools\create_hsk\hsk_ppt\template\HSK1 Bài Khóa template.pptx"
    json_path     = r"D:\Edmicro\Tools\create_hsk\hsk_ppt\test_output_json.json"
    output_path   = r"D:\Edmicro\Tools\create_hsk\hsk_ppt\test_output_baikhoa_new.pptx"

    gen = PPTGenerator(template_path, json_path)
    gen.build()
    gen.save(output_path)
