# -*- coding: utf-8 -*-
"""
Kịch bản kiểm thử tính năng Đồng bộ Dropbox cho MarkItDown.
"""

import os
import sys
import tempfile
import unittest

import infrastructure
import markitdown_gui


class TestDropboxSync(unittest.TestCase):

    def test_resolve_dropbox_token_empty(self):
        tok, err = infrastructure.resolve_dropbox_token("", "", "", "")
        self.assertEqual(tok, "")
        self.assertIn("Chưa cung cấp", err)

    def test_resolve_dropbox_token_direct(self):
        tok, err = infrastructure.resolve_dropbox_token(token="sl.u.test_token_123")
        self.assertEqual(tok, "sl.u.test_token_123")
        self.assertIsNone(err)

    def test_test_dropbox_connection_invalid_token(self):
        ok, msg, lat = infrastructure.test_dropbox_connection(token="invalid_token_xyz")
        self.assertFalse(ok)
        self.assertTrue("❌" in msg or "Lỗi" in msg)

    def test_upload_to_dropbox_nonexistent_file(self):
        path, err = infrastructure.upload_to_dropbox("/non/existent/file.txt", token="test_token")
        self.assertIsNone(path)
        self.assertIn("không tồn tại", err)

    def test_upload_to_dropbox_missing_auth(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".md") as tmp:
            tmp.write(b"# Test Markdown Content\n")
            tmp_path = tmp.name

        try:
            path, err = infrastructure.upload_to_dropbox(tmp_path, token="", refresh_token="", app_key="", app_secret="")
            self.assertIsNone(path)
            self.assertIn("Không thể xác thực", err)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_gui_prefs_state(self):
        prefs = markitdown_gui._save_prefs(
            preset_v="Cân bằng",
            mode_v="Sách cờ vua",
            dir_v="C:\\Downloads",
            engine_v="Google Antigravity",
            api_key_v="test_api_key",
            claude_token_v="test_claude_token",
            agy_token_v="test_agy_token",
            auto_download_v=True,
            dropbox_token_v="sl.u.test_dbx_token",
            dropbox_app_key_v="test_app_key",
            dropbox_app_secret_v="test_app_secret",
            dropbox_folder_v="/MarkItDown/Converted",
            dropbox_sync_v=True,
        )
        self.assertEqual(prefs["dropbox_token"], "sl.u.test_dbx_token")
        self.assertEqual(prefs["dropbox_folder"], "/MarkItDown/Converted")
        self.assertTrue(prefs["dropbox_sync"])


if __name__ == "__main__":
    unittest.main()
