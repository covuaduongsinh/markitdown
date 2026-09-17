# -*- coding: utf-8 -*-
"""
Module điều phối AI Engine cho MarkItDown GUI.

Hỗ trợ các phương thức:
1. Google Antigravity (`agy` CLI) - Phương án 1 (Mặc định & Khuyên dùng trên Local).
2. Google Gemini REST API Direct (Dùng API Key khi chạy trên Web Server/Docker).
3. Claude Code (`claude` CLI) - Phương án 2.
"""

import base64
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request


ENGINE_ANTIGRAVITY = "antigravity"
ENGINE_CLAUDE = "claude"

# Nhãn hiển thị trên giao diện người dùng
ENGINE_LABELS = [
    ("⚡ Google Antigravity / Gemini (Phương án 1 - Khuyên dùng)", ENGINE_ANTIGRAVITY),
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
    """Lỗi khi thực thi lệnh AI Engine (Antigravity, Gemini API hoặc Claude Code)."""


def find_agy():
    """Tìm đường dẫn thực thi của Antigravity (`agy.exe` hoặc `agy`)."""
    cmd = shutil.which("agy")
    if cmd:
        return cmd
    cmd = shutil.which("agy.exe")
    if cmd:
        return cmd

    user_home = os.path.expanduser("~")
    candidates = [
        "/usr/local/bin/agy",
        "/usr/bin/agy",
        "/root/.local/bin/agy",
        os.path.join(user_home, ".local", "bin", "agy"),
        os.path.join(user_home, ".local", "bin", "agy.exe"),
        os.path.join(user_home, ".gemini", "bin", "agy.exe"),
        os.path.join(user_home, ".gemini", "bin", "agy"),
    ]
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        candidates.extend([
            os.path.join(local_app_data, "agy", "bin", "agy.EXE"),
            os.path.join(local_app_data, "agy", "bin", "agy.exe"),
        ])
    candidate_home = os.path.join(user_home, "AppData", "Local", "agy", "bin", "agy.EXE")
    candidates.append(candidate_home)

    for c in candidates:
        if c and os.path.isfile(c):
            return c

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


def find_gemini_api_key(api_key: str = None) -> str:
    """Lấy Gemini API Key từ tham số, biến môi trường hoặc tệp cấu hình."""
    if api_key and str(api_key).strip():
        return str(api_key).strip()
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
    return key.strip()


def is_engine_available(engine=ENGINE_ANTIGRAVITY, api_key: str = None) -> bool:
    """Kiểm tra xem engine hoặc API Key tương ứng có sẵn để sử dụng không."""
    if engine == ENGINE_ANTIGRAVITY:
        return (find_agy() is not None) or bool(find_gemini_api_key(api_key))
    elif engine == ENGINE_CLAUDE:
        return find_claude() is not None
    return False


def get_default_engine(api_key: str = None) -> str:
    """Trả về engine mặc định ưu tiên."""
    if find_agy() or find_gemini_api_key(api_key):
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


def _map_gemini_api_model(model_name: str) -> str:
    """Ánh xạ tên model sang model ID chuẩn của Google Gemini API."""
    m = (model_name or "").lower().strip()
    if "flash" in m:
        if "3.7" in m or "3-7" in m:
            return "gemini-2.5-flash"  # Fallback hoặc chuẩn model REST
        if "2.5" in m or "2-5" in m:
            return "gemini-2.5-flash"
        if "2.0" in m or "2-0" in m:
            return "gemini-2.0-flash"
        if "1.5" in m or "1-5" in m:
            return "gemini-1.5-flash"
        return "gemini-2.5-flash"
    if "pro" in m:
        if "2.5" in m or "2-5" in m:
            return "gemini-2.5-pro"
        return "gemini-1.5-pro"
    return "gemini-2.5-flash"


def call_gemini_api_direct(
    prompt: str,
    model: str = "gemini-2.5-flash",
    img_dir: str = None,
    api_key: str = None,
    timeout: int = 180,
) -> str:
    """Gọi trực tiếp Google Gemini REST API bằng API Key (dành cho Web/Docker)."""
    key = find_gemini_api_key(api_key)
    if not key:
        raise AIEngineError("Chưa có Gemini API Key. Hãy nhập API Key trong phần 'Tùy chọn nâng cao'.")

    api_model = _map_gemini_api_model(model)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{api_model}:generateContent?key={key}"

    parts = []
    # Nếu có thư mục ảnh -> đọc tất cả ảnh nhúng vào parts
    if img_dir and os.path.isdir(img_dir):
        valid_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        files = sorted(os.listdir(img_dir))
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in valid_exts:
                fpath = os.path.join(img_dir, fname)
                try:
                    with open(fpath, "rb") as f:
                        b64_data = base64.b64encode(f.read()).decode("ascii")
                    mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
                    parts.append({
                        "inlineData": {
                            "mimeType": mime,
                            "data": b64_data
                        }
                    })
                except Exception as e:
                    print(f"[Gemini API] Lỗi đọc ảnh {fname}: {e}", file=sys.stderr)

    parts.append({"text": prompt})
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192,
        }
    }

    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_res = resp.read().decode("utf-8")
            data = json.loads(raw_res)
            candidates = data.get("candidates", [])
            if candidates:
                cand = candidates[0]
                content = cand.get("content", {})
                parts_out = content.get("parts", [])
                if parts_out and "text" in parts_out[0]:
                    return clean_markdown_output(parts_out[0]["text"])
            raise AIEngineError("Gemini API không trả về nội dung text hợp lệ.")
    except urllib.error.HTTPError as http_err:
        err_body = http_err.read().decode("utf-8", errors="replace")[:400]
        raise AIEngineError(f"Gemini API lỗi HTTP {http_err.code}: {err_body}") from http_err
    except urllib.error.URLError as url_err:
        raise AIEngineError(f"Không kết nối được tới Gemini API: {url_err.reason}") from url_err
    except Exception as exc:
        raise AIEngineError(f"Lỗi khi gọi Gemini API: {exc}") from exc


def run_agy_prompt(
    prompt: str,
    model: str = "gemini-3.7-flash",
    effort: str = "low",
    img_dir: str = None,
    timeout: int = 600,
    api_key: str = None,
    agy_token: str = None,
) -> str:
    """Thực thi prompt với Google Antigravity CLI (`agy -p`) hoặc Gemini Direct API."""
    if agy_token and str(agy_token).strip():
        from infrastructure import save_antigravity_token
        save_antigravity_token(str(agy_token).strip())

    agy_bin = find_agy()
    if not agy_bin:
        # Fallback sang Gemini REST API nếu có API Key
        if find_gemini_api_key(api_key):
            return call_gemini_api_direct(
                prompt=prompt,
                model=model,
                img_dir=img_dir,
                api_key=api_key,
                timeout=timeout,
            )
        raise AIEngineError(
            "Không tìm thấy Google Antigravity CLI ('agy') và chưa cấu hình GEMINI_API_KEY. "
            "Hãy cài đặt Antigravity hoặc nhập Gemini API Key trong Tùy chọn nâng cao."
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
