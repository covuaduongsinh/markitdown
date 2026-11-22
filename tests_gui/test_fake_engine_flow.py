"""Luồng đầu-cuối bằng engine giả qua công việc nền: PDF mẫu 6 trang -> .md, _vn.md, _fen.txt. Không gọi AI/Dropbox thật."""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import tests_gui._setup  # noqa: F401  (phải import trước mã ứng dụng)
import gradio as gr
import claude_ocr
import job_handlers
import jobs
import markitdown_gui as g
import pipeline
from tests_gui.sample_pdf import make_sample_pdf


def _refuse_subprocess(*_a, **_k):
    raise AssertionError("Engine giả không được chạy tiến trình con (agy/claude)")


class FlowBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mid_test_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.pdf = make_sample_pdf(os.path.join(self.tmp, "mid_test_mau6.pdf"), 6)
        os.environ.pop("MID_FAKE_FAIL_PAGES", None)
        self.job_id = None

    def run_flow(self, mode, translate, merge, pages="1", autosave_dir="", force_ocr=True):
        """Bấm Chuyển đổi (tạo công việc nền), chờ xong, vẽ lại như Timer. Trả (preview, raw, download_html, status)."""
        mgr = jobs.get_manager()
        with mock.patch.object(subprocess, "run", _refuse_subprocess), \
                mock.patch.object(subprocess, "Popen", _refuse_subprocess):
            started = job_handlers.on_start_job(
                [self.pdf], mode, False, True,
                "fake", "auto", "fake", "low",
                force_ocr, "200", translate, merge, pages,
                bool(autosave_dir), False, autosave_dir, [], pipeline.AUTOSAVE_CUSTOM, "fake",
                dropbox_sync_on=False,
            )
            self.job_id = started[0]
            mgr.wait(self.job_id, timeout=120)
        status, preview, raw, downloads = job_handlers.render_job(self.job_id, "")[:4]
        return preview, raw, downloads, status

    def output_text(self, name):
        mgr = jobs.get_manager()
        for f in mgr.get(self.job_id)["files"]:
            for o in f["outputs"]:
                if o["name"] == name:
                    with open(mgr.abs_path(self.job_id, o["rel"]), encoding="utf-8") as fh:
                        return fh.read()
        raise AssertionError(f"không có tệp kết quả {name}")

    @staticmethod
    def files_in(download_html):
        return sorted(set(re.findall(r"mid_test_mau6[^\s`<>\"')/]*\.(?:md|txt)", download_html or "")))


class TestEngineBasics(unittest.TestCase):
    def test_fake_engine_is_default_and_listed(self):
        from ai_engine import ENGINE_FAKE, ENGINE_LABELS, get_default_engine, is_engine_available
        self.assertTrue(is_engine_available(ENGINE_FAKE))
        self.assertEqual(get_default_engine(), ENGINE_FAKE)
        self.assertIn(ENGINE_FAKE, [v for _, v in ENGINE_LABELS])

    def test_fake_engine_unavailable_without_env(self):
        from ai_engine import ENGINE_FAKE, is_engine_available
        with mock.patch.dict(os.environ, {"MID_FAKE_ENGINE": "0"}):
            self.assertFalse(is_engine_available(ENGINE_FAKE))


class TestStartJobHandler(FlowBase):
    def test_no_files_gives_hint_and_no_job(self):
        out = job_handlers.on_start_job(
            [], g.MODE_CHESS, False, True, "fake", "auto", "fake", "low", True, "200", True, False, "1",
            False, False, "", [], pipeline.AUTOSAVE_CUSTOM, "fake",
        )
        self.assertEqual(out[0], "")
        self.assertIn("Chưa có tệp nào", out[1])

    def test_buttons_follow_job_state(self):
        # đang chạy: Chuyển đổi ẩn, Dừng hiện, Timer bật; xong: ngược lại
        os.environ["MID_FAKE_DELAY"] = "0.5"
        try:
            started = job_handlers.on_start_job(
                [self.pdf], g.MODE_CHESS, False, True, "fake", "auto", "fake", "low", True, "200",
                False, False, "1", False, False, "", [], pipeline.AUTOSAVE_CUSTOM, "fake",
            )
            self.job_id = started[0]
            running = job_handlers.render_job(self.job_id, "")
            self.assertFalse(running[6]["visible"])  # btn_file
            self.assertTrue(running[7]["visible"])   # btn_stop
            self.assertTrue(running[5].active)       # timer
            jobs.get_manager().wait(self.job_id, timeout=120)
        finally:
            os.environ["MID_FAKE_DELAY"] = "0"
        done = job_handlers.render_job(self.job_id, "")
        self.assertTrue(done[6]["visible"])
        self.assertFalse(done[7]["visible"])
        self.assertFalse(done[5].active)
        # chữ ký không đổi -> không gửi lại xem trước/tải về
        again = job_handlers.render_job(self.job_id, done[4])
        self.assertEqual(list(again[1:4]), [gr.skip()] * 3)
        self.assertEqual(again[4], done[4])


class TestChessSeparateTranslate(FlowBase):
    def test_outputs_and_translation(self):
        _prev, raw, dl, status = self.run_flow(g.MODE_CHESS, translate=True, merge=False)
        self.assertEqual(self.files_in(dl), ["mid_test_mau6.md", "mid_test_mau6_fen.txt", "mid_test_mau6_vn.md"])
        self.assertIn("Xong 1/1", status)
        self.assertEqual(raw.count("```chessboard"), 6)
        self.assertIn("Chapter 1", raw)  # OCR (chưa dịch) còn tiếng Anh
        vn = self.output_text("mid_test_mau6_vn.md")
        self.assertIn("Chương 6: Khai cuộc Ý", vn)
        self.assertEqual(vn.count("```chessboard"), 6)  # khối bàn cờ được bảo vệ khi dịch
        self.assertIn("2.Mf3 Mc6", vn)
        self.assertNotIn("Chapter", vn)
        self.assertEqual(len([ln for ln in self.output_text("mid_test_mau6_fen.txt").splitlines() if ln.strip()]), 6)


class TestChessMerged(FlowBase):
    def test_merge_skips_separate_translation(self):
        _prev, raw, dl, status = self.run_flow(g.MODE_CHESS, translate=True, merge=True, pages="2")
        files = self.files_in(dl)
        self.assertIn("mid_test_mau6_vn.md", files)
        self.assertNotIn("mid_test_mau6.md", files)  # gộp một bước chỉ ghi bản _vn
        self.assertIn("gộp 1 bước", status)
        self.assertEqual(status.count("Đã dịch bằng"), 0)  # không chạy pass dịch riêng
        self.assertIn("Chương 1", raw)
        self.assertEqual(raw.count("```chessboard"), 6)

    def test_translated_flag_is_structural(self):
        res = pipeline.convert_file(
            self.pdf, False, True, "fake", force_ocr=True, board_dpi_label="200", chess=True,
            merge_translate=True, ocr_pages_label="2 trang/lần", engine="fake",
        )
        self.assertTrue(res.translated)
        res = pipeline.convert_file(
            self.pdf, False, True, "fake", force_ocr=True, board_dpi_label="200", chess=True,
            merge_translate=False, engine="fake",
        )
        self.assertFalse(res.translated)


class TestGeneralMode(FlowBase):
    def test_no_boards_and_no_fen_file(self):
        _prev, raw, dl, _status = self.run_flow(g.MODE_GENERAL, translate=False, merge=False)
        self.assertEqual(self.files_in(dl), ["mid_test_mau6.md"])
        self.assertNotIn("chessboard", raw)


class TestFailedPages(FlowBase):
    def test_failed_pages_are_marked_and_others_survive(self):
        with mock.patch.dict(os.environ, {"MID_FAKE_FAIL_PAGES": "3,5"}):
            text = claude_ocr.ocr_pdf(self.pdf, engine="fake", chess=True, pages_per_call=1)
        errs = re.findall(r"\*\[Lỗi OCR trang (\d+)", text)
        self.assertEqual(errs, ["3", "5"])
        self.assertEqual(text.count("```chessboard"), 4)

    def test_all_pages_failing_raises(self):
        with mock.patch.dict(os.environ, {"MID_FAKE_FAIL_PAGES": "1,2,3,4,5,6"}):
            with self.assertRaises(claude_ocr.ClaudeOCRError):
                claude_ocr.ocr_pdf(self.pdf, engine="fake", chess=True)

    def test_status_offers_retry_button_for_failed_pages(self):
        with mock.patch.dict(os.environ, {"MID_FAKE_FAIL_PAGES": "3,5"}):
            _prev, _raw, _dl, status = self.run_flow(g.MODE_CHESS, translate=False, merge=False)
        self.assertIn("2 trang OCR bị lỗi", status)
        out = job_handlers.render_job(self.job_id, "")
        self.assertTrue(out[8]["visible"])
        self.assertEqual(out[8]["value"], "🔁 OCR lại 2 trang lỗi")


class TestAutosave(FlowBase):
    def test_autosave_copies_all_three_files(self):
        out = os.path.join(self.tmp, "luu")
        _prev, _raw, _dl, status = self.run_flow(g.MODE_CHESS, translate=True, merge=False, autosave_dir=out)
        self.assertEqual(
            sorted(os.listdir(out)), ["mid_test_mau6.md", "mid_test_mau6_fen.txt", "mid_test_mau6_vn.md"],
        )
        self.assertEqual(status.count("💾 [VPS] đã lưu"), 3)


class TestEstimate(FlowBase):
    def test_estimate_text(self):
        md = job_handlers.on_estimate([self.pdf], [], "2-4", "1")
        self.assertIn("3 lượt gọi OCR", md)
        self.assertIn("3/6 trang", md)
        self.assertIn("6 lượt gọi OCR", job_handlers.on_estimate([self.pdf], [], "", "1"))
        self.assertIn("2 lượt gọi OCR", job_handlers.on_estimate([self.pdf], [], "", "3"))
        self.assertIn("Khoảng trang không hợp lệ", job_handlers.on_estimate([self.pdf], [], "abc", "1"))
        self.assertEqual(job_handlers.on_estimate([], [], "", "1"), "")


if __name__ == "__main__":
    unittest.main()
