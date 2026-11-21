"""Test giao diện không cần trình duyệt: dựng build_ui, tệp CSS/JS, preset, xác thực."""

import unittest

import tests_gui._setup  # noqa: F401  (phải import trước mã ứng dụng)
import markitdown_gui as g
import presets
import ui_theme
from ai_engine import (
    ANTIGRAVITY_OCR_MODELS,
    ANTIGRAVITY_TRANSLATE_MODELS,
    CLAUDE_OCR_MODELS,
    CLAUDE_TRANSLATE_MODELS,
)


class TestBuildUi(unittest.TestCase):
    def test_build_ui_runs(self):
        self.assertEqual(type(g.build_ui()).__name__, "Blocks")


class TestUiAssets(unittest.TestCase):
    def test_css_and_js_come_from_files(self):
        self.assertIn("--navy", ui_theme.CSS)
        self.assertIn("<script>", ui_theme.HEAD)
        self.assertIn("</script>", ui_theme.HEAD)
        self.assertNotIn("__MID_PIECES__", ui_theme.HEAD)  # đã thay bằng JSON các quân cờ
        self.assertIn("mid-topbar", ui_theme.TOPBAR_HTML)
        self.assertEqual(ui_theme.MODE_CARDS_HTML.count('data-mid-mode="'), 4)


class TestPresets(unittest.TestCase):
    def test_every_preset_model_is_in_the_engine_choices(self):
        cases = [
            (presets._PRESET_OPTS_AGY, ANTIGRAVITY_OCR_MODELS, ANTIGRAVITY_TRANSLATE_MODELS),
            (presets._PRESET_OPTS_CLAUDE, CLAUDE_OCR_MODELS, CLAUDE_TRANSLATE_MODELS),
        ]
        for table, ocr_choices, tr_choices in cases:
            ocr_values = {v for _, v in ocr_choices}
            tr_values = {v for _, v in tr_choices}
            self.assertEqual(
                set(table), {presets.PRESET_SAVER, presets.PRESET_BALANCED, presets.PRESET_ACCURATE},
            )
            for name, opt in table.items():
                self.assertIn(opt["ocr_model"], ocr_values, name)
                self.assertIn(opt["tr_model"], tr_values, name)

    def test_apply_preset_returns_one_update_per_output(self):
        out = presets._apply_preset(presets.PRESET_BALANCED, g.MODE_CHESS, "antigravity")
        self.assertEqual(len(out), 13)
        self.assertEqual(out[0]["value"], True)   # chế độ cờ vua -> buộc OCR
        general = presets._apply_preset(presets.PRESET_BALANCED, g.MODE_GENERAL, "antigravity")
        self.assertEqual(general[0]["value"], False)


class TestAuthFromEnv(unittest.TestCase):
    def test_off_when_unset_or_empty(self):
        self.assertIsNone(g._auth_from_env({}))
        self.assertIsNone(g._auth_from_env({"MID_AUTH_USER": "", "MID_AUTH_PASS": ""}))

    def test_on_when_both_set(self):
        self.assertEqual(g._auth_from_env({"MID_AUTH_USER": " an ", "MID_AUTH_PASS": "x y"}), ("an", "x y"))

    def test_half_configured_refuses(self):
        with self.assertRaises(ValueError):
            g._auth_from_env({"MID_AUTH_USER": "an"})
        with self.assertRaises(ValueError):
            g._auth_from_env({"MID_AUTH_PASS": "x"})


if __name__ == "__main__":
    unittest.main()
