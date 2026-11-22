# -*- coding: utf-8 -*-
"""
Lớp trình bày: theme Gradio, CSS/JS (đọc từ assets/ui/), biểu tượng, HTML thanh tiêu đề và thẻ chế độ.

Bộ nhận diện "Cờ vua Dương Sinh" (navy/sun/teal), tái tạo từ design_handoff_markitdown_gui/ (Phương án A).
"""

import base64
import json
import os
import re
from urllib.parse import quote

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

# --- Phông tự lưu trữ (assets/fonts/*.woff2, giấy phép OFL/Apache-2.0 — xem LICENSE-*.txt cùng thư mục) ---------------
# Trước đây nạp từ Google Fonts: mạng chậm tới CDN làm cả trang đứng ở "Loading…" hơn 20 giây (K8).
_FONT_FAMILIES = {"roboto-condensed": "Roboto Condensed", "roboto-mono": "Roboto Mono", "roboto": "Roboto"}
_FONT_RANGES = {
    "latin": "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,"
             "U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD",
    "latin-ext": "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,"
                 "U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF",
    "vietnamese": "U+0102-0103,U+0110-0111,U+0128-0129,U+0168-0169,U+01A0-01A1,U+01AF-01B0,U+0300-0301,"
                  "U+0303-0304,U+0308-0309,U+0323,U+0329,U+1EA0-1EF9,U+20AB",
    "cyrillic": "U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116",
}
_FONT_FILE_RE = re.compile(r"^(roboto-condensed|roboto-mono|roboto)-(latin-ext|latin|vietnamese|cyrillic)-(\d+)-normal\.woff2$")


def font_face_css():
    """Sinh các khối @font-face cho mọi tệp trong assets/fonts/. Đường dẫn qua /gradio_api/file= (thư mục assets nằm
    trong allowed_paths), tính theo vị trí thật của tệp nên chạy đúng ở mọi nơi triển khai."""
    fonts_dir = os.path.join(_ASSETS_DIR, "fonts")
    try:
        names = sorted(os.listdir(fonts_dir))
    except OSError:
        return ""
    blocks = []
    for name in names:
        m = _FONT_FILE_RE.match(name)
        if not m:
            continue
        pkg, subset, weight = m.groups()
        url = "/gradio_api/file=" + quote(os.path.join(fonts_dir, name).replace("\\", "/"))
        blocks.append(
            f"@font-face{{font-family:'{_FONT_FAMILIES[pkg]}';font-style:normal;font-weight:{weight};"
            f"font-display:swap;src:url('{url}') format('woff2');unicode-range:{_FONT_RANGES[subset]};}}"
        )
    return "\n".join(blocks) + "\n"


# --- Theme Gradio: màu/bo góc/phông của thành phần gốc đặt qua .set() thay vì ghi đè DOM nội bộ (Q3) -----------------
_NAVY = gr.themes.Color(
    c50="#EEF0FA", c100="#E9EBF6", c200="#C9CEEA", c300="#9FA8D8", c400="#6F7BC0", c500="#4553A8",
    c600="#2B3990", c700="#232E78", c800="#1E2A6B", c900="#151D49", c950="#0E1430", name="mid_navy",
)
THEME = gr.themes.Base(
    primary_hue=_NAVY, secondary_hue=_NAVY, neutral_hue=gr.themes.colors.slate,
    # gr.themes.Font = phông cục bộ (không nạp stylesheet từ CDN); chuỗi trơn làm Gradio lỗi khi so sánh theme.
    font=[gr.themes.Font("Roboto"), gr.themes.Font("Segoe UI"), gr.themes.Font("system-ui"), gr.themes.Font("sans-serif")],
    font_mono=[gr.themes.Font("Roboto Mono"), gr.themes.Font("ui-monospace"), gr.themes.Font("monospace")],
    radius_size=gr.themes.sizes.radius_md,
).set(
    body_background_fill="#F1F3F9", body_background_fill_dark="#0E1430",
    background_fill_primary="#FFFFFF", background_fill_primary_dark="#1A2356",
    background_fill_secondary="#F5F6FB", background_fill_secondary_dark="#141C49",
    block_background_fill="#FFFFFF", block_background_fill_dark="#1A2356",
    block_border_color="#E3E5EC", block_border_color_dark="rgba(255,255,255,0.10)",
    border_color_primary="#E3E5EC", border_color_primary_dark="rgba(255,255,255,0.10)",
    body_text_color="#16203A", body_text_color_dark="#F2F4FB",
    body_text_color_subdued="#6E7486", body_text_color_subdued_dark="#A6AED2",
    block_label_text_color="#6E7486", block_label_text_color_dark="#A6AED2",
    block_title_text_color="#3A4254", block_title_text_color_dark="#D4D9EE",
    input_background_fill="#F5F6FB", input_background_fill_dark="#141C49",
    input_border_color="#E3E5EC", input_border_color_dark="rgba(255,255,255,0.10)",
    input_border_color_focus="#2B3990", input_border_color_focus_dark="#6378D6",
    button_primary_background_fill="#2B3990", button_primary_background_fill_dark="#2B3990",
    button_primary_background_fill_hover="#1E2A6B", button_primary_background_fill_hover_dark="#3A4CB0",
    button_primary_text_color="#FFFFFF", button_primary_text_color_dark="#FFFFFF",
    button_primary_border_color="#2B3990", button_primary_border_color_dark="#2B3990",
    button_secondary_background_fill="#F5F6FB", button_secondary_background_fill_dark="#141C49",
    button_secondary_background_fill_hover="#E9EBF6", button_secondary_background_fill_hover_dark="#1A2356",
    button_secondary_text_color="#3A4254", button_secondary_text_color_dark="#D4D9EE",
    button_secondary_border_color="#E3E5EC", button_secondary_border_color_dark="rgba(255,255,255,0.10)",
    checkbox_background_color_selected="#2B3990", checkbox_background_color_selected_dark="#2B3990",
    checkbox_border_color_selected="#2B3990", checkbox_border_color_selected_dark="#2B3990",
    loader_color="#2B3990", loader_color_dark="#F6B92B",
    block_radius="18px", button_large_radius="12px", button_small_radius="9px", input_radius="9px",
    block_shadow="none", block_shadow_dark="none",
)


def _read_asset(rel_path):
    with open(os.path.join(_ASSETS_DIR, rel_path), "r", encoding="utf-8") as f:
        return f.read()


# JS: chuyển theme sáng/tối, bắc cầu thẻ "chế độ" (HTML) -> gr.Radio ẩn, và
# render block ```chessboard``` / dòng `fen:` trong phần xem trước thành bàn cờ.
# Nội dung ở assets/ui/app.js (không gồm thẻ <script>).
_SCRIPT = "\n<script>\n" + _read_asset("ui/app.js") + "</script>\n"

HEAD = _SCRIPT.replace("__MID_PIECES__", json.dumps(_PIECES))

# CSS: @font-face (sinh theo vị trí tệp) + nội dung ở assets/ui/app.css.
def piece_css():
    """Ảnh nền cho quân cờ của bàn cờ HTML (fen_tools.board_html): `.mid-pc.<màu><quân>` (wp, bn, …)."""
    rules = [
        ".mid-pc{display:block;width:82%;height:82%;background-size:contain;background-repeat:no-repeat;"
        "background-position:center;}"
    ]
    for name, uri in _PIECES.items():
        if uri:
            rules.append(f'.mid-pc.{name}{{background-image:url("{uri}");}}')
    return "\n".join(rules) + "\n"


CSS = "\n" + font_face_css() + piece_css() + _read_asset("ui/app.css")


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
    <span class="mid-ai-badge" data-mid-ai-badge data-ready="" title="Trạng thái phiên AI (mở Cài đặt để kết nối)">
      <i></i><span data-mid-ai-label>AI: đang kiểm tra…</span>
    </span>
    <button class="mid-theme-btn" data-mid-action="toggle-settings" type="button" aria-label="Mở trang Cài đặt">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
      <span>Cài đặt</span>
    </button>
    <button class="mid-theme-btn" data-mid-action="toggle-theme" type="button">
      <span data-mid-theme-icon></span><span data-mid-theme-label>Tối</span>
    </button>
  </div>
</div>
"""

# Đầu trang Cài đặt (toàn chiều rộng): tiêu đề, nút bật thông báo trình duyệt, nút quay lại.
MID_SETTINGS_HEAD_HTML = """
<div class="mid-set-head">
  <div>
    <div class="mid-set-title">Cài đặt hạ tầng &amp; API</div>
    <div class="mid-set-sub">Kết nối gói thuê bao AI và Dropbox. Khóa/token chỉ lưu trong trình duyệt của bạn.</div>
  </div>
  <div class="mid-set-actions">
    <button type="button" class="mid-set-btn" data-mid-action="enable-notify" title="Báo khi công việc nền xong">
      <span data-mid-notify-label>🔔 Thông báo</span>
    </button>
    <button type="button" class="mid-set-btn mid-set-back" data-mid-action="close-settings">← Quay lại</button>
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
