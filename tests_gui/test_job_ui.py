"""Phần hiển thị và handler của công việc nền: vẽ trạng thái, lịch sử, chữ ký, escape HTML. Engine giả."""

import os
import shutil
import tempfile
import time
import unittest

import gradio as gr

import tests_gui._setup  # noqa: F401  (phải import trước mã ứng dụng)
import job_handlers
import job_view
import jobs
import pipeline
from tests_gui.sample_pdf import make_sample_pdf


class UiBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mid_test_ui_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.mgr = jobs.JobManager(os.path.join(self.tmp, "data"))
        # handler dùng JobManager dùng chung -> trỏ nó vào manager riêng của test
        self._old = jobs._MANAGER
        jobs._MANAGER = self.mgr
        self.addCleanup(setattr, jobs, "_MANAGER", self._old)
        self.pdf = make_sample_pdf(os.path.join(self.tmp, "sach4.pdf"), 4)
        os.environ["MID_FAKE_DELAY"] = "0"

    def run_job(self, **opts):
        base = dict(engine="fake", ocr_model="fake", translate_model="fake", board_dpi="200", translate_vn=False)
        base.update(opts)
        jid = self.mgr.submit([{"path": self.pdf, "name": "sach4.pdf"}], base)
        return jid, self.mgr.wait(jid)


class TestStatusRendering(UiBase):
    def test_status_html_for_each_state(self):
        job = dict(
            id="x", status="running", message="", options={"translate_vn": True, "merge": False},
            started=100.0,
            files=[
                dict(idx=0, name="a<x>.pdf", status="done", notes=["✅ xong a"], outputs=[], pages_failed=0, pages_total=4),
                dict(idx=1, name="b.pdf", status="running", stage="ocr", pages_done=6, pages_total=12, started=100.0, outputs=[], pages_failed=0),
                dict(idx=2, name="c.pdf", status="pending", outputs=[], pages_failed=0),
            ],
        )
        h = job_view.render_status_html(job, now=130.0)
        self.assertIn("Đang xử lý…", h)                      # chip
        self.assertIn("Đang chuyển đổi 3 tệp", h)
        self.assertIn("trang 6/12", h)                       # thẻ bên phải của tệp đang chạy
        self.assertIn("OCR trang 6/12 · 30s", h)
        self.assertIn("a&lt;x&gt;.pdf", h)                    # tên tệp đã escape
        self.assertNotIn("a<x>", h)
        self.assertIn("is-done", h)
        self.assertIn("is-wait", h)
        self.assertIn('aria-valuenow="', h)                  # thanh tiến độ
        # OCR 6/12 trong tệp 2, có dịch riêng: (1 + 0.7*0.5)/3 = 45%
        self.assertEqual(job_view.progress_percent(job), 45)
        job["status"], job["message"] = "cancelled", "Đã dừng."
        job["files"][1]["status"] = "cancelled"
        h = job_view.render_status_html(job, now=130.0)
        self.assertIn("mid-chip-stopped", h)
        self.assertIn("6/12 trang được giữ lại", h)
        job["status"] = "done"
        job["files"][1]["status"] = job["files"][2]["status"] = "done"
        h = job_view.render_status_html(job, now=130.0)
        self.assertIn("Xong 3/3 tệp", h)
        self.assertIn('aria-valuenow="100"', h)

    def test_idle_and_message_html(self):
        self.assertIn("Kết quả Markdown sẽ hiện ở đây", job_view.idle_html())
        self.assertIn("Chưa chạy", job_view.idle_html())
        m = job_view.message_html("<b>x</b>" + chr(10) + "`y`", "warn")
        self.assertNotIn("<b>", m)
        self.assertIn("<br>", m)
        self.assertNotIn("`", m)

    def test_resume_label_and_signature(self):
        jid, job = self.run_job()
        self.assertEqual(job_view.resume_label(job), "▶ Chạy tiếp")
        s1 = job_view.signature(job)
        job["files"][0]["pages_failed"] = 2
        self.assertEqual(job_view.resume_label(job), "🔁 OCR lại 2 trang lỗi")
        self.assertNotEqual(job_view.signature(job), s1)

    def test_flag_html_escapes(self):
        html_ = job_view.flag_html(dict(id='a"b<c', status="done", files=[]))
        self.assertNotIn('a"b<c', html_)
        self.assertIn('data-state="done"', html_)
        self.assertIn('data-state="none"', job_view.flag_html(None))

    def test_download_panel_escapes_names(self):
        from ui_render import _download_panel

        p = os.path.join(self.tmp, 'x"><script>.md')  # chỉ dựng HTML, không cần tệp tồn tại (Windows không tạo được tên này)
        self.assertNotIn("<script>", _download_panel([p]))


class TestUrlConversion(UiBase):
    """G1.9: chuyển từ URL ngang hàng với tệp — tùy chọn dịch + dùng chung _publish_output."""

    def _fake_convert_url(self, url, enable_plugins):
        md = "## Chapter 1: The Italian Game" + chr(10) + chr(10) + "White develops the knight and the bishop toward the centre of the board."
        path = pipeline._write_md(md, "mid_test_url")
        return md, md, path, "✅ Thành công"

    def test_translate_autosave_and_download_panel(self):
        import markitdown_gui as g
        from unittest import mock

        out_dir = os.path.join(self.tmp, "luu")
        with mock.patch.object(g, "convert_url", self._fake_convert_url):
            preview, raw, downloads, status = g.on_convert_url(
                "https://example.org", False, True, False, "/MarkItDown", "", "", "", "",
                translate_vn=True, translate_model="fake", translate_effort="low", engine="fake",
                autosave_on=True, autosave_dir=out_dir, mode_label=pipeline.MODE_GENERAL,
            )
        self.assertIn("Chapter 1", preview)
        self.assertEqual(sorted(os.listdir(out_dir)), ["ketqua_url_vn.md", "mid_test_url.md"])  # bản gốc tên do hàm giả đặt; bản dịch luôn là ketqua_url_vn
        with open(os.path.join(out_dir, "ketqua_url_vn.md"), encoding="utf-8") as f:
            self.assertIn("Chương 1: Khai cuộc Ý", f.read())
        self.assertIn("ketqua_url_vn.md", downloads)
        self.assertIn("Đã dịch", status)
        self.assertIn("💾 [VPS] đã lưu", status)
        self.assertIn('data-auto-download="1"', downloads)
        self.assertNotIn("`", status)

    def test_failure_has_no_downloads(self):
        import markitdown_gui as g

        preview, raw, downloads, status = g.on_convert_url("", False)
        self.assertEqual(downloads, "")
        self.assertIn("mid-st-warn", status)


class TestQueue(UiBase):
    def test_queue_html_escapes_and_shows_meta(self):
        html_ = job_view.queue_html([('a<b>.pdf', 4300000, 12), ("ghi chu.docx", 2048, None), ("x.bin", None, None)])
        self.assertNotIn("<b>", html_)
        self.assertIn("3 tệp trong hàng đợi", html_)
        self.assertIn("PDF · 4.1 MB · 12 trang", html_)
        self.assertIn("Word · 2.0 KB", html_)
        self.assertIn("BIN", html_)  # loại lạ: dùng đuôi tệp
        self.assertEqual(html_.count("data-mid-queue-remove"), 3)
        self.assertIn("data-mid-queue-clear", html_)
        self.assertEqual(job_view.queue_html([]), "")
        self.assertNotIn("data-mid-queue-remove", job_view.queue_html([("a.pdf", 1, 1)], removable=False))

    def test_on_queue_reads_real_pdf(self):
        out = job_handlers.on_queue([self.pdf], [])
        self.assertIn("sach4.pdf", out)
        self.assertIn("4 trang", out)
        self.assertIn("data-mid-queue-remove", out)
        # tệp chọn bằng hộp thoại Windows: chỉ liệt kê, không có nút xóa
        self.assertNotIn("data-mid-queue-remove", job_handlers.on_queue([], [self.pdf]))
        self.assertEqual(job_handlers.on_queue([], []), "")


class TestHistory(UiBase):
    def test_labels_open_delete(self):
        jid, job = self.run_job()
        dd, usage = job_handlers.history_refresh()
        self.assertEqual(len(dd["choices"]), 1)
        label, value = dd["choices"][0]
        self.assertEqual(value, jid)
        self.assertIn("sach4.pdf", label)
        self.assertIn("✅ 1/1 tệp", label)
        self.assertIn("1 công việc", usage)
        self.assertIn("giữ 60 ngày", usage)

        opened = job_handlers.history_open(jid)
        self.assertEqual(opened[0], jid)
        self.assertIn("Xong 1/1", opened[1])           # status
        self.assertIn("sach4.md", opened[4])           # downloads
        self.assertNotIn('data-auto-download="1"', opened[4])  # mở lại không tự tải về máy
        self.assertEqual(job_handlers.history_open("khong-co")[0], "")

        dd, usage, cur = job_handlers.history_delete(jid, jid)
        self.assertEqual((dd["choices"], cur), ([], ""))
        self.assertIn("Đã xóa", usage)
        self.assertEqual(job_handlers.render_job(jid)[0], gr.skip())  # công việc không còn -> trạng thái rỗng

    def test_cannot_delete_running_job(self):
        os.environ["MID_FAKE_DELAY"] = "0.4"
        os.environ["MID_FAKE_DELAY_SCALE"] = "1"
        try:
            jid = self.mgr.submit(
                [{"path": self.pdf, "name": "sach4.pdf"}],
                dict(engine="fake", ocr_model="fake", board_dpi="200", translate_vn=False),
            )
            time.sleep(0.5)
            _dd, usage, _cur = job_handlers.history_delete(jid, "")
            self.assertIn("Không xóa được", usage)
            self.mgr.cancel(jid)
            self.mgr.wait(jid, timeout=10)
        finally:
            os.environ["MID_FAKE_DELAY"] = "0"
            os.environ.pop("MID_FAKE_DELAY_SCALE", None)


class TestStopAndResumeHandlers(UiBase):
    def test_stop_and_resume_roundtrip(self):
        os.environ["MID_FAKE_DELAY"] = "0.4"
        os.environ["MID_FAKE_DELAY_SCALE"] = "1"
        try:
            started = job_handlers.on_start_job(
                [self.pdf], pipeline.MODE_CHESS, False, True, "fake", "auto", "fake", "low", True, "200",
                False, False, "1", False, False, "", [], pipeline.AUTOSAVE_CUSTOM, "fake",
            )
            jid = started[0]
            time.sleep(0.8)
            self.assertIn("Đang dừng", job_handlers.on_stop_job(jid))
            job = self.mgr.wait(jid, timeout=10)
            self.assertEqual(job["status"], jobs.CANCELLED)
            view = job_handlers.render_job(jid, "")
            self.assertTrue(view[6]["visible"])        # nút Chuyển đổi trở lại
            self.assertTrue(view[8]["visible"])        # có nút Chạy tiếp
            os.environ["MID_FAKE_DELAY"] = "0"
            os.environ.pop("MID_FAKE_DELAY_SCALE", None)
            resumed = job_handlers.on_resume_job(jid)
            self.assertTrue(resumed[5].active)         # Timer bật lại
            self.assertEqual(self.mgr.wait(jid)["status"], jobs.DONE)
        finally:
            os.environ["MID_FAKE_DELAY"] = "0"
            os.environ.pop("MID_FAKE_DELAY_SCALE", None)

    def test_stop_without_job_is_noop(self):
        self.assertEqual(job_handlers.on_stop_job(""), gr.skip())
        self.assertEqual(job_handlers.on_stop_job("khong-co"), gr.skip())


if __name__ == "__main__":
    unittest.main()
