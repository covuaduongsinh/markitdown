"""review.py: sửa FEN ghi đúng mọi nơi, đối chiếu trang, ảnh trang. Công việc thật bằng engine giả."""

import os
import shutil
import tempfile
import unittest
from unittest import mock

import tests_gui._setup  # noqa: F401  (phải import trước mã ứng dụng)
import fen_tools
import jobs
import review
from tests_gui.sample_pdf import make_sample_pdf

NEW = "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"


class ReviewBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mid_test_review_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.pdf = make_sample_pdf(os.path.join(self.tmp, "sach4.pdf"), 4)
        self.mgr = jobs.JobManager(os.path.join(self.tmp, "data"))
        os.environ["MID_FAKE_DELAY"] = "0"
        os.environ.pop("MID_FAKE_FAIL_PAGES", None)

    def run_job(self, **opts):
        base = dict(engine="fake", ocr_model="fake", translate_model="fake", board_dpi="200")
        base.update(opts)
        jid = self.mgr.submit([{"path": self.pdf, "name": "sach4.pdf"}], base)
        return jid, self.mgr.wait(jid)

    def read(self, jid, rel):
        with open(self.mgr.abs_path(jid, rel), encoding="utf-8") as f:
            return f.read()


class TestLoadBoards(ReviewBase):
    def test_boards_with_pages(self):
        jid, job = self.run_job(translate_vn=False)
        boards = review.load_boards(self.mgr, job, 0)
        self.assertEqual([b["n"] for b in boards], [1, 2, 3, 4])
        self.assertEqual([b["page"] for b in boards], [1, 2, 3, 4])
        self.assertTrue(all(b["valid"] for b in boards))

    def test_main_output_prefers_md_over_vn(self):
        jid, job = self.run_job(translate_vn=True, merge=False)
        self.assertEqual(review.main_output(job["files"][0])["kind"], "md")
        jid2, job2 = self.run_job(translate_vn=True, merge=True)
        self.assertEqual(review.main_output(job2["files"][0])["kind"], "vn")

    def test_failed_pages_do_not_break_the_page_mapping(self):
        with mock.patch.dict(os.environ, {"MID_FAKE_FAIL_PAGES": "2"}):
            jid, job = self.run_job(translate_vn=False)
        boards = review.load_boards(self.mgr, job, 0)
        self.assertEqual([b["page"] for b in boards], [1, 3, 4])


class TestApplyFen(ReviewBase):
    def test_writes_everywhere_and_survives_resume_assembly(self):
        jid, job = self.run_job(translate_vn=True, merge=False)
        out = review.apply_fen(self.mgr, jid, 0, 2, NEW)
        self.assertEqual(out["page"], 2)
        self.assertEqual(sorted(out["files"]), sorted(["sach4.md", "sach4_vn.md", "raw.md", "0002.md"]))
        job = self.mgr.get(jid)
        f = job["files"][0]
        rels = {o["kind"]: o["rel"] for o in f["outputs"]}
        for kind in ("md", "vn"):
            self.assertEqual(fen_tools.list_boards(self.read(jid, rels[kind]))[1]["fen"], NEW)
        self.assertEqual(fen_tools.list_boards(self.read(jid, "f01/raw.md"))[1]["fen"], NEW)
        self.assertIn(NEW, self.read(jid, "f01/pages/0002.md"))           # điểm lưu trang: "Chạy tiếp" không làm mất sửa
        fen_lines = self.read(jid, rels["fen"]).splitlines()
        self.assertEqual(len(fen_lines), 4)
        self.assertEqual(fen_lines[1], NEW)
        self.assertNotEqual(fen_lines[0], NEW)
        import zipfile
        with zipfile.ZipFile(os.path.join(self.mgr.job_dir(jid), "ketqua.zip")) as zf:
            self.assertEqual(zf.read("sach4_fen.txt").decode("utf-8").splitlines()[1], NEW)

    def test_merge_mode_edits_only_vn(self):
        jid, job = self.run_job(translate_vn=True, merge=True)
        out = review.apply_fen(self.mgr, jid, 0, 1, NEW)
        self.assertEqual(sorted(out["files"]), sorted(["sach4_vn.md", "raw.md", "0001.md"]))

    def test_invalid_fen_or_index_writes_nothing(self):
        jid, job = self.run_job(translate_vn=False)
        rel = job["files"][0]["outputs"][0]["rel"]
        before = self.read(jid, rel)
        for bad_n, bad_fen in ((9, NEW), (0, NEW), (1, "rác"), (1, "")):
            with self.assertRaises(review.ReviewError):
                review.apply_fen(self.mgr, jid, 0, bad_n, bad_fen)
        self.assertEqual(self.read(jid, rel), before)

    def test_refuses_running_job_and_unknown_job(self):
        os.environ["MID_FAKE_DELAY"] = "0.5"
        os.environ["MID_FAKE_DELAY_SCALE"] = "1"
        try:
            jid = self.mgr.submit([{"path": self.pdf, "name": "a.pdf"}], dict(engine="fake", ocr_model="fake", translate_vn=False))
            with self.assertRaises(review.ReviewError):
                review.apply_fen(self.mgr, jid, 0, 1, NEW)
            self.mgr.cancel(jid)
            self.mgr.wait(jid, timeout=10)
        finally:
            os.environ["MID_FAKE_DELAY"] = "0"
            os.environ.pop("MID_FAKE_DELAY_SCALE", None)
        with self.assertRaises(review.ReviewError):
            review.apply_fen(self.mgr, "khong-co", 0, 1, NEW)


class TestPageCompare(ReviewBase):
    def test_page_list_and_filters(self):
        with mock.patch.dict(os.environ, {"MID_FAKE_FAIL_PAGES": "3"}):
            jid, job = self.run_job(translate_vn=False)
        rows = review.page_list(self.mgr, job, 0)
        self.assertEqual([r["page"] for r in rows], [1, 2, 3, 4])
        self.assertEqual([r["ok"] for r in rows], [True, True, False, True])
        self.assertIn("giả lập lỗi OCR", rows[2]["error"])
        self.assertEqual([r["page"] for r in review.page_list(self.mgr, job, 0, "errors")], [3])
        self.assertEqual([r["page"] for r in review.page_list(self.mgr, job, 0, "boards")], [1, 2, 4])
        self.assertEqual(rows[0]["boards"], 1)

    def test_page_thumb_is_created_once_and_cached(self):
        jid, job = self.run_job(translate_vn=False)
        p = review.page_thumb(self.mgr, job, 0, 2)
        self.assertTrue(p and p.endswith("0002.jpg") and os.path.getsize(p) > 0)
        from PIL import Image
        with Image.open(p) as im:
            self.assertLessEqual(im.width, review.THUMB_MAX_WIDTH)
        m1 = os.path.getmtime(p)
        self.assertEqual(review.page_thumb(self.mgr, job, 0, 2), p)
        self.assertEqual(os.path.getmtime(p), m1)
        self.assertIsNone(review.page_thumb(self.mgr, job, 0, 99))
        # ảnh .jpg trong thư mục trang không làm hỏng việc nạp điểm lưu/chạy tiếp
        self.assertEqual(sorted(jobs.JobManager._load_done_pages(os.path.dirname(p), None)), [1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()
