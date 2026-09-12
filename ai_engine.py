# -*- coding: utf-8 -*-
"""
Module điều phối AI Engine cho MarkItDown GUI.

Hỗ trợ 2 engine AI:
1. Google Antigravity (`agy` CLI) - Phương án 1 (Mặc định & Khuyên dùng).
2. Claude Code (`claude` CLI) - Phương án 2.
"""

import json
import os
import shutil
import subprocess
import sys


ENGINE_ANTIGRAVITY = "antigravity"
ENGINE_CLAUDE = "claude"

# Nhãn hiển thị trên giao diện người dùng
ENGINE_LABELS = [
    ("⚡ Google Antigravity (Phương án 1 - Khuyên dùng)", ENGINE_ANTIGRAVITY),
    ("🟣 Claude Code (Phương án 2)", ENGINE_CLAUDE),
]

# Danh sách model cho từng Engine
ANTIGRAVITY_OCR_MODELS = [
    ("Gemini 3.6 Flash — Siêu tiết kiệm token", "gemini-3.6-flash"),
    ("Gemini 3.7 Flash — Cân bằng & Nhanh (Mặc định)", "gemini-3.7-flash"),
    ("Gemini 3.8 Flash — Tốc độ cao", "gemini-3.8-flash"),
    ("Gemini 3.1 Pro — Chính xác cao", "gemini-3.1-pro"),
    ("Claude Sonnet 4.6 (Thinking)", "claude-sonnet-4-6"),
    ("Claude Opus 4.6 (Thinking)", "claude-opus-4-6-thinking"),
]

ANTIGRAVITY_TRANSLATE_MODELS = [
    ("Gemini 3.6 Flash — Siêu tiết kiệm token", "gemini-3.6-flash"),
    ("Gemini 3.7 Flash — Tự nhiên & Nhanh (Mặc định)", "gemini-3.7-flash"),
    ("Gemini 3.8 Flash — Tốc độ cao", "gemini-3.8-flash"),
    ("Gemini 3.1 Pro — Văn phong cao cấp", "gemini-3.1-pro"),
    ("Claude Sonnet 4.6 (Thinking)", "claude-sonnet-4-6"),
]

CLAUDE_OCR_MODELS = [
    ("Sonnet — Cân bằng (Mặc định)", "sonnet"),
    ("Haiku — Nhanh", "haiku"),
    ("Opus — Chính xác", "opus"),
]

CLAUDE_TRANSLATE_MODELS = [
    ("Haiku — Tiết kiệm (Mặc định)", "haiku"),
    ("Sonnet — Cân bằng", "sonnet"),
    ("Opus — Chính xác", "opus"),
]


class AIEngineError(RuntimeError):
    """Lỗi khi thực thi lệnh AI Engine (Antigravity hoặc Claude Code)."""


def find_agy():
    """Tìm đường dẫn thực thi của Antigravity (`agy.EXE` hoặc `agy`)."""
    cmd = shutil.which("agy")
    if cmd:
        return cmd
    cmd = shutil.which("agy.exe")
    if cmd:
        return cmd

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        candidate = os.path.join(local_app_data, "agy", "bin", "agy.EXE")
        if os.path.isfile(candidate):
            return candidate
        candidate_lower = os.path.join(local_app_data, "agy", "bin", "agy.exe")
        if os.path.isfile(candidate_lower):
            return candidate_lower

    user_home = os.path.expanduser("~")
    candidate_home = os.path.join(user_home, "AppData", "Local", "agy", "bin", "agy.EXE")
    if os.path.isfile(candidate_home):
        return candidate_home

    return None


def find_claude():
    """Tìm đường dẫn thực thi của Claude Code (`claude.exe` hoặc `claude`)."""
    cmd = shutil.which("claude")
    if cmd:
        return cmd
    cmd = shutil.which("claude.exe")
    if cmd:
        return cmd

    user_home = os.path.expanduser("~")
    candidate_local = os.path.join(user_home, ".local", "bin", "claude.exe")
    if os.path.isfile(candidate_local):
        return candidate_local

    return None


def is_engine_available(engine=ENGINE_ANTIGRAVITY):
    """Kiểm tra xem engine đã được cài đặt và có sẵn không."""
    if engine == ENGINE_ANTIGRAVITY:
        return find_agy() is not None
    elif engine == ENGINE_CLAUDE:
        return find_claude() is not None
    return False


def get_default_engine():
    """Trả về engine mặc định ưu tiên: Antigravity nếu có, fallback sang Claude Code."""
    if find_agy():
        return ENGINE_ANTIGRAVITY
    if find_claude():
        return ENGINE_CLAUDE
    return ENGINE_ANTIGRAVITY


def clean_markdown_output(text: str) -> str:
    """Loại bỏ các block bọc ngoài dư thừa nếu model trả về ```markdown ... ```."""
    if not text:
        return ""
    stripped = text.strip()
    if stripped.startswith("```markdown") and stripped.endswith("```"):
        inner = stripped[len("```markdown"): -3].strip()
        if not inner.startswith("```"):
            return inner
    elif stripped.startswith("```md") and stripped.endswith("```"):
        inner = stripped[len("```md"): -3].strip()
        if not inner.startswith("```"):
            return inner
    return stripped


def run_agy_prompt(
    prompt: str,
    model: str = "gemini-3.7-flash",
    effort: str = "low",
    img_dir: str = None,
    timeout: int = 600,
) -> str:
    """Thực thi prompt với Google Antigravity CLI (`agy -p`).

    Trả về chuỗi văn bản kết quả (đã làm sạch).
    """
    agy_bin = find_agy()
    if not agy_bin:
        raise AIEngineError(
            "Không tìm thấy Google Antigravity CLI (lệnh 'agy'). "
            "Hãy đảm bảo Antigravity đã được cài đặt."
        )

    model_name = model.strip() if model else "gemini-3.7-flash"
    effort_val = effort if effort in ("low", "medium", "high") else "low"

    cmd = [
        agy_bin,
        "-p",
        prompt,
        "--output-format",
        "json",
        "--dangerously-skip-permissions",
        "--disable-slash-commands",
        "--model",
        model_name,
        "--effort",
        effort_val,
    ]

    if img_dir:
        cmd.extend(["--add-dir", img_dir])

    env = os.environ.copy()
    cwd = img_dir if img_dir and os.path.isdir(img_dir) else None

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise AIEngineError(f"Antigravity quá thời gian ({timeout}s) khi xử lý.") from exc

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[:600]
        raise AIEngineError(f"Antigravity lỗi (exit {proc.returncode}): {detail}")

    out = (proc.stdout or "").strip()
    if not out:
        raise AIEngineError("Antigravity không trả về dữ liệu.")

    try:
        data = json.loads(out)
        if isinstance(data, dict):
            res = data.get("response") or data.get("result") or out
            return clean_markdown_output(res)
    except json.JSONDecodeError:
        pass

    return clean_markdown_output(out)
