# -*- coding: utf-8 -*-
"""Preset chất lượng (Tiết kiệm / Cân bằng / Chính xác) và việc lưu/nạp lựa chọn của người dùng (BrowserState)."""

import os

import gradio as gr

from ai_engine import (
    ENGINE_ANTIGRAVITY,
    ANTIGRAVITY_OCR_MODELS,
    ANTIGRAVITY_TRANSLATE_MODELS,
    CLAUDE_OCR_MODELS,
    CLAUDE_TRANSLATE_MODELS,
    get_default_engine,
)
import pipeline
from pipeline import MODE_CHESS, _is_chess_mode


# Preset -> gợi ý ngắn hiển thị cạnh "MỨC CHẤT LƯỢNG".
PRESET_SAVER = "Tiết kiệm"
PRESET_BALANCED = "Cân bằng"
PRESET_ACCURATE = "Chính xác"



# Presets ánh xạ theo từng Engine
_PRESET_OPTS_AGY = {
    PRESET_SAVER: dict(merge=True, ocr_model="gemini-4-hydrogen", ocr_effort="low",
                       tr_model="gemini-4-hydrogen", tr_effort="low", dpi="250", pages="2"),
    PRESET_BALANCED: dict(merge=True, ocr_model="gemini-3.8-flash", ocr_effort="auto",
                          tr_model="gemini-3.8-flash", tr_effort="low", dpi="250", pages="1"),
    PRESET_ACCURATE: dict(merge=False, ocr_model="gemini-4-argon", ocr_effort="high",
                          tr_model="gemini-4-argon", tr_effort="medium", dpi="400", pages="1"),
}

_PRESET_OPTS_CLAUDE = {
    PRESET_SAVER: dict(merge=True, ocr_model="haiku", ocr_effort="low",
                       tr_model="haiku", tr_effort="low", dpi="250", pages="2"),
    PRESET_BALANCED: dict(merge=True, ocr_model="sonnet", ocr_effort="auto",
                          tr_model="haiku", tr_effort="low", dpi="250", pages="1"),
    PRESET_ACCURATE: dict(merge=False, ocr_model="opus", ocr_effort="high",
                          tr_model="sonnet", tr_effort="medium", dpi="400", pages="1"),
}


def preset_hint_text(preset, engine=ENGINE_ANTIGRAVITY):
    """Gợi ý ngắn cạnh "MỨC CHẤT LƯỢNG", SINH từ bảng preset của engine đang chọn (không còn bảng gợi ý tĩnh dễ lệch)."""
    table = _PRESET_OPTS_AGY if engine == ENGINE_ANTIGRAVITY else _PRESET_OPTS_CLAUDE
    opt = table.get(preset, table[PRESET_BALANCED])
    return f"{opt['ocr_model']} · effort {opt['ocr_effort']} · {'gộp OCR+dịch' if opt['merge'] else 'dịch riêng'}"


def _apply_preset(preset, engine=ENGINE_ANTIGRAVITY):
    """Chọn preset / đổi engine -> đặt model, effort, DPI, trang-mỗi-lần và "gộp OCR+dịch".

    KHÔNG đụng tới các công tắc người dùng tự chọn (dịch tiếng Việt, tự lưu, tự tải về, Dropbox): trước đây đổi preset
    bật lại cả bốn (T8/B10). `force_ocr` chỉ được đặt lại khi đổi CHẾ ĐỘ (xem `_on_mode_change`).
    Thứ tự trả về khớp `preset_outputs` trong build_ui.
    """
    table = _PRESET_OPTS_AGY if engine == ENGINE_ANTIGRAVITY else _PRESET_OPTS_CLAUDE
    opt = table.get(preset, table[PRESET_BALANCED])
    ocr_choices = ANTIGRAVITY_OCR_MODELS if engine == ENGINE_ANTIGRAVITY else CLAUDE_OCR_MODELS
    tr_choices = ANTIGRAVITY_TRANSLATE_MODELS if engine == ENGINE_ANTIGRAVITY else CLAUDE_TRANSLATE_MODELS
    return (
        gr.update(value=opt["merge"]),     # merge_ocr_translate
        gr.update(choices=ocr_choices, value=opt["ocr_model"]),
        gr.update(value=opt["ocr_effort"]),
        gr.update(choices=tr_choices, value=opt["tr_model"]),
        gr.update(value=opt["tr_effort"]),
        gr.update(value=opt["dpi"]),
        gr.update(value=opt["pages"]),
        gr.update(value=preset_hint_text(preset, engine)),   # preset_hint
    )


def _on_mode_change(mode_label):
    """Đổi chế độ xử lý -> đặt lại "Buộc OCR": bật cho sách cờ vua, tắt cho tài liệu thường."""
    return gr.update(value=_is_chess_mode(mode_label))


def _load_prefs(p):
    """BrowserState -> đặt lại preset/chế độ/thư mục lưu/engine/khóa/công tắc/dropbox khi tải trang."""
    p = p or {}
    default_eng = get_default_engine()
    return (
        gr.update(value=p.get("preset", PRESET_BALANCED)),
        gr.update(value=p.get("mode", MODE_CHESS)),
        gr.update(value=pipeline.normalize_save_dir(p.get("dir"))),   # ngoài vùng cho phép (Docker) -> về mặc định
        gr.update(value=p.get("engine", default_eng)),
        gr.update(value=p.get("api_key", "")),
        gr.update(value=p.get("claude_token", "")),
        gr.update(value=p.get("agy_token", "")),
        gr.update(value=p.get("auto_download", True)),
        gr.update(value=p.get("dropbox_token", "")),
        gr.update(value=p.get("dropbox_app_key", "")),
        gr.update(value=p.get("dropbox_app_secret", "")),
        gr.update(value=p.get("dropbox_folder", "/MarkItDown")),
        gr.update(value=p.get("dropbox_sync", True)),
        gr.update(value=p.get("translate_vn", True)),
        gr.update(value=p.get("autosave_on", True)),
        gr.update(value=p.get("remember_keys", True)),
    )


def _save_prefs(
    preset_v, mode_v, dir_v, engine_v, api_key_v="", claude_token_v="", agy_token_v="", auto_download_v=True,
    dropbox_token_v="", dropbox_app_key_v="", dropbox_app_secret_v="", dropbox_folder_v="/MarkItDown", dropbox_sync_v=True,
    translate_vn_v=True, autosave_on_v=True, remember_keys_v=True,
):
    """Gói lựa chọn hiện tại để lưu vào BrowserState (localStorage).

    remember_keys_v=False ("Nhớ khóa trên trình duyệt này" tắt): các khóa/token/App Secret được lưu RỖNG, nên không nằm lại
    trong localStorage (S3). Mặc định True giữ hành vi cũ.
    """
    keep = bool(remember_keys_v)
    if not keep:
        api_key_v = claude_token_v = agy_token_v = dropbox_token_v = dropbox_app_secret_v = ""
    return {
        "preset": preset_v,
        "mode": mode_v,
        "dir": dir_v,
        "engine": engine_v,
        "api_key": api_key_v,
        "claude_token": claude_token_v,
        "agy_token": agy_token_v,
        "auto_download": auto_download_v,
        "dropbox_token": dropbox_token_v,
        "dropbox_app_key": dropbox_app_key_v,
        "dropbox_app_secret": dropbox_app_secret_v,
        "dropbox_folder": dropbox_folder_v,
        "dropbox_sync": dropbox_sync_v,
        "translate_vn": translate_vn_v,
        "autosave_on": autosave_on_v,
        "remember_keys": keep,
    }
