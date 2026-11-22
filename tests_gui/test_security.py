"""Test G4 (bảo mật & vận hành): thư mục tự lưu bị giới hạn, biến môi trường ưu tiên hơn khóa trình duyệt,
độ trung thực của "sẵn sàng", công tắc nhớ khóa. Không gọi AI/Dropbox thật."""

import os
import tempfile
import unittest
from unittest import mock

import tests_gui._setup  # noqa: F401  (phải import trước mã ứng dụng)
import ai_engine
import infrastructure
import pipeline
import presets


class TestSaveRoot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        p = mock.patch.dict(os.environ, {"MID_SAVE_ROOT": self.tmp})
        p.start()
        self.addCleanup(p.stop)

    def test_inside_root_ok(self):
        real, err = pipeline.resolve_save_folder(os.path.join(self.tmp, "ok"))
        self.assertIsNone(err)
        self.assertTrue(real.startswith(os.path.realpath(self.tmp)))

    def test_relative_is_under_root(self):
        real, err = pipeline.resolve_save_folder("sub/x")
        self.assertIsNone(err)
        self.assertTrue(real.startswith(os.path.realpath(self.tmp)))

    def test_dotdot_rejected(self):
        for bad in ("../x", os.path.join(self.tmp, "..", "evil"), "a/../../b"):
            real, err = pipeline.resolve_save_folder(bad)
            self.assertIsNone(real, bad)
            self.assertIn("⚠️", err)

    def test_outside_rejected(self):
        outside = "C:/Windows" if os.name == "nt" else "/etc"
        real, err = pipeline.resolve_save_folder(outside)
        self.assertIsNone(real)
        self.assertIn(self.tmp, err)

    def test_empty_rejected(self):
        self.assertIsNotNone(pipeline.resolve_save_folder("  ")[1])

    def test_normalize_falls_back_to_default(self):
        self.assertEqual(pipeline.normalize_save_dir("C:/Windows" if os.name == "nt" else "/etc"), self.tmp)
        self.assertEqual(pipeline.normalize_save_dir(""), self.tmp)

    def test_autosave_refuses_outside(self):
        src = os.path.join(self.tmp, "a.md")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write("x")
        outside = "C:/Windows/Temp/mid_evil" if os.name == "nt" else "/etc/mid_evil"
        out, err = pipeline._autosave(src, outside)
        self.assertIsNone(out)
        self.assertIn("⚠️", err)
        self.assertFalse(os.path.exists(outside))


class TestSaveRootDefaults(unittest.TestCase):
    def test_no_limit_on_dev_machine(self):
        env = {k: v for k, v in os.environ.items() if k not in ("MID_SAVE_ROOT", "DOCKER")}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertIsNone(pipeline.save_root())
            self.assertEqual(pipeline.resolve_save_folder("C:/anything")[1], None)

    def test_docker_defaults_under_data_dir(self):
        env = {k: v for k, v in os.environ.items() if k != "MID_SAVE_ROOT"}
        env.update({"DOCKER": "1", "MID_DATA_DIR": "/data"})
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(pipeline.save_root(), os.path.join("/data", "saved"))


class TestEnvPrecedence(unittest.TestCase):
    def test_env_first_prefers_server(self):
        with mock.patch.dict(os.environ, {"X_TOK": " server "}):
            self.assertEqual(ai_engine.env_first(("X_TOK",), "browser"), "server")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("X_TOK", None)
            self.assertEqual(ai_engine.env_first(("X_TOK",), " browser "), "browser")
            self.assertEqual(ai_engine.env_first(("X_TOK",), None), "")

    def test_gemini_key_env_wins(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "srv"}):
            self.assertEqual(ai_engine.find_gemini_api_key("browser"), "srv")

    def test_dropbox_env_wins(self):
        with mock.patch.dict(os.environ, {"DROPBOX_ACCESS_TOKEN": "srv"}):
            src = infrastructure.resolve_dropbox_token("browser")
            self.assertIn("srv", repr(src))
            self.assertNotIn("browser", repr(src))

    def test_env_configured_flags(self):
        clean = {k: v for k, v in os.environ.items() if k not in (
            "GEMINI_API_KEY", "GOOGLE_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "DROPBOX_ACCESS_TOKEN", "DROPBOX_REFRESH_TOKEN")}
        with mock.patch.dict(os.environ, clean, clear=True):
            self.assertEqual(infrastructure.env_configured(), {"gemini": False, "claude": False, "dropbox": False})
        with mock.patch.dict(os.environ, {**clean, "CLAUDE_CODE_OAUTH_TOKEN": "t"}, clear=True):
            self.assertTrue(infrastructure.env_configured()["claude"])


class TestHonestAvailability(unittest.TestCase):
    def test_antigravity_needs_cli_or_key(self):
        clean = {k: v for k, v in os.environ.items() if k not in ("GEMINI_API_KEY", "GOOGLE_API_KEY")}
        with mock.patch.dict(os.environ, clean, clear=True), mock.patch.object(ai_engine, "find_agy", return_value=None):
            self.assertFalse(ai_engine.is_engine_available(ai_engine.ENGINE_ANTIGRAVITY, agy_token="whatever"))
            self.assertTrue(ai_engine.is_engine_available(ai_engine.ENGINE_ANTIGRAVITY, api_key="k"))
        with mock.patch.object(ai_engine, "find_agy", return_value="/x/agy"):
            self.assertTrue(ai_engine.is_engine_available(ai_engine.ENGINE_ANTIGRAVITY))

    def test_claude_needs_cli(self):
        with mock.patch.object(ai_engine, "find_claude", return_value=None):
            self.assertFalse(ai_engine.is_engine_available(ai_engine.ENGINE_CLAUDE, claude_token="tok"))
        with mock.patch.object(ai_engine, "find_claude", return_value="/x/claude"):
            self.assertTrue(ai_engine.is_engine_available(ai_engine.ENGINE_CLAUDE))

    def test_display_names(self):
        self.assertEqual(ai_engine.engine_display_name(ai_engine.ENGINE_CLAUDE), "Claude Code")
        self.assertIn("Antigravity", ai_engine.engine_display_name(ai_engine.ENGINE_ANTIGRAVITY))

    def test_onnx_status_uses_available(self):
        import chessboard_fen

        with mock.patch.object(chessboard_fen, "available", return_value=False):
            off = infrastructure.render_infrastructure_html()
        with mock.patch.object(chessboard_fen, "available", return_value=True):
            on = infrastructure.render_infrastructure_html()
        self.assertIn("○ Tắt", off)
        self.assertNotIn("○ Tắt", on)


class TestRememberKeys(unittest.TestCase):
    def _save(self, remember):
        names = presets._save_prefs.__code__.co_varnames[: presets._save_prefs.__code__.co_argcount]
        kwargs = {n: "" for n in names}
        kwargs.update({"api_key_v": "AK", "claude_token_v": "CT", "agy_token_v": "AT",
                       "dropbox_token_v": "DT", "dropbox_app_secret_v": "DS", "remember_keys_v": remember})
        return presets._save_prefs(**kwargs)

    def test_off_blanks_secrets(self):
        p = self._save(False)
        for k in ("api_key", "claude_token", "agy_token", "dropbox_token", "dropbox_app_secret"):
            self.assertEqual(p[k], "", k)
        self.assertFalse(p["remember_keys"])

    def test_on_keeps_secrets(self):
        p = self._save(True)
        self.assertEqual(p["api_key"], "AK")
        self.assertTrue(p["remember_keys"])


class TestPickButtonHiddenOnDocker(unittest.TestCase):
    def test_build_ui_on_docker(self):
        import markitdown_gui as g

        with mock.patch.dict(os.environ, {"DOCKER": "1"}):
            self.assertEqual(type(g.build_ui()).__name__, "Blocks")


if __name__ == "__main__":
    unittest.main()
