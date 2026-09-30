import math

from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from hsk_ppt.test_generate_ppt_bk import PPTGenerator


class HSK4BookPPTGenerator(PPTGenerator):
    """Render HSK4 book units using a fixed 12-slide content layout per unit."""

    BACKGROUND = "F9F6EF"
    FULL_NEW_WORD = "A40400"
    SENTENCE_NEW_WORD = "29741D"
    HAN_FONT = "字由点字云霆楷体"
    TITLE_FONT = "字由点字典楷"

    def _clear_content_slide(self, slide):
        for shape in list(slide.shapes):
            slide.shapes._spTree.remove(shape._element)
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = RGBColor.from_string(self.BACKGROUND)

    def _add_title(self, slide, text):
        box = slide.shapes.add_textbox(Inches(0.55), Inches(0.25), Inches(18.9), Inches(0.65))
        box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        self._set_text_exact_style(
            box, text, font_name=self.TITLE_FONT, font_size=28,
            color="000000", bold=True, align="center"
        )

    def _add_highlighted_paragraph(self, text_frame, text, highlight_color, font_size=42):
        paragraph = text_frame.add_paragraph() if text_frame.paragraphs[0].runs else text_frame.paragraphs[0]
        paragraph.alignment = PP_ALIGN.LEFT
        paragraph.space_after = Pt(8)
        parts = text.split("<hl>")
        for part in parts:
            if "</hl>" in part:
                highlighted, rest = part.split("</hl>", 1)
                run = paragraph.add_run()
                run.text = highlighted
                run.font.name = self.HAN_FONT
                run.font.size = Pt(font_size)
                run.font.color.rgb = RGBColor.from_string(highlight_color)
                if rest:
                    run = paragraph.add_run()
                    run.text = rest
                    run.font.name = self.HAN_FONT
                    run.font.size = Pt(font_size)
                    run.font.color.rgb = RGBColor(0, 0, 0)
            else:
                run = paragraph.add_run()
                run.text = part
                run.font.name = self.HAN_FONT
                run.font.size = Pt(font_size)
                run.font.color.rgb = RGBColor(0, 0, 0)

    def _render_full_text(self, slide, unit, highlight=False):
        self._clear_content_slide(slide)
        self._add_title(slide, unit.get("title", "Bài khóa"))
        box = slide.shapes.add_textbox(Inches(0.85), Inches(1.15), Inches(17.9), Inches(5.85))
        tf = box.text_frame
        tf.word_wrap = True
        tf.margin_top = tf.margin_bottom = tf.margin_left = tf.margin_right = 0
        hz_lines = unit.get("content", {}).get("hz", [])
        for line in hz_lines:
            if highlight:
                self._add_highlighted_paragraph(tf, line, self.FULL_NEW_WORD, 42)
            else:
                paragraph = tf.add_paragraph() if tf.paragraphs[0].runs else tf.paragraphs[0]
                paragraph.space_after = Pt(8)
                run = paragraph.add_run()
                run.text = line.replace("<hl>", "").replace("</hl>", "")
                run.font.name = self.HAN_FONT
                run.font.size = Pt(42)
                run.font.color.rgb = RGBColor(0, 0, 0)

    def _render_vocabulary(self, slide, vocabulary):
        self._clear_content_slide(slide)
        self._add_title(slide, "Từ mới")
        box = slide.shapes.add_textbox(Inches(0.8), Inches(1.2), Inches(18.0), Inches(5.9))
        tf = box.text_frame
        tf.word_wrap = True
        tf.margin_top = tf.margin_bottom = tf.margin_left = tf.margin_right = 0
        for item in vocabulary:
            paragraph = tf.add_paragraph() if tf.paragraphs[0].runs else tf.paragraphs[0]
            paragraph.space_after = Pt(12)
            run = paragraph.add_run()
            run.text = f"{item.get('hz', '')}  /{item.get('pinyin', '')}/  "
            run.font.name = self.HAN_FONT
            run.font.size = Pt(30)
            run.font.color.rgb = RGBColor(0, 0, 0)
            run = paragraph.add_run()
            meanings = ", ".join(item.get("meanings", []))
            run.text = f"{item.get('type', '')}: {meanings}"
            run.font.name = "Muli"
            run.font.size = Pt(28)
            run.font.color.rgb = RGBColor.from_string(self.FULL_NEW_WORD)

    def _render_sentences(self, slide, unit, sentences):
        self._clear_content_slide(slide)
        self._add_title(slide, unit.get("title", "Câu ví dụ"))
        box = slide.shapes.add_textbox(Inches(0.8), Inches(1.1), Inches(18.0), Inches(6.0))
        tf = box.text_frame
        tf.word_wrap = True
        tf.margin_top = tf.margin_bottom = tf.margin_left = tf.margin_right = 0
        for sentence in sentences:
            p = tf.add_paragraph() if tf.paragraphs[0].runs else tf.paragraphs[0]
            p.space_after = Pt(2)
            self._add_highlighted_paragraph(tf, sentence.get("hz", ""), self.SENTENCE_NEW_WORD, 42)
            p = tf.add_paragraph()
            p.space_after = Pt(2)
            run = p.add_run()
            run.text = sentence.get("pinyin", "")
            run.font.name = "Muli"
            run.font.size = Pt(28)
            run.font.color.rgb = RGBColor.from_string("545454")
            p = tf.add_paragraph()
            p.space_after = Pt(14)
            run = p.add_run()
            run.text = sentence.get("vi", "")
            run.font.name = "Muli"
            run.font.size = Pt(28)
            run.font.color.rgb = RGBColor(0, 0, 0)

    def _render_exercises(self, slide, unit):
        self._clear_content_slide(slide)
        self._add_title(slide, "Luyện tập")
        box = slide.shapes.add_textbox(Inches(0.9), Inches(1.2), Inches(17.8), Inches(5.8))
        tf = box.text_frame
        tf.word_wrap = True
        tf.margin_top = tf.margin_bottom = tf.margin_left = tf.margin_right = 0
        for index, exercise in enumerate(unit.get("exercises", []), 1):
            p = tf.add_paragraph() if tf.paragraphs[0].runs else tf.paragraphs[0]
            p.space_after = Pt(8)
            run = p.add_run()
            run.text = f"{index}. {exercise.get('question', '')}"
            run.font.name = "Muli Bold"
            run.font.size = Pt(26)
            run.font.bold = True
            run.font.color.rgb = RGBColor(0, 0, 0)
            options = exercise.get("options") or exercise.get("given_words") or []
            if options:
                p = tf.add_paragraph()
                p.space_after = Pt(8)
                run = p.add_run()
                run.text = "   " + "    ".join(str(option) for option in options)
                run.font.name = "Muli"
                run.font.size = Pt(24)
                run.font.color.rgb = RGBColor(0, 0, 0)

    def render_unit(self, unit, vocabulary_by_id):
        unit_vocabulary = [
            vocabulary_by_id[item_id]
            for item_id in unit.get("vocabulary_ids", [])
            if item_id in vocabulary_by_id
        ]
        sentences = unit.get("sentences", [])

        self._render_full_text(self._next_slide(), unit, highlight=True)

        vocab_chunks = [
            unit_vocabulary[index:index + max(1, math.ceil(len(unit_vocabulary) / 4))]
            for index in range(0, len(unit_vocabulary), max(1, math.ceil(len(unit_vocabulary) / 4)))
        ]
        for index in range(4):
            self._render_vocabulary(
                self._next_slide(),
                vocab_chunks[index] if index < len(vocab_chunks) else []
            )

        sentence_chunks = [sentences[index::5] for index in range(5)]
        for chunk in sentence_chunks:
            self._render_sentences(self._next_slide(), unit, chunk)

        self._render_full_text(self._next_slide(), unit, highlight=False)
        self._render_exercises(self._next_slide(), unit)

    def build(self):
        self.add_cover_slide()
        self.add_table_of_content()
        vocabulary_by_id = {
            item.get("id"): item
            for item in self.data.get("vocabulary_source", {}).get("items", [])
            if item.get("id")
        }
        for unit in sorted(self.data.get("units", []), key=lambda item: item.get("order", 0)):
            self.render_unit(unit, vocabulary_by_id)
        self.add_end_slide()

        for index in range(self._end_slide_index - 1, self._slide_cursor - 1, -1):
            r_id = self.prs.slides._sldIdLst[index].rId
            self.prs.part.drop_rel(r_id)
            del self.prs.slides._sldIdLst[index]