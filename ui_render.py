# -*- coding: utf-8 -*-
"""Các hàm vẽ HTML cho phần kết quả (danh sách tải về...). Chuỗi đưa vào HTML do hàm gọi chịu trách nhiệm escape."""

import html
import os
from urllib.parse import quote

from pipeline import _zip_all


_DL_FILE_ICON = (
    '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#1FA98F" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
    '<polyline points="14 2 14 8 20 8"/></svg>'
)
_DL_DOWN_ICON = (
    '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
    '<polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>'
)
_DL_ZIP_ICON = (
    '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#fff" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M21 8v13H3V8"/><path d="M1 3h22v5H1z"/><path d="M10 12h4"/></svg>'
)


def _zip_count(zip_path, fallback):
    """Số tệp thật trong zip (có thể gồm cả thư mục chương Obsidian); lỗi thì dùng fallback."""
    try:
        import zipfile

        with zipfile.ZipFile(zip_path) as zf:
            return len(zf.namelist())
    except Exception:
        return fallback


def _download_panel(paths, auto_download=False, zip_path=None, metas=None, rerun=False):
    """HTML danh sách tệp kết quả, mỗi tệp một nút tải riêng.

    Khi có ≥2 tệp, chèn thêm một dòng "Tải tất cả (.zip)" ở đầu danh sách.
    `auto_download=True`: thêm cờ data-auto-download="1" để JS client tự động tải về máy.
    `metas`: {đường dẫn: chuỗi meta} hiện dưới tên tệp (số ký tự, số thế cờ).
    `rerun=True`: thêm nút "Chạy lại" (JS bấm hộ nút ẩn #mid-rerun).
    """
    if not paths:
        return ""
    metas = metas or {}
    rows = []
    has_zip = bool(zip_path) and os.path.exists(zip_path)
    if len(paths) >= 2 or has_zip:
        zip_path = zip_path if has_zip else _zip_all(paths)
        zip_name = html.escape(os.path.basename(zip_path), quote=True)
        zip_href = "/gradio_api/file=" + quote(zip_path.replace("\\", "/"))
        rows.append(
            f'<div class="dl-row dl-all">'
            f'<span class="dl-fileicon">{_DL_ZIP_ICON}</span>'
            f'<span class="dl-name">Tải tất cả · {_zip_count(zip_path, len(paths))} tệp</span>'
            f'<a class="dl-btn dl-all-btn" href="{zip_href}" download="{zip_name}">'
            f'{_DL_DOWN_ICON}Tải .zip</a></div>'
        )
    for p in paths:
        name = html.escape(os.path.basename(p), quote=True)
        href = "/gradio_api/file=" + quote(p.replace("\\", "/"))
        meta = metas.get(p)
        meta_html = f'<span class="dl-meta">{html.escape(meta)}</span>' if meta else ""
        rows.append(
            f'<div class="dl-row"><span class="dl-fileicon">{_DL_FILE_ICON}</span>'
            f'<span class="dl-main"><span class="dl-name">{name}</span>{meta_html}</span>'
            f'<a class="dl-btn dl-file-btn" href="{href}" download="{name}">{_DL_DOWN_ICON}Tải về</a></div>'
        )
    auto_attr = ' data-auto-download="1"' if auto_download else ' data-auto-download="0"'
    auto_badge = ' <span class="dl-auto">⚡ Tự động tải về máy</span>' if auto_download else ""
    rerun_btn = (
        '<button type="button" class="dl-rerun" data-mid-action="rerun" title="Chạy lại công việc này">'
        '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" '
        'stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/>'
        '<path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>Chạy lại</button>'
        if rerun else ""
    )
    return (
        f'<div class="dl-list"{auto_attr}><div class="dl-head"><div class="dl-title">Tệp .md kết quả · '
        f'{len(paths)} tệp{auto_badge}</div>{rerun_btn}</div>'
        + "".join(rows)
        + "</div>"
    )
