"""glossary.py (G3.3): phân tích, giới hạn, khối chỉ thị dùng chung cho OCR-gộp-dịch và dịch riêng, khóa điểm lưu."""

import os
import tempfile
import unittest
from unittest import mock

import tests_gui._setup  # noqa: F401  (phải import trước mã ứng dụng)
import claude_ocr
import claude_translate
import fake_engine
import glossary
import jobs


class GlossaryBase(unittest.TestCase):
    def setUp(self):
        self.path = glossary.glossary_path()
        if os.path.exists(self.path):
            os.remove(self.path)
        self.addCleanup(lambda: os.path.exists(self.path) and os.remove(self.path))


class TestParse(GlossaryBase):
    def test_accepts_three_separators_comments_and_blanks(self):
        entries, warns = glossary.parse(
            "# chú thích\n\nzugzwang → thế bí\nfork -> đòn chiếu đôi\npin => ghim quân\n  Luft   →   ô thoáng  \n"
        )
        self.assertEqual(
            entries,
            [("zugzwang", "thế bí"), ("fork", "đòn chiếu đôi"), ("pin", "ghim quân"), ("Luft", "ô thoáng")],
        )
        self.assertEqual(warns, [])

    def test_bad_lines_warn_and_are_skipped(self):
        entries, warns = glossary.parse("không có dấu ngăn\n→ chỉ có đích\nnguồn →\nok → tốt")
        self.assertEqual(entries, [("ok", "tốt")])
        self.assertEqual(len(warns), 3)
        self.assertIn("Dòng 1", warns[0])

    def test_duplicate_source_last_wins_case_insensitive(self):
        entries, _ = glossary.parse("Fork → a\nfork → b")
        self.assertEqual(entries, [("fork", "b")])

    def test_limits(self):
        many = "\n".join(f"t{i} → d{i}" for i in range(glossary.MAX_ENTRIES + 5))
        entries, warns = glossary.parse(many)
        self.assertEqual(len(entries), glossary.MAX_ENTRIES)
        self.assertEqual(len(warns), 5)
        entries, warns = glossary.parse("x" * (glossary.MAX_TERM_LEN + 1) + " → y")
        self.assertEqual((entries, len(warns)), ([], 1))

    def test_save_and_load_roundtrip(self):
        self.assertEqual(glossary.load_text(), "")
        n, warns = glossary.save_text("a → b\nxấu")
        self.assertEqual((n, len(warns)), (1, 1))
        self.assertEqual(glossary.load_text(), "a → b\nxấu")
        self.assertTrue(self.path.startswith(jobs.data_dir()))


class TestPromptBlock(GlossaryBase):
    def test_empty_gives_empty_block(self):
        self.assertEqual(glossary.prompt_block(), "")
        self.assertEqual(glossary.fingerprint(""), "")

    def test_block_lists_terms_under_the_shared_header(self):
        glossary.save_text("zugzwang → thế bí\nfork → đòn chiếu đôi")
        block = glossary.prompt_block()
        self.assertTrue(block.startswith(glossary.GLOSSARY_HEADER))
        self.assertIn("- zugzwang → thế bí\n", block)
        self.assertIn("- fork → đòn chiếu đôi\n", block)
        self.assertIn("BẮT BUỘC", block)      # quy ước prompt: chỉ thị bắt buộc viết HOA

    def test_block_is_capped(self):
        entries = [(f"term{i:02d}" + "x" * 40, "y" * 55) for i in range(glossary.MAX_ENTRIES)]
        block = glossary.prompt_block(entries)
        self.assertLessEqual(len(block), glossary.MAX_BLOCK_CHARS + 1)

    def test_fingerprint_changes_with_content(self):
        glossary.save_text("a → b")
        f1 = glossary.fingerprint(glossary.prompt_block())
        glossary.save_text("a → c")
        self.assertNotEqual(f1, glossary.fingerprint(glossary.prompt_block()))


class TestSettingsUi(GlossaryBase):
    def test_save_handler_message_and_file(self):
        import markitdown_gui as g

        msg = g.on_save_glossary("a → b" + chr(10) + "hỏng" + chr(10) + "c -> d")
        self.assertIn("Đã lưu **2** thuật ngữ", msg)
        self.assertIn("Dòng 2 bỏ qua", msg)
        self.assertEqual(glossary.parse(glossary.load_text())[0], [("a", "b"), ("c", "d")])

    def test_long_text_is_truncated_with_warning(self):
        n, warns = glossary.save_text("a → b" + chr(10) + "x" * (glossary.MAX_TEXT_CHARS + 10))
        self.assertEqual(n, 1)
        self.assertTrue(any("bị cắt" in w for w in warns))
        self.assertLessEqual(len(glossary.load_text()), glossary.MAX_TEXT_CHARS)

    def test_settings_page_has_the_glossary_card(self):
        import markitdown_gui as g

        ids = {getattr(b, "elem_id", None) for b in g.build_ui().blocks.values()}
        self.assertIn("mid-glossary", ids)


class TestPromptInjection(GlossaryBase):
    def prompts(self):
        single = claude_ocr._build_prompt("/x/page_001.png", None, chess=True, translate_to="vi")
        plain = claude_ocr._build_prompt("/x/page_001.png", None, chess=False, translate_to="vi")
        multi = claude_ocr._build_prompt_multi(
            [("/x/page_001.png", None), ("/x/page_002.png", None)], chess=True, translate_to="vi",
        )
        no_tr = claude_ocr._build_prompt("/x/page_001.png", None, chess=True, translate_to=None)
        return single, plain, multi, no_tr

    def test_prompts_unchanged_without_glossary(self):
        for p in self.prompts():
            self.assertNotIn("BẢNG THUẬT NGỮ", p)

    def test_merge_prompts_get_the_block_but_plain_ocr_does_not(self):
        glossary.save_text("zugzwang → thế bí")
        single, plain, multi, no_tr = self.prompts()
        for p in (single, plain, multi):
            self.assertIn("- zugzwang → thế bí", p)
            self.assertEqual(p.count("BẢNG THUẬT NGỮ"), 1)
        self.assertNotIn("BẢNG THUẬT NGỮ", no_tr)             # OCR không dịch: không cần thuật ngữ
        # khối đứng TRƯỚC chỉ thị đầu ra cuối cùng
        self.assertLess(single.index("BẢNG THUẬT NGỮ"), single.index("CHỈ trả về"))

    def test_separate_translation_instruction_gets_block_and_key_changes(self):
        seen = []

        def spy(chunk, model, timeout=600, instruction=None, **kw):
            seen.append(instruction)
            return fake_engine.fake_translate(chunk)

        md = "## Chapter 1: The Italian Game\n\nWhite develops the knight and the bishop toward the centre of the board."
        with mock.patch.object(claude_translate, "_call_engine_translate", spy):
            claude_translate.translate_markdown_vn(md, engine="fake")
            glossary.save_text("bishop → tượng")
            claude_translate.translate_markdown_vn(md, engine="fake")
        self.assertNotIn("BẢNG THUẬT NGỮ", seen[0])
        self.assertIn("- bishop → tượng", seen[1])

    def test_cache_is_not_reused_after_glossary_change(self):
        tmp = tempfile.mkdtemp(prefix="mid_test_gl_")
        cache = jobs.DiskChunkCache(tmp)
        md = "## Chapter 1: The Italian Game\n\nWhite develops the knight and the bishop toward the centre of the board."
        fake_engine.reset_calls()
        claude_translate.translate_markdown_vn(md, engine="fake", chunk_cache=cache)
        n1 = len([c for c in fake_engine.CALLS if c[0] == "translate"])
        claude_translate.translate_markdown_vn(md, engine="fake", chunk_cache=cache)
        self.assertEqual(len([c for c in fake_engine.CALLS if c[0] == "translate"]), n1)   # cùng thuật ngữ: dùng lại
        glossary.save_text("bishop → tượng")
        claude_translate.translate_markdown_vn(md, engine="fake", chunk_cache=cache)
        self.assertGreater(len([c for c in fake_engine.CALLS if c[0] == "translate"]), n1)  # đổi thuật ngữ: dịch lại
        self.assertNotEqual(
            claude_translate.chunk_cache_key("a", True, "en", ""), claude_translate.chunk_cache_key("a", True, "en", "x"),
        )


if __name__ == "__main__":
    unittest.main()
