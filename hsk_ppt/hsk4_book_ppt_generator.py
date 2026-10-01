import math
import os
import re

from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Cm, Inches, Pt

from hsk_ppt.test_generate_ppt_bk import PPTGenerator


class HSK4BookPPTGenerator(PPTGenerator):
    """Render HSK4 book units using a fixed 12-slide content layout per unit."""

    BACKGROUND = "F9F6EF"
    FULL_NEW_WORD = "A40400"
    SENTENCE_NEW_WORD = "29741D"
    HAN_FONT = "字由点字云霆楷体"
    TITLE_FONT = "字由点字典楷"
    FULL_BOX_LEFT_CM = 1.32
    FULL_BOX_TOP_CM = 7.74
    FULL_BOX_WIDTH_CM = 47.92
    FULL_BOX_HEIGHT_CM = 14.04
    SENTENCE_BOX_LEFT_CM = 1.39
    SENTENCE_BOX_TOP_CM = 7.82
    SENTENCE_BOX_WIDTH_CM = 48.04
    SENTENCE_BOX_HEIGHT_CM = 7.92
    IMAGE_LEFT_CM = 38.10
    IMAGE_TOP_CM = 19.59
    IMAGE_SIZE_CM = 7.31
    TEXT_IMAGE_GAP_CM = 0.80

    def _add_title(self, slide, text):
        box = slide.shapes.add_textbox(Cm(15.28), Cm(1.26), Cm(20.14), Cm(2.67))
        box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        self._set_text_exact_style(
            box, text, font_name="Fraunces", font_size=57,
            color="FCF1D4", bold=False, align="center"
        )

    def _next_slide(self):
        slide = super()._next_slide()
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = RGBColor.from_string(self.BACKGROUND)
        return slide

    def _add_image(self, slide, unit):
        local_image_path = unit.get("local_image_path")
        if local_image_path:
            if os.path.exists(local_image_path):
                slide.shapes.add_picture(
                    local_image_path,
                    Cm(self.IMAGE_LEFT_CM),
                    Cm(self.IMAGE_TOP_CM),
                    Cm(self.IMAGE_SIZE_CM),
                    Cm(self.IMAGE_SIZE_CM),
                )

    @staticmethod
    def _plain_text(text):
        return re.sub(r"</?hl>", "", text or "")

    @staticmethod
    def _estimate_lines(text, font_size, width_cm):
        width_chars = max(1, int(width_cm / (font_size * 0.026)))
        return max(
            1,
            sum(max(1, math.ceil(len(line) / width_chars)) for line in str(text).split("\n")),
        )

    def _estimate_sentence_height(self, sentences, hz_size=42, detail_size=28):
        text_width = self._safe_text_width(self.SENTENCE_BOX_LEFT_CM)
        total = 0.0
        for sentence in sentences:
            total += self._estimate_lines(sentence.get("hz", ""), hz_size, text_width) * hz_size * 0.045
            total += self._estimate_lines(sentence.get("pinyin", ""), detail_size, text_width) * detail_size * 0.040
            total += self._estimate_lines(sentence.get("vi", ""), detail_size, text_width) * detail_size * 0.040
            total += 0.55
        return total

    def _safe_text_width(self, left_cm):
        requested_right = left_cm + self.SENTENCE_BOX_WIDTH_CM
        image_safe_right = self.IMAGE_LEFT_CM - self.TEXT_IMAGE_GAP_CM
        return max(10.0, min(requested_right, image_safe_right) - left_cm)

    def _fit_full_font_size(self, lines):
        available_height = self.FULL_BOX_HEIGHT_CM
        text_width = self._safe_text_width(self.FULL_BOX_LEFT_CM)
        font_size = 42
        while font_size > 30:
            estimated_height = sum(
                self._estimate_lines(line, font_size, text_width) * font_size * 0.045 + 0.35
                for line in lines
            )
            if estimated_height <= available_height:
                break
            font_size -= 2
        return font_size

    def _highlight_vocabulary(self, text, vocabulary):
        result = self._plain_text(text)
        words = sorted(
            {self._plain_text(item.get("hz", "")) for item in vocabulary if item.get("hz")},
            key=len,
            reverse=True,
        )
        for word in words:
            result = re.sub(
                rf"(?<!<hl>){re.escape(word)}(?!</hl>)",
                f"<hl>{word}</hl>",
                result,
            )
        return result

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
        self._add_title(slide, unit.get("title", "Bài khóa"))
        self._add_image(slide, unit)
        box = slide.shapes.add_textbox(
            Cm(self.FULL_BOX_LEFT_CM),
            Cm(self.FULL_BOX_TOP_CM),
            Cm(self._safe_text_width(self.FULL_BOX_LEFT_CM)),
            Cm(self.FULL_BOX_HEIGHT_CM),
        )
        tf = box.text_frame
        tf.word_wrap = True
        tf.margin_top = tf.margin_bottom = tf.margin_left = tf.margin_right = 0
        hz_lines = unit.get("content", {}).get("hz", [])
        font_size = self._fit_full_font_size(hz_lines)
        for index, line in enumerate(hz_lines):
            line = line or ""
            if highlight:
                self._add_highlighted_paragraph(tf, line, self.FULL_NEW_WORD, font_size)
            else:
                paragraph = tf.add_paragraph() if tf.paragraphs[0].runs else tf.paragraphs[0]
                paragraph.space_after = Pt(8 if index < len(hz_lines) - 1 else 0)
                run = paragraph.add_run()
                run.text = self._plain_text(line)
                run.font.name = self.HAN_FONT
                run.font.size = Pt(font_size)
                run.font.color.rgb = RGBColor(0, 0, 0)

    def _render_vocabulary(self, vocabulary):
        legacy_vocabulary = []
        for item in vocabulary:
            example = item.get("example") or {}
            legacy_vocabulary.append({
                "hz": item.get("hz", ""),
                "pinyin": item.get("pinyin", ""),
                "type": item.get("type", ""),
                "vi": ", ".join(item.get("meanings", [])),
                "example": {
                    "hz": example.get("hz", ""),
                    "py": example.get("pinyin", example.get("py", "")),
                    "vi": example.get("vi", "")
                }
            })
        self.add_vocab_slides({"vocabulary": legacy_vocabulary})

    def _render_sentence_slide(self, slide, unit, sentences, vocabulary):
        self._add_title(slide, unit.get("title", ""))
        image_path = next(
            (sentence.get("local_image_path") for sentence in sentences if sentence.get("local_image_path")),
            None,
        )
        if image_path and os.path.exists(image_path):
            slide.shapes.add_picture(
                image_path,
                Cm(self.IMAGE_LEFT_CM),
                Cm(self.IMAGE_TOP_CM),
                Cm(self.IMAGE_SIZE_CM),
                Cm(self.IMAGE_SIZE_CM),
            )

        hz_size, detail_size = 42, 28
        while self._estimate_sentence_height(sentences, hz_size, detail_size) > self.SENTENCE_BOX_HEIGHT_CM:
            if hz_size <= 30:
                break
            hz_size -= 2
            detail_size = max(20, detail_size - 1)

        box = slide.shapes.add_textbox(
            Cm(self.SENTENCE_BOX_LEFT_CM),
            Cm(self.SENTENCE_BOX_TOP_CM),
            Cm(self._safe_text_width(self.SENTENCE_BOX_LEFT_CM)),
            Cm(self.SENTENCE_BOX_HEIGHT_CM),
        )
        tf = box.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_top = tf.margin_bottom = tf.margin_left = tf.margin_right = 0

        for index, sentence in enumerate(sentences):
            hz = self._highlight_vocabulary(sentence.get("hz", ""), vocabulary)
            p_hz = tf.paragraphs[0] if index == 0 else tf.add_paragraph()
            self._add_hl_text(p_hz, hz, self.HAN_FONT, hz_size, "000000", self.SENTENCE_NEW_WORD)
            p_hz.space_after = Pt(2)

            p_py = tf.add_paragraph()
            p_py.space_after = Pt(2)
            run_py = p_py.add_run()
            run_py.text = sentence.get("pinyin", "")
            run_py.font.name = "Muli"
            run_py.font.size = Pt(detail_size)
            run_py.font.color.rgb = self.hex_to_rgb_color("545454")

            p_vi = tf.add_paragraph()
            p_vi.space_after = Pt(8 if index < len(sentences) - 1 else 0)
            run_vi = p_vi.add_run()
            run_vi.text = sentence.get("vi", "")
            run_vi.font.name = "Muli"
            run_vi.font.size = Pt(detail_size)
            run_vi.font.color.rgb = self.hex_to_rgb_color("A40400")

    def _render_sentences(self, unit, sentences, vocabulary):
        slide = self._next_slide()
        self._render_sentence_slide(slide, unit, sentences, vocabulary)

    def _render_exercises(self, unit):
        legacy_exercises = []
        for exercise in unit.get("exercises", []):
            exercise_type = exercise.get("type")
            if exercise_type == "multiple_choice":
                options = exercise.get("options") or []
                legacy_exercises.append({
                    "type": exercise_type,
                    "multiple_choice": {
                        "question": exercise.get("question", ""),
                        "options": [{"label": chr(65 + i), "hz": option, "py": ""} for i, option in enumerate(options)],
                        "answer": exercise.get("answer", "")
                    }
                })
            elif exercise_type == "true_false":
                legacy_exercises.append({
                    "type": exercise_type,
                    "true_false": {"statement": exercise.get("question", ""), "answer": exercise.get("answer", False)}
                })
            elif exercise_type == "fill_in_the_blanks":
                legacy_exercises.append({
                    "type": exercise_type,
                    "fill_in_the_blanks": {
                        "instruction": exercise.get("question", "Điền từ vào chỗ trống:"),
                        "given_words": exercise.get("given_words") or [],
                        "sentences": exercise.get("sentences") or []
                    }
                })
        self.add_exercise_slide({"exercise": legacy_exercises})

    def render_unit(self, unit, vocabulary_by_id):
        unit_vocabulary = [
            vocabulary_by_id[item_id]
            for item_id in unit.get("vocabulary_ids", [])
            if item_id in vocabulary_by_id
        ]
        sentences = unit.get("sentences", [])

        self._render_full_text(self._next_slide(), unit, highlight=True)

        self._render_vocabulary(unit_vocabulary[:3])
        for index in range(3, len(unit_vocabulary), 3):
            self._render_vocabulary(unit_vocabulary[index:index + 3])

        sentence_chunks = []
        current_chunk = []
        for sentence in sentences:
            candidate = current_chunk + [sentence]
            if current_chunk and self._estimate_sentence_height(candidate) > self.SENTENCE_BOX_HEIGHT_CM:
                sentence_chunks.append(current_chunk)
                current_chunk = [sentence]
            else:
                current_chunk = candidate
        if current_chunk:
            sentence_chunks.append(current_chunk)
        for chunk in sentence_chunks:
            self._render_sentences(unit, chunk, unit_vocabulary)

        self._render_full_text(self._next_slide(), unit, highlight=False)
        self._render_exercises(unit)

    def build(self):
        self.add_cover_slide()
        self.add_table_of_content()
        vocabulary_by_id = {
            item.get("id"): item
            for item in self.data.get("vocabulary_source", {}).get("items", [])
            if item.get("id")
        }
        type_counters = {"dialogue": 0, "passage": 0}
        for unit in sorted(self.data.get("units", []), key=lambda item: item.get("order", 0)):
            unit = dict(unit)
            unit_type = unit.get("unit_type", "section")
            if unit_type in type_counters:
                type_counters[unit_type] += 1
                label = "Hội thoại" if unit_type == "dialogue" else "Đoạn văn"
                unit["title"] = f"{label} {type_counters[unit_type]}"
            self.render_unit(unit, vocabulary_by_id)
        self.add_end_slide()

        for index in range(self._end_slide_index - 1, self._slide_cursor - 1, -1):
            r_id = self.prs.slides._sldIdLst[index].rId
            self.prs.part.drop_rel(r_id)
            del self.prs.slides._sldIdLst[index]