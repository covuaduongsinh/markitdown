"""obsidian.py (G3.4): frontmatter YAML, tách chương theo `#`, tên tệp."""

import unittest

import tests_gui._setup  # noqa: F401
import obsidian as ob

FENCE = "```"
MD = (
    "Lời tựa trước chương.\n\n"
    "# Chương 1: Khai cuộc Ý\n\nNội dung 1.\n\n" + FENCE + "chessboard\nfen: 8/8/8/8/8/8/8/4K2k w - - 0 1\n" + FENCE + "\n\n"
    "## Mục con\n\nCòn trong chương 1.\n\n"
    "# Chương 2\n\nNội dung 2.\n"
)


class TestFrontmatter(unittest.TestCase):
    def test_types_and_quoting(self):
        fm = ob.frontmatter({"title": 'Sách "A" \\ B', "pages": 12, "translated": True, "skip": None, "empty": "", "n": 1.5})
        self.assertTrue(fm.startswith("---\n") and fm.endswith("---\n\n"))
        self.assertIn('title: "Sách \\"A\\" \\\\ B"', fm)
        self.assertIn("pages: 12", fm)
        self.assertIn("translated: true", fm)
        self.assertIn("n: 1.5", fm)
        self.assertNotIn("skip", fm)
        self.assertNotIn("empty", fm)

    def test_newlines_cannot_break_out_of_the_value(self):
        fm = ob.frontmatter({"title": "dòng 1\n---\nevil: 1"})
        self.assertEqual(fm.count("\n---\n"), 1)  # chỉ dấu đóng thật
        self.assertEqual(len(fm.splitlines()), 4)

    def test_with_and_strip_are_idempotent(self):
        once = ob.with_frontmatter("# T\n\nThân.\n", {"title": "T"})
        twice = ob.with_frontmatter(once, {"title": "T2"})
        self.assertEqual(twice.count("---\n"), 2)
        self.assertIn('title: "T2"', twice)
        self.assertEqual(ob.strip_frontmatter(twice), "# T\n\nThân.\n")
        self.assertEqual(ob.strip_frontmatter("không có\n"), "không có\n")


class TestSplit(unittest.TestCase):
    def test_split_keeps_preamble_and_nested_headings(self):
        parts = ob.split_by_h1(MD)
        self.assertEqual([t for t, _b in parts], ["", "Chương 1: Khai cuộc Ý", "Chương 2"])
        self.assertTrue(parts[0][1].startswith("Lời tựa"))
        self.assertIn("## Mục con", parts[1][1])               # `##` không phải ranh giới
        self.assertIn("```chessboard", parts[1][1])
        self.assertTrue(parts[2][1].startswith("# Chương 2"))

    def test_hash_inside_code_fence_is_not_a_boundary(self):
        md = "# A\n\n" + FENCE + "\n# không phải tiêu đề\n" + FENCE + "\n\n# B\n"
        self.assertEqual([t for t, _b in ob.split_by_h1(md)], ["A", "B"])

    def test_no_h1_means_nothing_to_split(self):
        self.assertEqual(ob.split_by_h1("## chỉ cấp hai\n\ntext"), [])
        self.assertEqual(ob.split_by_h1(""), [])

    def test_lossless(self):
        joined = "\n".join(b.strip("\n") for _t, b in ob.split_by_h1(MD))
        for needle in ("Lời tựa", "Nội dung 1.", "Còn trong chương 1.", "Nội dung 2.", "fen: 8/8/8/8/8/8/8/4K2k"):
            self.assertIn(needle, joined)

    def test_first_title(self):
        self.assertEqual(ob.first_title(MD, "x"), "Chương 1: Khai cuộc Ý")
        self.assertEqual(ob.first_title("không có", "x"), "x")


class TestChapters(unittest.TestCase):
    def test_filenames_and_numbers(self):
        ch = ob.chapters(MD)
        self.assertEqual([n for n, _b in ch], ["00-Mở đầu.md", "01-Chương 1 Khai cuộc Ý.md", "02-Chương 2.md"])

    def test_padding_grows_with_total(self):
        md = "".join(f"# C{i}\n\nx\n\n" for i in range(1, 101))
        names = [n for n, _b in ob.chapters(md)]
        self.assertEqual(names[0], "001-C1.md")
        self.assertEqual(names[-1], "100-C100.md")

    def test_frontmatter_per_chapter(self):
        ch = dict(ob.chapters(MD, {"book": "Sách mẫu", "source": "s.pdf"}))
        text = ch["02-Chương 2.md"]
        self.assertTrue(text.startswith("---\n"))
        self.assertIn('title: "Chương 2"', text)
        self.assertIn("chapter: 2", text)
        self.assertIn('book: "Sách mẫu"', text)
        self.assertIn("# Chương 2", text)
        self.assertIn('title: "Mở đầu"', ch["00-Mở đầu.md"])
        self.assertIn("chapter: 0", ch["00-Mở đầu.md"])

    def test_safe_name(self):
        self.assertEqual(ob.safe_name('a<b>:c"/d\\e|f?g*'), "a b c d e f g")
        self.assertEqual(ob.safe_name("  ..  "), "chuong")
        self.assertLessEqual(len(ob.safe_name("x" * 200)), 60)
        self.assertEqual(ob.chapter_filename(3, "", 10), "03-Mở đầu.md")


if __name__ == "__main__":
    unittest.main()
