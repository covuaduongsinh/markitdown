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


class TestMobileLayout(unittest.TestCase):
    def test_actionbar_exists_and_css_has_mobile_rules(self):
        blocks = g.build_ui()
        ids = {getattr(b, "elem_id", None) for b in blocks.blocks.values()}
        for need in ("mid-actionbar", "mid-convert", "mid-stop", "mid-resume", "mid-queue", "mid-file-pick", "mid-rerun"):
            self.assertIn(need, ids)
        css = ui_theme.CSS
        self.assertIn("@media (max-width:780px)", css)
        self.assertIn("#mid-actionbar { position:fixed", css)
        self.assertIn(".mid-modes:not(.open) .mid-mode:not(.active) { display:none; }", css)
        self.assertIn("min-height:44px", css)

    def test_js_has_mobile_behaviour(self):
        js = ui_theme._read_asset("ui/app.js")
        self.assertIn("max-width: 780px", js)
        self.assertIn("scrollIntoView", js)
        self.assertIn("midSyncQualitySummary", js)


class TestSettingsPage(unittest.TestCase):
    def test_topbar_has_gear_and_ai_badge_and_settings_head(self):
        self.assertIn('data-mid-action="toggle-settings"', ui_theme.TOPBAR_HTML)
        self.assertIn("data-mid-ai-badge", ui_theme.TOPBAR_HTML)
        self.assertIn('data-mid-action="close-settings"', ui_theme.MID_SETTINGS_HEAD_HTML)
        self.assertIn('data-mid-action="enable-notify"', ui_theme.MID_SETTINGS_HEAD_HTML)

    def test_infra_html_exposes_ai_ready_flag(self):
        import infrastructure
        self.assertRegex(infrastructure.render_infrastructure_html(), r'data-mid-ai-ready="[01]"')

    def test_settings_is_a_separate_page_not_an_input_tab(self):
        blocks = g.build_ui()
        by_id = {getattr(b, "elem_id", None): b for b in blocks.blocks.values()}
        self.assertIn("mid-settings", by_id)
        self.assertIn("mid-workspace", by_id)
        tabs = [b.label for b in blocks.blocks.values() if type(b).__name__ == "Tab"]
        self.assertFalse([t for t in tabs if "Cài đặt" in str(t)], tabs)

    def test_css_never_uses_body_prefixed_selectors_for_layout(self):
        # Gradio nhân quy tắc CSS thành bản có tiền tố .gradio-container .contain: `body.x #id` không thắng được -> cấm.
        for line in ui_theme.CSS.splitlines():
            if line.startswith("body") and "{" in line:
                self.assertTrue(line.startswith("body {") or line.startswith('body[data-mid-theme="dark"] {'), line)


class TestSelfHostedFonts(unittest.TestCase):
    def test_no_cdn_and_font_faces_present(self):
        css = ui_theme.CSS + ui_theme.HEAD
        for host in ("fonts.googleapis.com", "fonts.gstatic.com"):
            self.assertNotIn(host, css)
        self.assertGreaterEqual(css.count("@font-face"), 30)
        self.assertIn("font-family:'Roboto Condensed'", css)
        self.assertIn("unicode-range:U+0102-0103", css)  # tập vietnamese
        self.assertIn("/gradio_api/file=", css)

    def test_every_font_file_has_a_face_and_exists(self):
        import os
        names = [n for n in os.listdir(os.path.join(ui_theme._ASSETS_DIR, "fonts")) if n.endswith(".woff2")]
        self.assertEqual(ui_theme.font_face_css().count("@font-face"), len(names))


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

    def test_apply_preset_only_touches_quality_options(self):
        out = presets._apply_preset(presets.PRESET_ACCURATE, "antigravity")
        self.assertEqual(len(out), 8)  # merge, ocr_model, ocr_effort, tr_model, tr_effort, dpi, pages, hint
        merge, ocr_model, ocr_effort, tr_model, tr_effort, dpi, pages, hint = out
        opt = presets._PRESET_OPTS_AGY[presets.PRESET_ACCURATE]
        self.assertEqual((merge["value"], ocr_model["value"], tr_model["value"], dpi["value"], pages["value"]),
                         (opt["merge"], opt["ocr_model"], opt["tr_model"], opt["dpi"], opt["pages"]))
        self.assertEqual(hint["value"], presets.preset_hint_text(presets.PRESET_ACCURATE, "antigravity"))

    def test_hint_is_generated_from_the_engine_table(self):
        self.assertIn("gemini-3.8-flash", presets.preset_hint_text(presets.PRESET_BALANCED, "antigravity"))
        self.assertIn("sonnet", presets.preset_hint_text(presets.PRESET_BALANCED, "claude"))
        self.assertIn("dịch riêng", presets.preset_hint_text(presets.PRESET_ACCURATE, "claude"))
        self.assertFalse(hasattr(presets, "_PRESET_HINTS"))  # không còn bảng gợi ý tĩnh dễ lệch

    def test_mode_change_only_resets_force_ocr(self):
        self.assertEqual(presets._on_mode_change(g.MODE_CHESS)["value"], True)
        self.assertEqual(presets._on_mode_change(g.MODE_CHESS_RU)["value"], True)
        self.assertEqual(presets._on_mode_change(g.MODE_GENERAL)["value"], False)

    def test_prefs_roundtrip_keeps_user_switches(self):
        saved = presets._save_prefs(
            presets.PRESET_SAVER, g.MODE_GENERAL, "/d", "claude", "k", "ct", "at", False,
            "dt", "ak", "as", "/F", False, False, False,
        )
        self.assertEqual((saved["translate_vn"], saved["autosave_on"], saved["auto_download"], saved["dropbox_sync"]),
                         (False, False, False, False))
        loaded = presets._load_prefs(saved)
        self.assertEqual(len(loaded), 16)
        self.assertEqual((loaded[13]["value"], loaded[14]["value"]), (False, False))
        defaults = presets._load_prefs({})
        self.assertEqual((defaults[13]["value"], defaults[14]["value"]), (True, True))


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
