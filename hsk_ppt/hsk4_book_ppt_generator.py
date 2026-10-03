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

    def _estimate_sentence_height(self, sentences, width_cm):
        total = 0.0
        for sentence in sentences:
            total += self._estimate_lines(sentence.get("hz", ""), 42, width_cm) * 1.45
            total += self._estimate_lines(sentence.get("pinyin", ""), 28, width_cm) * 0.95
            total += self._estimate_lines(sentence.get("vi", ""), 28, width_cm) * 0.95
            total += 0.25
        return total

    def _safe_text_width(self, left_cm):
        requested_right = left_cm + self.SENTENCE_BOX_WIDTH_CM
        image_safe_right = self.IMAGE_LEFT_CM - self.TEXT_IMAGE_GAP_CM
        return max(10.0, min(requested_right, image_safe_right) - left_cm)

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

    def _highlight_example(self, text, marker):
        text = self._plain_text(text)
        if not text or not marker:
            return text
        return re.sub(
            rf"(?<!<hl>){re.escape(marker)}(?!</hl>)",
            f"<hl>{marker}</hl>",
            text,
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

    def _render_full_text(self, slide, unit, highlight=False, vocabulary=None):
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
        for index, line in enumerate(hz_lines):
            line = line or ""
            if highlight:
                line = self._highlight_vocabulary(line, vocabulary or [])
                self._add_highlighted_paragraph(tf, line, self.FULL_NEW_WORD, 42)
            else:
                paragraph = tf.add_paragraph() if tf.paragraphs[0].runs else tf.paragraphs[0]
                paragraph.space_after = Pt(8 if index < len(hz_lines) - 1 else 0)
                run = paragraph.add_run()
                run.text = self._plain_text(line)
                run.font.name = self.HAN_FONT
                run.font.size = Pt(42)
                run.font.color.rgb = RGBColor(0, 0, 0)

    def _render_vocabulary(self, vocabulary):
        legacy_vocabulary = []
        for item in vocabulary:
            example = item.get("example") or {}
            word = self._plain_text(item.get("hz", ""))
            pinyin = item.get("pinyin", "")
            meanings = item.get("meanings", [])
            example_hz = self._highlight_example(example.get("hz", ""), word)
            example_py = self._highlight_example(
                example.get("pinyin", example.get("py", "")), pinyin
            )
            example_vi = example.get("vi", "")
            for meaning in sorted(meanings, key=len, reverse=True):
                example_vi = self._highlight_example(example_vi, meaning)
            legacy_vocabulary.append({
                "hz": item.get("hz", ""),
                "pinyin": item.get("pinyin", ""),
                "type": item.get("type", ""),
                "vi": ", ".join(item.get("meanings", [])),
                "example": {
                    "hz": example_hz,
                    "py": example_py,
                    "vi": example_vi
                }
            })
        self.add_vocab_slides({"vocabulary": legacy_vocabulary})

    def _render_sentence_slide(self, slide, unit, sentences, vocabulary):
        self._add_title(slide, unit.get("title", ""))
        image_path = next(
            (
                sentence.get("image_group_local_path") or sentence.get("local_image_path")
                for sentence in sentences
                if sentence.get("image_group_local_path") or sentence.get("local_image_path")
            ),
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

        if self._estimate_sentence_height(sentences, 31.45) <= 4.64:
            box_left = 9.73
            box_top = 8.28
            box_width = 31.45
            box_height = 4.64
        else:
            box_left = self.SENTENCE_BOX_LEFT_CM
            box_top = self.SENTENCE_BOX_TOP_CM
            box_width = self.SENTENCE_BOX_WIDTH_CM
            box_height = self.SENTENCE_BOX_HEIGHT_CM

        box = slide.shapes.add_textbox(
            Cm(box_left), Cm(box_top), Cm(box_width), Cm(box_height)
        )
        tf = box.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_top = tf.margin_bottom = tf.margin_left = tf.margin_right = 0

        for index, sentence in enumerate(sentences):
            hz = self._highlight_vocabulary(sentence.get("hz", ""), vocabulary)
            p_hz = tf.paragraphs[0] if index == 0 else tf.add_paragraph()
            self._add_hl_text(p_hz, hz, self.HAN_FONT, 42, "000000", self.SENTENCE_NEW_WORD)
            p_hz.space_after = Pt(2)

            p_py = tf.add_paragraph()
            p_py.space_after = Pt(2)
            run_py = p_py.add_run()
            run_py.text = self._plain_text(sentence.get("pinyin", ""))
            run_py.font.name = "Muli"
            run_py.font.size = Pt(28)
            run_py.font.color.rgb = self.hex_to_rgb_color("545454")

            p_vi = tf.add_paragraph()
            p_vi.space_after = Pt(8 if index < len(sentences) - 1 else 0)
            run_vi = p_vi.add_run()
            run_vi.text = self._plain_text(sentence.get("vi", ""))
            run_vi.font.name = "Muli"
            run_vi.font.size = Pt(28)
            run_vi.font.color.rgb = self.hex_to_rgb_color("A40400")

    def _render_sentences(self, unit, sentences, vocabulary):
        slide = self._next_slide()
        self._render_sentence_slide(slide, unit, sentences, vocabulary)

    def _render_exercises(self, unit):
        legacy_exercises = []
        for exercise in unit.get("exercises", []):
            exercise_type = exercise.get("type")
            if exercise_type == "multiple_choice":
                data = exercise.get("multiple_choice") or exercise
                options = data.get("options") or []
                normalized_options = []
                for index, option in enumerate(options):
                    if isinstance(option, dict):
                        normalized_options.append({
                            "label": option.get("label", chr(65 + index)),
                            "hz": option.get("hz", ""),
                            "py": option.get("py", option.get("pinyin", "")),
                        })
                    else:
                        normalized_options.append({
                            "label": chr(65 + index), "hz": option, "py": ""
                        })
                legacy_exercises.append({
                    "type": exercise_type,
                    "multiple_choice": {
                        "question": data.get("question", ""),
                        "options": normalized_options,
                        "answer": data.get("answer", "")
                    }
                })
            elif exercise_type == "true_false":
                data = exercise.get("true_false") or exercise
                legacy_exercises.append({
                    "type": exercise_type,
                    "true_false": {
                        "statement": data.get("statement", data.get("question", "")),
                        "answer": data.get("answer", False),
                    }
                })
            elif exercise_type == "fill_in_the_blanks":
                data = exercise.get("fill_in_the_blanks") or exercise
                legacy_exercises.append({
                    "type": exercise_type,
                    "fill_in_the_blanks": {
                        "instruction": data.get("instruction", data.get("question", "Điền từ vào chỗ trống:")),
                        "given_words": data.get("given_words") or [],
                        "sentences": data.get("sentences") or [],
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

        self._render_full_text(
            self._next_slide(), unit, highlight=True, vocabulary=unit_vocabulary
        )

        self._render_vocabulary(unit_vocabulary[:3])
        for index in range(3, len(unit_vocabulary), 3):
            self._render_vocabulary(unit_vocabulary[index:index + 3])

        sentence_chunks = []
        current_chunk = []
        for sentence in sentences:
            candidate = current_chunk + [sentence]
            if current_chunk and self._estimate_sentence_height(candidate, 48.04) > 7.92:
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
        content_counter = 0
        for unit in sorted(self.data.get("units", []), key=lambda item: item.get("order", 0)):
            unit = dict(unit)
            unit_type = unit.get("unit_type", "section")
            if unit_type in {"dialogue", "passage"}:
                content_counter += 1
                label = "Hội thoại" if unit_type == "dialogue" else "Đoạn văn"
                unit["title"] = f"{label} {content_counter}"
            self.render_unit(unit, vocabulary_by_id)
        self.add_end_slide()

        for index in range(self._end_slide_index - 1, self._slide_cursor - 1, -1):
            r_id = self.prs.slides._sldIdLst[index].rId
            self.prs.part.drop_rel(r_id)
            del self.prs.slides._sldIdLst[index]