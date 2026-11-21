"""Công việc nền (jobs.py): điểm lưu, Dừng thật, chạy tiếp, khoảng trang, khôi phục sau khởi động lại. Engine giả."""

import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from unittest import mock

import tests_gui._setup  # noqa: F401  (phải import trước mã ứng dụng)
import claude_translate
import fake_engine
import jobs
import pipeline
from tests_gui.sample_pdf import make_sample_pdf


class JobsBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mid_test_jobs_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.pdf = make_sample_pdf(os.path.join(self.tmp, "sach6.pdf"), 6)
        self.mgr = jobs.JobManager(os.path.join(self.tmp, "data"), keep_days=60)
        fake_engine.reset_calls()
        for k in ("MID_FAKE_FAIL_PAGES", "MID_FAKE_DELAY_SCALE"):
            os.environ.pop(k, None)
        os.environ["MID_FAKE_DELAY"] = "0"

    def submit(self, creds=None, **opts):
        base = dict(engine="fake", ocr_model="fake", translate_model="fake", board_dpi="200")
        base.update(opts)
        return self.mgr.submit([{"path": self.pdf, "name": "sach6.pdf"}], base, creds)

    def ocr_calls(self):
        return [pages for kind, pages in fake_engine.CALLS if kind == "ocr"]

    def read(self, job_id, rel):
        with open(self.mgr.abs_path(job_id, rel), encoding="utf-8") as f:
            return f.read()


class TestFullRun(JobsBase):
    def test_done_with_all_outputs_and_checkpoints(self):
        jid = self.submit(creds={"api_key": "BI-MAT-12345"})
        job = self.mgr.wait(jid)
        self.assertEqual(job["status"], jobs.DONE, job)
        f = job["files"][0]
        self.assertEqual(f["status"], "done")
        self.assertEqual((f["pages_done"], f["pages_total"], f["pages_failed"]), (6, 6, 0))
        self.assertEqual(sorted(o["name"] for o in f["outputs"]), ["sach6.md", "sach6_fen.txt", "sach6_vn.md"])
        self.assertEqual(sorted(os.listdir(os.path.join(self.mgr.file_dir(jid, 0), "pages"))), [f"{i:04d}.md" for i in range(1, 7)])
        self.assertIn("Chương 6: Khai cuộc Ý", self.read(jid, f["outputs"][1]["rel"]))
        self.assertTrue(os.path.exists(os.path.join(self.mgr.job_dir(jid), "ketqua.zip")))
        self.assertEqual(self.read(jid, "f01/raw.md").count("```chessboard"), 6)

    def test_job_json_never_stores_credentials(self):
        jid = self.submit(creds={"api_key": "BI-MAT-12345", "dropbox_token": "sl.TOKEN-XYZ"})
        self.mgr.wait(jid)
        text = self.read(jid, "job.json")
        self.assertNotIn("BI-MAT-12345", text)
        self.assertNotIn("sl.TOKEN-XYZ", text)
        self.assertEqual(self.mgr._creds.get(jid), None)  # RAM cũng được xóa khi xong

    def test_merge_mode_writes_only_vn(self):
        jid = self.submit(merge=True, ocr_pages_per_call="2")
        job = self.mgr.wait(jid)
        self.assertEqual(sorted(o["name"] for o in job["files"][0]["outputs"]), ["sach6_fen.txt", "sach6_vn.md"])
        self.assertEqual(len([c for c in fake_engine.CALLS if c[0] == "translate"]), 0)


class TestPageRange(JobsBase):
    def test_range_calls_exactly_the_selected_pages(self):
        jid = self.submit(page_spec="2-4", translate_vn=False)
        job = self.mgr.wait(jid)
        self.assertEqual(job["status"], jobs.DONE)
        self.assertEqual(sorted(sum(self.ocr_calls(), [])), [2, 3, 4])
        self.assertEqual(len(self.ocr_calls()), 3)
        raw = self.read(jid, "f01/raw.md")
        self.assertIn("Chapter 2", raw)
        self.assertIn("Chapter 4", raw)
        self.assertNotIn("Chapter 1", raw)
        self.assertNotIn("Chapter 5", raw)
        self.assertEqual((job["files"][0]["pages_done"], job["files"][0]["pages_total"]), (3, 3))

    def test_invalid_range_marks_file_error_without_calling_ai(self):
        jid = self.submit(page_spec="abc")
        job = self.mgr.wait(jid)
        self.assertEqual(job["status"], jobs.ERROR)
        self.assertIn("Khoảng trang không hợp lệ", job["files"][0]["error"])
        self.assertEqual(self.ocr_calls(), [])


class TestResumeAndRetry(JobsBase):
    def test_retry_only_failed_pages(self):
        with mock.patch.dict(os.environ, {"MID_FAKE_FAIL_PAGES": "3,5"}):
            jid = self.submit(translate_vn=False)
            job = self.mgr.wait(jid)
        f = job["files"][0]
        self.assertEqual((job["status"], f["pages_failed"]), (jobs.DONE, 2))
        self.assertTrue(self.mgr.is_resumable(job))
        self.assertIn("Lỗi OCR trang 3", self.read(jid, "f01/raw.md"))
        self.assertTrue(os.path.exists(os.path.join(self.mgr.file_dir(jid, 0), "pages", "0003.err")))

        fake_engine.reset_calls()
        self.assertTrue(self.mgr.resume(jid))
        job = self.mgr.wait(jid)
        f = job["files"][0]
        self.assertEqual(sorted(sum(self.ocr_calls(), [])), [3, 5])  # chỉ 2 lượt gọi AI, không làm lại cả cuốn
        self.assertEqual((job["status"], f["pages_failed"]), (jobs.DONE, 0))
        raw = self.read(jid, "f01/raw.md")
        self.assertNotIn("Lỗi OCR", raw)
        self.assertEqual(raw.count("```chessboard"), 6)
        self.assertFalse(self.mgr.is_resumable(job))
        self.assertFalse(self.mgr.resume(jid))  # không còn gì để làm

    def test_translation_chunks_are_cached_by_content(self):
        cache = jobs.DiskChunkCache(os.path.join(self.tmp, "tr"))
        md = "## Chapter 1: The Italian Game\n\nWhite develops the knight and the bishop toward the centre of the board."
        fake_engine.reset_calls()
        first = claude_translate.translate_markdown_vn(md, engine="fake", chunk_cache=cache)
        n_first = len([c for c in fake_engine.CALLS if c[0] == "translate"])
        second = claude_translate.translate_markdown_vn(md, engine="fake", chunk_cache=cache)
        n_total = len([c for c in fake_engine.CALLS if c[0] == "translate"])
        self.assertEqual(first, second)
        self.assertGreaterEqual(n_first, 1)
        self.assertEqual(n_total, n_first)  # lần hai toàn bộ từ điểm lưu
        self.assertIn("Chương 1: Khai cuộc Ý", first)


class TestCancel(JobsBase):
    def test_stop_kills_work_fast_and_keeps_finished_pages(self):
        os.environ["MID_FAKE_DELAY"] = "0.6"
        os.environ["MID_FAKE_DELAY_SCALE"] = "1"  # trang 1 xong ở 0,6 s; trang 6 ở 3,6 s
        jid = self.submit(translate_vn=False)
        pages_dir = os.path.join(self.mgr.file_dir(jid, 0), "pages")
        deadline = time.time() + 20
        while time.time() < deadline and not os.path.exists(os.path.join(pages_dir, "0001.md")):
            time.sleep(0.05)
        t0 = time.time()
        self.assertTrue(self.mgr.cancel(jid))
        job = self.mgr.wait(jid, timeout=10)
        self.assertLess(time.time() - t0, 3.0)
        self.assertEqual(job["status"], jobs.CANCELLED)
        self.assertEqual(job["files"][0]["status"], "cancelled")
        time.sleep(0.3)
        left = [t.name for t in threading.enumerate() if t.name.startswith("ThreadPoolExecutor")]
        self.assertEqual(left, [], "còn luồng OCR của công việc đã dừng")
        kept = sorted(n for n in os.listdir(pages_dir) if n.endswith(".md"))
        self.assertIn("0001.md", kept)
        self.assertLess(len(kept), 6)  # trang chưa xong thì chưa có

        # Chạy tiếp: chỉ làm các trang còn thiếu
        os.environ["MID_FAKE_DELAY"] = "0"
        os.environ["MID_FAKE_DELAY_SCALE"] = "0"
        fake_engine.reset_calls()
        self.assertTrue(self.mgr.resume(jid))
        job = self.mgr.wait(jid)
        self.assertEqual(job["status"], jobs.DONE)
        redone = sorted(sum(self.ocr_calls(), []))
        self.assertEqual(redone, [p for p in range(1, 7) if f"{p:04d}.md" not in kept])

    def test_cancel_while_queued(self):
        os.environ["MID_FAKE_DELAY"] = "1.0"
        first = self.submit(translate_vn=False)
        second = self.submit(translate_vn=False)  # MAX 1 công việc một lúc -> phải chờ
        self.assertTrue(self.mgr.cancel(second))
        self.assertEqual(self.mgr.get(second)["status"], jobs.CANCELLED)
        self.mgr.cancel(first)
        self.mgr.wait(first, timeout=10)
        self.assertEqual(self.mgr.get(second)["files"][0]["status"], "cancelled")
        self.assertFalse(os.path.exists(os.path.join(self.mgr.file_dir(second, 0), "pages")))  # chưa hề chạy

    def test_run_cli_kills_real_child_process_tree(self):
        import subprocess
        import sys

        import proc_control

        token = proc_control.CancelToken()
        threading.Timer(0.7, token.cancel).start()
        t0 = time.time()
        with proc_control.use_token(token):
            with self.assertRaises(proc_control.OperationCancelled):
                proc_control.run_cli([sys.executable, "-c", "import time; time.sleep(60)"], timeout=120)
        self.assertLess(time.time() - t0, 5.0)

        # Quá giờ: diệt tiến trình và ném TimeoutExpired như subprocess.run
        with self.assertRaises(subprocess.TimeoutExpired):
            proc_control.run_cli([sys.executable, "-c", "import time; time.sleep(60)"], timeout=0.5)


class TestRecoveryAndHousekeeping(JobsBase):
    def test_restart_marks_running_job_resumable(self):
        jid = self.submit(translate_vn=False)
        self.mgr.wait(jid)
        path = os.path.join(self.mgr.job_dir(jid), "job.json")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        data["status"] = "running"
        data["files"][0]["status"] = "running"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        mgr2 = jobs.JobManager(os.path.join(self.tmp, "data"))
        job = mgr2.get(jid)
        self.assertEqual(job["status"], jobs.ERROR)
        self.assertIn("khởi động lại", job["message"])
        self.assertTrue(mgr2.is_resumable(job))

    def test_cleanup_old_and_delete(self):
        old = self.submit(translate_vn=False)
        new = self.submit(translate_vn=False)
        self.mgr.wait(old)
        self.mgr.wait(new)
        self.mgr._jobs[old]["updated"] = time.time() - 61 * 86400
        self.assertEqual(self.mgr.cleanup_old(), 1)
        self.assertIsNone(self.mgr.get(old))
        self.assertFalse(os.path.exists(self.mgr.job_dir(old)))
        self.assertIsNotNone(self.mgr.get(new))
        self.assertGreater(self.mgr.disk_usage(), 0)
        self.assertTrue(self.mgr.delete(new))
        self.assertEqual(self.mgr.list_jobs(), [])

    def test_abs_path_blocks_traversal(self):
        jid = self.submit(translate_vn=False)
        self.mgr.wait(jid)
        with self.assertRaises(ValueError):
            self.mgr.abs_path(jid, "../../etc/passwd")
        self.assertTrue(self.mgr.abs_path(jid, "job.json").endswith("job.json"))


class TestPageRangeParser(unittest.TestCase):
    def test_parse(self):
        self.assertIsNone(pipeline.parse_page_ranges("  ", 10))
        self.assertEqual(pipeline.parse_page_ranges("1-3, 5;8 3", 10), {1, 2, 3, 5, 8})
        self.assertEqual(pipeline.parse_page_ranges("8-99", 10), {8, 9, 10})  # cắt theo số trang của tệp
        for bad in ("x", "5-2", "0", "11-20"):
            with self.assertRaises(ValueError):
                pipeline.parse_page_ranges(bad, 10)

    def test_estimate(self):
        self.assertEqual(pipeline.estimate_ocr_calls(97, 1), 97)
        self.assertEqual(pipeline.estimate_ocr_calls(97, 3), 33)
        self.assertEqual(pipeline.estimate_ocr_calls(0, 2), 0)


if __name__ == "__main__":
    unittest.main()
