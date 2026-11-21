"""Test hàm thuần và đường xuất kết quả của pipeline.py (không gọi AI, không gọi Dropbox thật)."""

import os
import shutil
import tempfile
import unittest
import zipfile
from unittest import mock

import tests_gui._setup  # noqa: F401  (phải import trước mã ứng dụng)
import pipeline


class TestSafeNamesAndLabels(unittest.TestCase):
    def test_safe_filename(self):
        self.assertEqual(pipeline._safe_filename('a<b>:c"/d\\e|f?g*'), "a_b_c_d_e_f_g_")
        self.assertEqual(pipeline._safe_filename("  ..  "), "ketqua")
        self.assertEqual(pipeline._safe_filename("Sách cờ vua"), "Sách cờ vua")

    def test_mode_helpers(self):
        self.assertTrue(pipeline._is_chess_mode(pipeline.MODE_CHESS))
        self.assertTrue(pipeline._is_chess_mode("nhãn lạ"))
        self.assertFalse(pipeline._is_chess_mode(pipeline.MODE_GENERAL))
        self.assertEqual(pipeline._chess_lang_from_mode(pipeline.MODE_CHESS_RU), "ru")
        self.assertEqual(pipeline._chess_lang_from_mode(pipeline.MODE_CHESS_ES), "es")
        self.assertEqual(pipeline._chess_lang_from_mode(pipeline.MODE_CHESS), "en")

    def test_label_parsers(self):
        self.assertEqual(pipeline._model_from_label("Gemini-3.8-Flash (cân bằng)"), "gemini-3.8-flash")
        self.assertEqual(pipeline._model_from_label(None), "gemini-3.8-flash")
        self.assertEqual(pipeline._effort_from_label("low (tiết kiệm nhất)"), "low")
        self.assertIsNone(pipeline._effort_from_label("auto (tự động)", default=None))
        self.assertEqual(pipeline._effort_from_label("auto", default="low"), "low")
        self.assertEqual(pipeline._dpi_from_label("400 (nét nhất)"), 400)
        self.assertEqual(pipeline._dpi_from_label("lạ"), 400)
        self.assertEqual(pipeline._pages_from_label("2 trang/lần"), 2)
        self.assertEqual(pipeline._pages_from_label("9 trang/lần"), 3)  # giới hạn 1..3
        self.assertEqual(pipeline._pages_from_label(""), 1)


class TestFilesOut(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mid_test_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_write_md_dedupes_within_batch(self):
        used = []
        p1 = pipeline._write_md("một", "mid_test_dup", used)
        used.append(p1)
        p2 = pipeline._write_md("hai", "mid_test_dup", used)
        self.assertNotEqual(p1, p2)
        self.assertTrue(p2.endswith("mid_test_dup_2.md"))
        with open(p2, encoding="utf-8") as f:
            self.assertEqual(f.read(), "hai")

    def test_write_fen_file(self):
        md = "x\n\n```chessboard\nfen: 6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1\n```\n"
        path, n = pipeline._write_fen_file(md, "mid_test_fen")
        self.assertEqual(n, 1)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1\n")
        self.assertEqual(pipeline._write_fen_file("không có thế cờ", "mid_test_fen"), (None, 0))

    def test_zip_all_dedupes_names(self):
        a = os.path.join(self.tmp, "a", "x.md")
        b = os.path.join(self.tmp, "b", "x.md")
        for p, t in ((a, "A"), (b, "B")):
            os.makedirs(os.path.dirname(p))
            with open(p, "w", encoding="utf-8") as f:
                f.write(t)
        z = pipeline._zip_all([a, b, os.path.join(self.tmp, "khong-co.md")])
        with zipfile.ZipFile(z) as zf:
            self.assertEqual(sorted(zf.namelist()), ["x.md", "x_2.md"])

    def test_autosave_never_overwrites(self):
        src = os.path.join(self.tmp, "k.md")
        with open(src, "w", encoding="utf-8") as f:
            f.write("nội dung")
        dest_dir = os.path.join(self.tmp, "out")
        d1, e1 = pipeline._autosave(src, dest_dir)
        d2, e2 = pipeline._autosave(src, dest_dir)
        self.assertIsNone(e1)
        self.assertTrue(d2.endswith("k_2.md"))
        self.assertIsNone(pipeline._autosave(src, "  ")[0])

    def test_resolve_save_dir(self):
        fp = os.path.join(self.tmp, "sach.pdf")
        d, note = pipeline._resolve_save_dir(fp, pipeline.AUTOSAVE_SRC, "/tuy-chon", True)
        self.assertEqual(d, self.tmp)
        self.assertEqual(note, "")
        d, note = pipeline._resolve_save_dir(fp, pipeline.AUTOSAVE_SRC, "/tuy-chon", False)
        self.assertEqual(d, "/tuy-chon")
        self.assertIn("kéo-thả", note)
        d, note = pipeline._resolve_save_dir(fp, pipeline.AUTOSAVE_CUSTOM, "/tuy-chon", True)
        self.assertEqual((d, note), ("/tuy-chon", ""))


class TestPublishOutput(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mid_test_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.src = os.path.join(self.tmp, "kq.md")
        with open(self.src, "w", encoding="utf-8") as f:
            f.write("x")
        self.out = os.path.join(self.tmp, "out")

    def test_nothing_enabled_gives_empty_note(self):
        self.assertEqual(pipeline._publish_output(self.src, self.out), "")

    def test_main_style_and_inline_style(self):
        main = pipeline._publish_output(
            self.src, self.out, autosave_on=True, auto_download_on=True, save_note=" (ghi chú)",
        )
        self.assertTrue(main.startswith("\n  💾 [VPS] đã lưu: `"))
        self.assertIn("` (ghi chú)", main)
        self.assertIn("\n  ⚡ [Máy tính] Đang tải `kq.md` về máy...", main)
        inline = pipeline._publish_output(
            self.src, self.out, autosave_on=True, auto_download_on=True, inline=True, save_note="BỎ QUA",
        )
        self.assertTrue(inline.startswith(" · 💾 [VPS] đã lưu: `"))
        self.assertNotIn("BỎ QUA", inline)
        self.assertTrue(inline.endswith(" · ⚡ [Máy tính] Đang tải `kq.md`"))

    def test_autosave_error_is_reported_on_new_line(self):
        note = pipeline._publish_output(self.src, "", autosave_on=True)
        self.assertEqual(note, "\n  ⚠️ Chưa nhập thư mục lưu kết quả.")

    def test_dropbox_paths_use_fake_uploader(self):
        cfg = dict(folder="/F", token="t", refresh_token="r", app_key="k", app_secret="s")
        with mock.patch.object(pipeline.infrastructure, "upload_to_dropbox", return_value=("/F/kq.md", None)) as up:
            main = pipeline._publish_output(self.src, self.out, dropbox_sync_on=True, dropbox_cfg=cfg)
            inline = pipeline._publish_output(self.src, self.out, dropbox_sync_on=True, dropbox_cfg=cfg, inline=True)
        self.assertEqual(main, "\n  ☁️ [Dropbox] đã lưu: `/F/kq.md`")
        self.assertEqual(inline, " · ☁️ [Dropbox] `/F/kq.md`")
        up.assert_called_with(
            self.src, target_folder="/F", token="t", refresh_token="r", app_key="k", app_secret="s",
        )
        with mock.patch.object(pipeline.infrastructure, "upload_to_dropbox", return_value=(None, "hết hạn")):
            self.assertEqual(
                pipeline._publish_output(self.src, self.out, dropbox_sync_on=True, dropbox_cfg=cfg),
                "\n  ⚠️ [Dropbox] hết hạn",
            )


class TestConvertUrl(unittest.TestCase):
    def test_rejects_bad_urls_without_network(self):
        self.assertIn("nhập một URL", pipeline.convert_url("", False)[3])
        self.assertIn("http://", pipeline.convert_url("ftp://x", False)[3])


if __name__ == "__main__":
    unittest.main()
