# -*- coding: utf-8 -*-
"""Các hàm vẽ HTML cho phần kết quả (danh sách tải về...). Chuỗi đưa vào HTML do hàm gọi chịu trách nhiệm escape."""

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


def _download_panel(paths, auto_download=False):
    """HTML danh sách tệp kết quả, mỗi tệp một nút tải riêng.

    Khi có ≥2 tệp, chèn thêm một dòng "Tải tất cả (.zip)" ở đầu danh sách.
    `auto_download=True`: thêm cờ data-auto-download="1" để JS client tự động tải về máy.
    """
    if not paths:
        return ""
    rows = []
    if len(paths) >= 2:
        zip_path = _zip_all(paths)
        zip_name = os.path.basename(zip_path)
        zip_href = "/gradio_api/file=" + quote(zip_path.replace("\\", "/"))
        rows.append(
            f'<div class="dl-row dl-all">'
            f'<span class="dl-fileicon">{_DL_ZIP_ICON}</span>'
            f'<span class="dl-name">Tải tất cả · {len(paths)} tệp</span>'
            f'<a class="dl-btn dl-all-btn" href="{zip_href}" download="{zip_name}">'
            f'{_DL_DOWN_ICON}Tải .zip</a></div>'
        )
    for p in paths:
        name = os.path.basename(p)
        href = "/gradio_api/file=" + quote(p.replace("\\", "/"))
        rows.append(
            f'<div class="dl-row"><span class="dl-fileicon">{_DL_FILE_ICON}</span>'
            f'<span class="dl-name">{name}</span>'
            f'<a class="dl-btn dl-file-btn" href="{href}" download="{name}">{_DL_DOWN_ICON}Tải về</a></div>'
        )
    auto_attr = ' data-auto-download="1"' if auto_download else ' data-auto-download="0"'
    auto_badge = (
        ' <span style="font-size:11px;font-weight:normal;color:var(--teal);margin-left:6px;">'
        '⚡ Tự động tải về máy</span>'
        if auto_download else ''
    )
    return (
        f'<div class="dl-list"{auto_attr}><div class="dl-title">Tệp kết quả · '
        f'{len(paths)} tệp{auto_badge}</div>'
        + "".join(rows)
        + "</div>"
    )
