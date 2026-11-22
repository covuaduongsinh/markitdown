"""Xuất Obsidian trong công việc nền (G3.4): frontmatter, tách chương vào zip, hiệu đính FEN làm lại chương."""

import os
import shutil
import tempfile
import unittest
import zipfile
from unittest import mock

import tests_gui._setup  # noqa: F401  (phải import trước mã ứng dụng)
import fen_tools
import jobs
import obsidian
import review
from tests_gui.sample_pdf import make_sample_pdf

NEW = "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"


class ObsBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mid_test_obs_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.pdf = make_sample_pdf(os.path.join(self.tmp, "sach4.pdf"), 4)
        self.mgr = jobs.JobManager(os.path.join(self.tmp, "data"))
        os.environ["MID_FAKE_DELAY"] = "0"
        patcher = mock.patch.dict(os.environ, {"MID_FAKE_H1": "1"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_job(self, **opts):
        base = dict(engine="fake", ocr_model="fake", translate_model="fake", board_dpi="200", translate_vn=False)
        base.update(opts)
        jid = self.mgr.submit([{"path": self.pdf, "name": "sach4.pdf"}], base)
        return jid, self.mgr.wait(jid)

    def read(self, jid, rel):
        with open(self.mgr.abs_path(jid, rel), encoding="utf-8") as f:
            return f.read()

    def zip_names(self, jid):
        with zipfile.ZipFile(os.path.join(self.mgr.job_dir(jid), "ketqua.zip")) as zf:
            return sorted(zf.namelist())


class TestFrontmatterOption(ObsBase):
    def test_frontmatter_added_to_md_but_not_to_preview_text(self):
        jid, job = self.run_job(obsidian_frontmatter=True)
        f = job["files"][0]
        md = self.read(jid, next(o["rel"] for o in f["outputs"] if o["kind"] == "md"))
        self.assertTrue(md.startswith("---\n"))
        for key in ('title: "Chapter 1: The Italian Game"', 'source: "sach4.pdf"', 'engine: "fake"', "pages: 4"):
            self.assertIn(key, md)
        self.assertRegex(md, r"date: \"\d{4}-\d\d-\d\d\"")
        self.assertFalse(self.read(jid, "f01/raw.md").startswith("---"))     # xem trước/raw không có frontmatter
        self.assertTrue(any("frontmatter YAML" in n for n in f["notes"]))
        self.assertEqual(len(fen_tools.list_boards(md)), 4)                  # thân văn bản không đổi

    def test_off_by_default(self):
        jid, job = self.run_job()
        md = self.read(jid, next(o["rel"] for o in job["files"][0]["outputs"] if o["kind"] == "md"))
        self.assertFalse(md.startswith("---"))
        self.assertFalse(os.path.exists(os.path.join(self.mgr.file_dir(jid, 0), "out", "chapters")))
        self.assertEqual(self.zip_names(jid), ["sach4.md", "sach4_fen.txt"])

    def test_translated_file_is_flagged(self):
        jid, job = self.run_job(obsidian_frontmatter=True, translate_vn=True, merge=False)
        outs = {o["kind"]: o["rel"] for o in job["files"][0]["outputs"]}
        self.assertIn("translated: true", self.read(jid, outs["vn"]))
        self.assertNotIn("translated:", self.read(jid, outs["md"]))
        self.assertIn('translate_model: "fake"', self.read(jid, outs["vn"]))


class TestSplitOption(ObsBase):
    def test_chapters_go_only_into_the_zip(self):
        jid, job = self.run_job(obsidian_split=True)
        f = job["files"][0]
        self.assertEqual(sorted(o["name"] for o in f["outputs"]), ["sach4.md", "sach4_fen.txt"])   # không liệt kê chương
        names = self.zip_names(jid)
        chapters = [n for n in names if n.startswith("sach4/")]
        self.assertEqual(len(chapters), 4)
        self.assertEqual(chapters[0], "sach4/01-Chapter 1 The Italian Game.md")
        self.assertTrue(any("tách 4 chương" in n for n in f["notes"]))
        with zipfile.ZipFile(os.path.join(self.mgr.job_dir(jid), "ketqua.zip")) as zf:
            body = zf.read(chapters[1]).decode("utf-8")
        self.assertTrue(body.startswith("# Chapter 2"))                      # không bật frontmatter -> không có khối ---
        self.assertIn("```chessboard", body)

    def test_split_with_frontmatter_adds_book_and_chapter_number(self):
        jid, job = self.run_job(obsidian_split=True, obsidian_frontmatter=True)
        with zipfile.ZipFile(os.path.join(self.mgr.job_dir(jid), "ketqua.zip")) as zf:
            body = zf.read("sach4/03-Chapter 3 The Italian Game.md").decode("utf-8")
        self.assertTrue(body.startswith("---\n"))
        self.assertIn("chapter: 3", body)
        self.assertIn('book: "Chapter 1: The Italian Game"', body)
        self.assertIn('title: "Chapter 3: The Italian Game"', body)

    def test_document_without_h1_reports_nothing_to_split(self):
        with mock.patch.dict(os.environ, {"MID_FAKE_H1": "0"}):
            jid, job = self.run_job(obsidian_split=True)
        self.assertTrue(any("không có tiêu đề `#`" in n for n in job["files"][0]["notes"]))
        self.assertEqual([n for n in self.zip_names(jid) if "/" in n], [])

    def test_single_output_job_still_gets_a_zip_when_chapters_exist(self):
        jid, job = self.run_job(obsidian_split=True, mode_label="📄 Tài liệu thường (chế độ gốc)")
        self.assertEqual([o["name"] for o in job["files"][0]["outputs"]], ["sach4.md"])      # chỉ một tệp kết quả
        self.assertEqual(len([n for n in self.zip_names(jid) if n.startswith("sach4/")]), 4)


class TestReviewRebuildsChapters(ObsBase):
    def test_fen_fix_updates_chapter_files_and_keeps_one_frontmatter(self):
        jid, job = self.run_job(obsidian_split=True, obsidian_frontmatter=True)
        review.apply_fen(self.mgr, jid, 0, 2, NEW)
        with zipfile.ZipFile(os.path.join(self.mgr.job_dir(jid), "ketqua.zip")) as zf:
            ch2 = zf.read("sach4/02-Chapter 2 The Italian Game.md").decode("utf-8")
            ch1 = zf.read("sach4/01-Chapter 1 The Italian Game.md").decode("utf-8")
        self.assertIn(NEW, ch2)
        self.assertNotIn(NEW, ch1)
        self.assertEqual(ch2.count("\n---\n"), 1)                              # frontmatter không bị nhân đôi
        md_rel = next(o["rel"] for o in self.mgr.get(jid)["files"][0]["outputs"] if o["kind"] == "md")
        md = self.read(jid, md_rel)
        self.assertTrue(md.startswith("---\n"))
        self.assertEqual(md.count("\n---\n"), 1)                              # tệp .md chính cũng chỉ có một khối frontmatter
        self.assertNotIn("title:", obsidian.strip_frontmatter(md).split("\n# ")[0])
        self.assertEqual(fen_tools.list_boards(md)[1]["fen"], NEW)


if __name__ == "__main__":
    unittest.main()
