# -*- coding: utf-8 -*-
"""
Lớp trình bày: theme Gradio, CSS/JS (đọc từ assets/ui/), biểu tượng, HTML thanh tiêu đề và thẻ chế độ.

Bộ nhận diện "Cờ vua Dương Sinh" (navy/sun/teal), tái tạo từ design_handoff_markitdown_gui/ (Phương án A).
"""

import base64
import json
import os

import gradio as gr

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def _svg_data_uri(rel_path):
    """Đọc 1 file SVG trong assets/ -> data URI base64 (nhúng thẳng vào HTML)."""
    try:
        with open(os.path.join(_ASSETS_DIR, rel_path), "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return "data:image/svg+xml;base64," + b64
    except OSError:
        return ""


_PIECE_NAMES = ["wp", "wn", "wb", "wr", "wq", "wk", "bp", "bn", "bb", "br", "bq", "bk"]
_PIECES = {n: _svg_data_uri(f"pieces/{n}.svg") for n in _PIECE_NAMES}
_SYMBOL_WHITE = _svg_data_uri("symbol-white.svg")

THEME = gr.themes.Base(
    font=[gr.themes.GoogleFont("Roboto"), "Segoe UI", "system-ui", "sans-serif"],
    font_mono=[gr.themes.GoogleFont("Roboto Mono"), "monospace"],
)

_FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Roboto:ital,wght@0,300;'
    "0,400;0,500;0,700;0,900;1,400&family=Roboto+Condensed:wght@400;500;600;700"
    '&family=Roboto+Mono:wght@400;500&display=swap" rel="stylesheet">'
)


def _read_asset(rel_path):
    with open(os.path.join(_ASSETS_DIR, rel_path), "r", encoding="utf-8") as f:
        return f.read()


# JS: chuyển theme sáng/tối, bắc cầu thẻ "chế độ" (HTML) -> gr.Radio ẩn, và
# render block ```chessboard``` / dòng `fen:` trong phần xem trước thành bàn cờ.
# Nội dung ở assets/ui/app.js (không gồm thẻ <script>).
_SCRIPT = "\n<script>\n" + _read_asset("ui/app.js") + "</script>\n"

HEAD = _FONTS_LINK + _SCRIPT.replace("__MID_PIECES__", json.dumps(_PIECES))

# CSS: nội dung ở assets/ui/app.css.
CSS = "\n" + _read_asset("ui/app.css")


# Doc-mode icon (lucide file-text) cho thẻ "Tài liệu thường".
_DOC_ICON_SVG = (
    '<svg width="23" height="23" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="color:var(--c-subtext)">'
    '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
    '<polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/>'
    '<line x1="16" y1="17" x2="8" y2="17"/></svg>'
)

TOPBAR_HTML = f"""
<div id="mid-topbar">
  <img class="mid-logo" src="{_SYMBOL_WHITE}" alt="">
  <span class="mid-brand">MarkItDown</span>
  <span class="mid-tagline">Cờ vua Dương Sinh — tài liệu &amp; sách cờ → Markdown</span>
  <div class="mid-topbar-right">
    <div class="mid-badges">
      <span class="mid-badge">PDF</span>
      <span class="mid-badge">Word · Excel</span>
      <span class="mid-badge">Ảnh · URL</span>
      <span class="mid-badge mid-badge-chess">Sách cờ vua</span>
    </div>
    <button class="mid-theme-btn" data-mid-action="toggle-theme" type="button">
      <span data-mid-theme-icon></span><span data-mid-theme-label>Tối</span>
    </button>
  </div>
</div>
"""

MODE_CARDS_HTML = f"""
<div class="mid-modes">
  <div class="mid-mode active" data-mid-mode="0">
    <img class="mid-mode-icon" src="{_PIECES['wn']}" alt="">
    <div class="mid-mode-text">
      <div class="mid-mode-title">Sách cờ vua — ký hiệu Anh</div>
      <div class="mid-mode-desc">Nhận diện bàn cờ → FEN · K/Q/R/B/N → V/H/X/T/M</div>
    </div>
    <span class="mid-check"></span>
  </div>
  <div class="mid-mode" data-mid-mode="1">
    <img class="mid-mode-icon" src="{_PIECES['bn']}" alt="">
    <div class="mid-mode-text">
      <div class="mid-mode-title">Sách cờ vua — ký hiệu Nga</div>
      <div class="mid-mode-desc">Кр/Ф/Л/С/К → V/H/X/T/M · xử lý figurine</div>
    </div>
    <span class="mid-check"></span>
  </div>
  <div class="mid-mode" data-mid-mode="2">
    <img class="mid-mode-icon" src="{_PIECES['wb']}" alt="">
    <div class="mid-mode-text">
      <div class="mid-mode-title">Sách cờ vua — ký hiệu Tây Ban Nha</div>
      <div class="mid-mode-desc">R/D/T/A/C → V/H/X/T/M · ký hiệu Tây Ban Nha</div>
    </div>
    <span class="mid-check"></span>
  </div>
  <div class="mid-mode" data-mid-mode="3">
    <span class="mid-mode-icon">{_DOC_ICON_SVG}</span>
    <div class="mid-mode-text">
      <div class="mid-mode-title">Tài liệu thường</div>
      <div class="mid-mode-desc">Chuyển đổi gốc của MarkItDown + dịch thông thường</div>
    </div>
    <span class="mid-check"></span>
  </div>
</div>
"""
