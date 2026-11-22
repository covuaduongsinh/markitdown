"""review_handlers: tab Thế cờ và Đối chiếu trang ở tầng handler (không cần trình duyệt)."""

import os
import shutil
import tempfile
import unittest
from unittest import mock

import gradio as gr

import tests_gui._setup  # noqa: F401  (phải import trước mã ứng dụng)
import fen_tools
import jobs
import review_handlers as rh
from tests_gui.sample_pdf import make_sample_pdf

NEW = "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"


class HandlerBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mid_test_rh_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.mgr = jobs.JobManager(os.path.join(self.tmp, "data"))
        old = jobs._MANAGER
        jobs._MANAGER = self.mgr
        self.addCleanup(setattr, jobs, "_MANAGER", old)
        os.environ["MID_FAKE_DELAY"] = "0"
        os.environ.pop("MID_FAKE_FAIL_PAGES", None)
        pdf = make_sample_pdf(os.path.join(self.tmp, "s.pdf"), 4)
        self.jid = self.mgr.submit(
            [{"path": pdf, "name": "s.pdf"}],
            dict(engine="fake", ocr_model="fake", translate_vn=False, board_dpi="200"),
        )
        self.mgr.wait(self.jid)


class TestFenTab(HandlerBase):
    def test_refresh_builds_table_and_first_board(self):
        info, rows, idx, text, preview, link, msg = rh.fen_refresh(self.jid, None)
        self.assertIn("<b>4</b> thế cờ", info)
        self.assertEqual([r[0] for r in rows], [1, 2, 3, 4])
        self.assertEqual([r[1] for r in rows], [1, 2, 3, 4])      # trang
        self.assertEqual(idx, 1)
        self.assertEqual(text, rows[0][2])
        self.assertIn("mid-fenboard", preview)
        self.assertIn("lichess.org/editor/", link)

    def test_no_job_gives_empty_view(self):
        out = rh.fen_refresh("", None)
        self.assertEqual(len(out), rh.FEN_OUTPUTS_N)
        self.assertEqual(out[1], [])
        self.assertIn("Chưa có thế cờ", out[0])

    def test_goto_clamps_and_steps(self):
        self.assertEqual(rh.fen_goto(self.jid, None, 99)[2], 4)
        self.assertEqual(rh.fen_goto(self.jid, None, 0)[2], 1)
        self.assertEqual(rh.fen_goto(self.jid, None, None)[2], 1)
        self.assertEqual(rh.fen_step(self.jid, None, 2, 1)[2], 3)
        self.assertEqual(rh.fen_step(self.jid, None, 1, -1)[2], 1)

    def test_select_event_maps_row_to_board(self):
        evt = gr.SelectData(None, {"index": [2, 0], "value": 3})
        out = rh.fen_select(self.jid, None, evt)
        self.assertEqual(out[2], 3)

    def test_flip_and_preview_do_not_write(self):
        text = rh.fen_goto(self.jid, None, 1)[3]
        flipped, preview, link = rh.fen_flip(text)
        self.assertEqual(fen_tools.flip_fen(flipped), text)
        self.assertIn("mid-fenboard", preview)
        self.assertEqual(rh.fen_goto(self.jid, None, 1)[3], text)      # chưa ghi gì
        prev, _ = rh.fen_preview("xyz")
        self.assertIn("Cần xem", prev)

    def test_apply_updates_table_and_reports_files(self):
        out = rh.fen_apply(self.jid, None, 2, NEW)
        info, rows, idx, text, preview, link, msg = out
        self.assertEqual(rows[1][2], NEW)
        self.assertEqual(idx, 2)
        self.assertEqual(text, NEW)
        self.assertIn("Đã ghi thế cờ số 2 (trang 2)", msg)
        self.assertIn("raw.md", msg)

    def test_apply_errors_are_shown_not_raised(self):
        out = rh.fen_apply(self.jid, None, 2, "rác")
        self.assertIn("FEN không hợp lệ", out[-1])
        self.assertEqual(out[1][1][2], rh.fen_goto(self.jid, None, 2)[1][1][2])   # bảng không đổi
        out = rh.fen_apply(self.jid, None, 99, NEW)
        self.assertIn("Không có thế cờ số 99", out[-1])
        self.assertIn("Chưa có tệp", rh.fen_apply("", None, 1, NEW)[-1])

    def test_invalid_board_is_flagged_in_table(self):
        rh.fen_apply(self.jid, None, 3, "8/8/8/8/8/8/8/4K3 w - - 0 1")     # thiếu Vua đen: ghi được nhưng báo "cần xem"
        info, rows, *_ = rh.fen_refresh(self.jid, None)
        self.assertEqual(rows[2][3], "⚠️ cần xem")
        self.assertIn("1 cần xem", info)


class TestCompareTab(HandlerBase):
    def test_load_first_page_with_image_and_markdown(self):
        page, img, md, info = rh.cmp_load(self.jid, None, rh.CMP_FILTERS[0], None)
        self.assertEqual(page, 1)
        self.assertIn("mid-cmp-img", img)
        self.assertIn("/gradio_api/file=", img)
        self.assertIn("```chessboard", md)
        self.assertIn("Trang <b>1</b> (1/4", info)

    def test_steps_and_clamping(self):
        flt = rh.CMP_FILTERS[0]
        self.assertEqual(rh.cmp_step(self.jid, None, flt, 1, 1)[0], 2)
        self.assertEqual(rh.cmp_step(self.jid, None, flt, 4, 1)[0], 4)
        self.assertEqual(rh.cmp_step(self.jid, None, flt, 1, -1)[0], 1)
        self.assertEqual(rh.cmp_load(self.jid, None, flt, 99)[0], 4)

    def test_error_filter_and_error_page_text(self):
        with mock.patch.dict(os.environ, {"MID_FAKE_FAIL_PAGES": "2"}):
            pdf = make_sample_pdf(os.path.join(self.tmp, "e.pdf"), 4)
            jid = self.mgr.submit(
                [{"path": pdf, "name": "e.pdf"}], dict(engine="fake", ocr_model="fake", translate_vn=False, board_dpi="200"),
            )
            self.mgr.wait(jid)
        page, img, md, info = rh.cmp_load(jid, None, rh.CMP_FILTERS[1], None)
        self.assertEqual(page, 2)
        self.assertIn("OCR lỗi", md)
        self.assertIn("lỗi", info)
        page, _img, _md, info = rh.cmp_load(self.jid, None, rh.CMP_FILTERS[1], None)
        self.assertIsNone(page)
        self.assertIn("Không có trang nào khớp", info)
        self.assertEqual(rh.cmp_load("", None, rh.CMP_FILTERS[0], None)[0], None)


if __name__ == "__main__":
    unittest.main()
