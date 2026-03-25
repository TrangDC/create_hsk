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
            self._set_text_exact_style(
                title_shape, lesson.get("title_cn", ""),
                font_size=135, color="B51F09"
            )
        if subtitle_shape:
            self._set_text_exact_style(
                subtitle_shape,
                f"Bài Khóa - Bài {lesson.get('number', '')}",
                font_size=50, color="B51F09"
            )

    def add_table_of_content(self):
        """Slide [1] — edit in-place."""
        slide  = self.prs.slides[1]
        shapes = self._get_all_shapes(slide.shapes)

        left_shape  = self._find_shape_by_name(shapes, "TextBox 16")
        title_shape = self._find_shape_by_name(shapes, "TextBox 17")
        right_shape = self._find_shape_by_name(shapes, "TextBox 18")

        if left_shape:
            self._set_text_exact_style(left_shape,  "01. TỪ VỰNG",  font_size=56, color="FCF1D4")
        if title_shape:
            self._set_text_exact_style(title_shape, "目录",           font_size=90, color="B02012")
        if right_shape:
            self._set_text_exact_style(right_shape, "02. BÀI KHÓA", font_size=56, color="FCF1D4")

    def add_end_slide(self):
        """Slide [40] — edit in-place."""
        lesson = self.data.get("lesson_info", {})
        slide  = self.prs.slides[40]
        shapes = self._get_all_shapes(slide.shapes)

        title_shape    = self._find_shape_by_name(shapes, "TextBox 10")
        subtitle_shape = self._find_shape_by_name(shapes, "TextBox 21")

        if title_shape:
            self._set_text_exact_style(
                title_shape, lesson.get("title_cn", ""), font_size=126
            )
        if subtitle_shape:
            self._set_text_exact_style(
                subtitle_shape,
                f"Bài Khóa - Bài {lesson.get('number', '')}",
                font_size=50
            )

    # ================================================================
    # CONTENT SLIDES — lấy tuần tự từ index 2 qua _next_slide()
    # ================================================================

    # def add_dialogue_slide(self, sec: dict):
    #     """
    #     Mỗi page 3 dòng = 1 slide lấy từ template.
    #     Thêm textbox title + các dòng hz/py/vi lên slide đó.
    #     """
    #     dialogue = sec.get("full_dialogue", {})
    #     hz_lines = dialogue.get("hz", "").split("\n")
    #     py_lines = dialogue.get("py", "").split("\n")
    #     vi_lines = dialogue.get("vi", "").split("\n")

    #     n = len(hz_lines)
    #     if n == 0:
    #         return

    #     if n <= 3:
    #         BASE_FHZ, BASE_FPY, BASE_FVI = 44, 28, 28
    #     elif n == 4:
    #         BASE_FHZ, BASE_FPY, BASE_FVI = 40, 26, 26
    #     else:
    #         BASE_FHZ, BASE_FPY, BASE_FVI = 36, 24, 24

    #     ROWS_PER_SLIDE = 3
    #     pages       = [hz_lines[i:i+ROWS_PER_SLIDE] for i in range(0, n, ROWS_PER_SLIDE)]
    #     line_offset = 0

    #     for page_idx, page_lines in enumerate(pages):
    #         slide  = self._next_slide()
    #         shapes = self._get_all_shapes(slide.shapes)
    #         title_shape = self._find_shape_by_name(shapes, "TextBox 17")
    #         n_rows = len(page_lines)

    #         title = sec.get("section_title", "")
    #         if len(pages) > 1:
    #             title += f" ({page_idx+1}/{len(pages)})"

    #         # self.add_text(
    #         #     slide, title,
    #         #     1, 0.6, 8, 1,
    #         #     font_size=22, bold=True, color="FCF1D4", align="center"
    #         # )
    #         self._set_text_exact_style(title_shape, title,font_size=56.7, color="FCF1D4")

    #         fhz = BASE_FHZ - (3 - n_rows) * 2
    #         fpy = BASE_FPY - (3 - n_rows) * 2
    #         fvi = BASE_FVI - (3 - n_rows) * 2

    #         start_top = 2.2
    #         gap       = 1.8

    #         for j in range(n_rows):
    #             global_i = line_offset + j
    #             hz = hz_lines[global_i] if global_i < len(hz_lines) else ""
    #             py = py_lines[global_i] if global_i < len(py_lines) else ""
    #             vi = vi_lines[global_i] if global_i < len(vi_lines) else ""

    #             box = slide.shapes.add_textbox(
    #                 Inches(1),
    #                 Inches(start_top + j * gap),
    #                 Inches(8),
    #                 Inches(1.5)
    #             )
    #             self._bring_to_front(box)
    #             tf = box.text_frame
    #             tf.clear()

    #             p1 = tf.paragraphs[0]
    #             p1.alignment = PP_ALIGN.CENTER
    #             r1 = p1.add_run()
    #             r1.text = hz
    #             r1.font.size = Pt(fhz)
    #             r1.font.bold = True
    #             r1.font.name = "字由点字典楷 Bold"
    #             # r1.font.color.rgb = ""
    #             r1.font.color.rgb = self.hex_to_rgb_color("000000")

    #             p2 = tf.add_paragraph()
    #             p2.alignment = PP_ALIGN.CENTER
    #             r2 = p2.add_run()
    #             r2.text = py
    #             r2.font.size = Pt(fpy)
    #             r2.font.name = "Muli"
    #             # r2.font.color.rgb = RGBColor(84, 84, 84)
    #             r2.font.color.rgb = self.hex_to_rgb_color("545454")

    #             p3 = tf.add_paragraph()
    #             p3.alignment = PP_ALIGN.CENTER
    #             r3 = p3.add_run()
    #             r3.text = vi
    #             r3.font.size = Pt(fvi)
    #             r3.font.italic = True
    #             r3.font.name  = "Muli Italics"
    #             r3.font.color.rgb = RGBColor(164, 4, 0)
    #             r3.font.color.rgb = self.hex_to_rgb_color("A40400")

    #         line_offset += n_rows

    def add_dialogue_slide(self, sec: dict):
        """
        Toàn bộ dialogue luôn nằm trong 1 slide duy nhất.
        Layout left-aligned, tự điều chỉnh font size theo số dòng.
        """
        dialogue = sec.get("full_dialogue", {})
        hz_lines = dialogue.get("hz", "").split("\n")
        py_lines = dialogue.get("py", "").split("\n")
        vi_lines = dialogue.get("vi", "").split("\n")

        n = len(hz_lines)
        if n == 0:
            return

        # ── Font size tự co theo số dòng ──────────────────────────────────
        # Mỗi dòng chiếm: fhz-line + fpy-line + fvi-line + spacing
        # Slide content height ~ 5.5 inch (từ top=1.8 đến bottom=7.0)
        if n <= 2:
            BASE_FHZ, BASE_FPY, BASE_FVI = 44, 26, 26
        elif n == 3:
            BASE_FHZ, BASE_FPY, BASE_FVI = 38, 24, 24
        elif n == 4:
            BASE_FHZ, BASE_FPY, BASE_FVI = 33, 21, 21
        elif n == 5:
            BASE_FHZ, BASE_FPY, BASE_FVI = 28, 18, 18
        else:
            BASE_FHZ, BASE_FPY, BASE_FVI = 24, 15, 15

        # ── Tính layout động ───────────────────────────────────────────────
        CONTENT_TOP    = 1.75   # inch – ngay dưới title bar
        CONTENT_BOTTOM = 7.0    # inch – sát đáy slide (slide cao 7.5")
        CONTENT_HEIGHT = CONTENT_BOTTOM - CONTENT_TOP  # 5.25"

        # Mỗi group (hz+py+vi) chiếm bao nhiêu inch?
        # ước lượng: pt → inch  (1 pt = 1/72 inch), thêm leading
        LEADING = 1.18  # hệ số dãn dòng
        group_h = (BASE_FHZ + BASE_FPY + BASE_FVI) / 72 * LEADING
        gap     = (CONTENT_HEIGHT - group_h * n) / (n + 1)   # khoảng cách đều
        gap     = max(gap, 0.08)  # tối thiểu 0.08"

        # ── Lấy slide & shapes ────────────────────────────────────────────
        slide  = self._next_slide()
        shapes = self._get_all_shapes(slide.shapes)
        title_shape = self._find_shape_by_name(shapes, "TextBox 17")

        # Title
        title = sec.get("section_title", "")
        self._set_text_exact_style(title_shape, title, font_size=56.7, color="FCF1D4")

        # ── Vẽ từng dòng thoại ────────────────────────────────────────────
        LEFT   = 1.05   # inch – canh lề trái (sau icon bullet ~0.8")
        WIDTH  = 8.2    # inch

        for j in range(n):
            hz = hz_lines[j] if j < len(hz_lines) else ""
            py = py_lines[j] if j < len(py_lines) else ""
            vi = vi_lines[j] if j < len(vi_lines) else ""

            top = CONTENT_TOP + gap + j * (group_h + gap)
            box_h = group_h + 0.05  # thêm chút buffer

            box = slide.shapes.add_textbox(
                Inches(LEFT),
                Inches(top),
                Inches(WIDTH),
                Inches(box_h)
            )
            self._bring_to_front(box)

            tf = box.text_frame
            tf.word_wrap = False   # tránh wrap bất ngờ
            tf.clear()

            # ── Dòng 1: Hán tự ──
            p1 = tf.paragraphs[0]
            p1.alignment = PP_ALIGN.LEFT
            p1.space_after = Pt(2)
            r1 = p1.add_run()
            r1.text = hz
            r1.font.size = Pt(BASE_FHZ)
            r1.font.bold = True
            r1.font.name = "字由点字典楷 Bold"
            r1.font.color.rgb = self.hex_to_rgb_color("000000")

            # ── Dòng 2: Pinyin ──
            p2 = tf.add_paragraph()
            p2.alignment = PP_ALIGN.LEFT
            p2.space_after = Pt(1)
            r2 = p2.add_run()
            r2.text = py
            r2.font.size = Pt(BASE_FPY)
            r2.font.name = "Muli"
            r2.font.color.rgb = self.hex_to_rgb_color("545454")

            # ── Dòng 3: Tiếng Việt ──
            p3 = tf.add_paragraph()
            p3.alignment = PP_ALIGN.LEFT
            r3 = p3.add_run()
            r3.text = vi
            r3.font.size = Pt(BASE_FVI)
            r3.font.italic = True
            r3.font.name = "Muli Italics"
            r3.font.color.rgb = self.hex_to_rgb_color("A40400")

    def add_vocab_slides(self, sec: dict):
        """
        Tối đa 3 từ / slide.
        Layout mỗi hàng: HZ to bên trái | pinyin / loại / nghĩa / ví dụ bên phải.
        Số slide cần = ceil(len(vocab) / 3), lấy tuần tự từ template.
        """
        vocab = sec.get("vocabulary", [])
        if not vocab:
            return

        SLIDE_HEIGHT_IN = 7.5
        HEADER_BOTTOM   = 1.5
        BOTTOM_MARGIN   = 0.2
        USABLE_HEIGHT   = SLIDE_HEIGHT_IN - HEADER_BOTTOM - BOTTOM_MARGIN
        MAX_PER_SLIDE   = 3

        def _add_header(slide):
            tag = slide.shapes.add_shape(
                1, Inches(0.4), Inches(0.4), Inches(5), Inches(0.85)
            )
            tag.fill.solid()
            tag.fill.fore_color.rgb = self.primary_red
            tag.line.fill.background()
            tf = tag.text_frame
            tf.text = "Từ vựng"
            p = tf.paragraphs[0]
            p.font.size      = Pt(28)
            p.font.bold      = True
            p.font.name      = "Arial"
            p.font.color.rgb = RGBColor(255, 255, 255)
            p.alignment      = PP_ALIGN.CENTER

        pages = [vocab[i:i + MAX_PER_SLIDE] for i in range(0, len(vocab), MAX_PER_SLIDE)]

        for page_words in pages:
            slide      = self._next_slide()
            _add_header(slide)

            row_height = USABLE_HEIGHT / MAX_PER_SLIDE
            han_font   = max(36, min(72, int(row_height * 38)))
            text_font  = max(16, min(24, int(row_height * 14)))

            COLOR_MAP = [
                RGBColor(240, 220, 180),   # dòng 0: pinyin/loại/nghĩa — kem
                RGBColor(200, 200, 200),   # dòng 1: ví dụ HZ — xám sáng
                RGBColor(160, 160, 160),   # dòng 2: ví dụ VI — xám nhạt
            ]

            for i, word in enumerate(page_words):
                y            = HEADER_BOTTOM + i * row_height
                row_center_y = y + row_height * 0.05

                # Cột trái: HZ
                self.add_text(
                    slide, word.get("hz", ""),
                    0.2, row_center_y, 3.5, row_height * 0.85,
                    font_size=han_font, bold=True, align="center"
                )

                # Cột phải: pinyin / loại / nghĩa / ví dụ
                content_lines = []
                pinyin    = word.get("pinyin", "")
                word_type = word.get("type", "")
                vi        = word.get("vi", "")
                content_lines.append(f"/{pinyin}/  ({word_type})  :  {vi}")

                ex = word.get("example", {})
                if ex:
                    content_lines.append(f"VD: {ex.get('hz', '')}  /{ex.get('py', '')}/")
                    if ex.get("vi"):
                        content_lines.append(ex.get("vi", ""))

                box = slide.shapes.add_textbox(
                    Inches(4.0), Inches(row_center_y),
                    Inches(8.8), Inches(row_height * 0.85)
                )
                self._bring_to_front(box)
                tf = box.text_frame
                tf.word_wrap     = True
                tf.auto_size     = None
                tf.margin_top    = Pt(4)
                tf.margin_bottom = Pt(2)
                tf.margin_left   = Pt(4)

                for idx, line in enumerate(content_lines):
                    p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
                    run = p.add_run()
                    run.text           = line
                    run.font.size      = Pt(text_font)
                    run.font.bold      = (idx == 0)
                    run.font.italic    = (idx == 2)
                    run.font.name      = "Arial"
                    run.font.color.rgb = COLOR_MAP[min(idx, 2)]

    def add_extra_slide(self, extra: dict):
        """
        Kiến thức mở rộng.
        Tự lấy thêm slide tiếp theo từ template nếu nội dung tràn trang.
        Layout: Header đỏ → Tiêu đề → Nội dung → Ví dụ (hz / py / vi).
        """
        SLIDE_HEIGHT  = 7.5
        SLIDE_WIDTH   = 13.33
        MARGIN_BOTTOM = 0.3
        MAX_Y         = SLIDE_HEIGHT - MARGIN_BOTTOM
        TITLE_BOTTOM  = 1.0
        CONTENT_X     = 0.8
        CONTENT_W     = SLIDE_WIDTH - CONTENT_X - 0.5
        EXAMPLE_X     = 1.0
        EXAMPLE_W     = SLIDE_WIDTH - EXAMPLE_X - 0.5

        def _setup_slide():
            slide = self._next_slide()
            # Header tag đỏ
            tag = slide.shapes.add_shape(
                1, Inches(0.4), Inches(0.3), Inches(4), Inches(0.65)
            )
            tag.fill.solid()
            tag.fill.fore_color.rgb = self.primary_red
            tag.line.fill.background()
            tf = tag.text_frame
            tf.text = "Kiến thức thêm"
            p = tf.paragraphs[0]
            p.font.size      = Pt(20)
            p.font.bold      = True
            p.font.name      = "Arial"
            p.font.color.rgb = RGBColor(255, 255, 255)
            p.alignment      = PP_ALIGN.CENTER
            # Tiêu đề
            self.add_text(
                slide, extra.get("title", ""),
                0.5, 1.05, SLIDE_WIDTH - 1.0, 0.7,
                font_size=28, bold=True, color="FCF1D4", align="left"
            )
            return slide

        slide = _setup_slide()

        # Nội dung chính
        content_text = extra.get("content", "")
        content_h    = self.get_text_height(content_text, 22, CONTENT_W)
        self.add_text(
            slide, content_text,
            CONTENT_X, TITLE_BOTTOM + 0.75, CONTENT_W, content_h,
            font_size=22, color="FFFFFF", align="left"
        )

        y = TITLE_BOTTOM + 0.75 + content_h + 0.25

        # Ví dụ — lấy slide tiếp theo nếu tràn
        for ex in extra.get("examples", []):
            hz = ex.get("hz", "")
            py = ex.get("py", "")
            vi = ex.get("vi", "")
            if not hz and not vi:
                continue

            txt     = "\n".join(filter(None, [hz, py, vi]))
            block_h = self.get_text_height(txt, 20, EXAMPLE_W) + 0.1

            if y + block_h > MAX_Y:
                slide = _setup_slide()
                y     = TITLE_BOTTOM + 0.75

            box = slide.shapes.add_textbox(
                Inches(EXAMPLE_X), Inches(y),
                Inches(EXAMPLE_W), Inches(block_h)
            )
            self._bring_to_front(box)
            tf = box.text_frame
            tf.word_wrap = True
            tf.clear()

            def _ex_para(tf_, text_, fsize, bold_, italic_, rgb, is_first):
                p_ = tf_.paragraphs[0] if is_first else tf_.add_paragraph()
                p_.alignment = PP_ALIGN.LEFT
                r_ = p_.add_run()
                r_.text           = text_
                r_.font.size      = Pt(fsize)
                r_.font.bold      = bold_
                r_.font.italic    = italic_
                r_.font.name      = "Arial"
                r_.font.color.rgb = rgb

            if hz:
                _ex_para(tf, hz, 24, True,  False, RGBColor(245, 220, 150), True)
            if py:
                _ex_para(tf, py, 18, False, True,  RGBColor(160, 160, 160), not hz)
            if vi:
                _ex_para(tf, vi, 20, False, True,  RGBColor(210, 210, 210), not hz and not py)

            y += block_h + 0.2

    def add_exercise_slide(self, sec: dict):
        """
        Bài tập trắc nghiệm.
        Layout: Header đỏ → Câu hỏi → A/B/C/D dọc (hz + py) → Đáp án đúng.
        """
        ex = sec.get("exercise", {})
        if not ex:
            return

        slide = self._next_slide()

        # Header tag
        tag = slide.shapes.add_shape(
            1, Inches(0.4), Inches(0.3), Inches(3.5), Inches(0.65)
        )
        tag.fill.solid()
        tag.fill.fore_color.rgb = self.primary_red
        tag.line.fill.background()
        tf_tag = tag.text_frame
        tf_tag.text = "Luyện tập"
        p_tag = tf_tag.paragraphs[0]
        p_tag.font.size      = Pt(22)
        p_tag.font.bold      = True
        p_tag.font.name      = "Arial"
        p_tag.font.color.rgb = RGBColor(255, 255, 255)
        p_tag.alignment      = PP_ALIGN.CENTER

        # Câu hỏi
        self.add_text(
            slide, ex.get("question", ""),
            1.0, 1.2, 11.3, 0.85,
            font_size=26, bold=True, color="FFFFFF", align="left"
        )

        # Đáp án A/B/C/D — dọc
        options       = ex.get("options", [])
        labels        = ["A", "B", "C", "D"]
        OPTION_TOP    = 2.2
        OPTION_HEIGHT = 0.88
        OPTION_GAP    = 0.18

        for idx, opt in enumerate(options):
            label   = labels[idx] if idx < len(labels) else str(idx + 1)
            hz_text = opt.get("hz", "")
            py_text = opt.get("py", "")
            y       = OPTION_TOP + idx * (OPTION_HEIGHT + OPTION_GAP)

            # Label
            self.add_text(
                slide, f"{label}.",
                0.6, y + 0.05, 0.55, OPTION_HEIGHT * 0.9,
                font_size=22, bold=True, color="FCF1D4", align="center"
            )
            # HZ
            self.add_text(
                slide, hz_text,
                1.25, y + 0.02, 11.5, OPTION_HEIGHT * 0.52,
                font_size=24, color="FFFFFF", align="left"
            )
            # Pinyin
            if py_text:
                self.add_text(
                    slide, py_text,
                    1.25, y + 0.5, 11.5, OPTION_HEIGHT * 0.45,
                    font_size=16, color="A0A0A0", align="left"
                )

        # Đáp án đúng
        answer_y = OPTION_TOP + len(options) * (OPTION_HEIGHT + OPTION_GAP) + 0.2
        self.add_text(
            slide,
            f"✅  Đáp án: {ex.get('answer', '')}",
            0.5, min(answer_y, 6.7), 12.3, 0.65,
            font_size=22, italic=True, color="90EE90", align="center"
        )

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

        for sec in self.data.get("sections", []):
            self.add_dialogue_slide(sec)
            self.add_vocab_slides(sec)
            for extra in sec.get("extra_knowledge", []):
                self.add_extra_slide(extra)
            self.add_exercise_slide(sec)

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
    output_path   = "test_output_baikhoa.pptx"

    gen = PPTGenerator(template_path, json_path)
    gen.build()
    gen.save(output_path)