# -*- coding: utf-8 -*-
"""
Module Quản lý & Kiểm tra Hạ tầng (Infrastructure Manager) cho MarkItDown.

Hỗ trợ các phương thức kết nối:
1. 💎 Gói Thuê bao Tháng (Subscription Mode - KHÔNG tốn tiền API):
   - Google Antigravity CLI (`agy` CLI - Dùng phiên đăng nhập Google Gemini Advanced/Pro).
   - Claude Code CLI (`claude` CLI - Dùng phiên đăng nhập Claude Pro/Team/Max).
2. 🔑 Khóa API (Pay-as-you-go API Key):
   - Google Gemini REST API Direct (Dành cho Web/Docker).
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request


def test_gemini_connection(api_key):
    """Kiểm tra kết nối trực tiếp tới Google Gemini REST API bằng API Key.

    Trả về: (bool: is_ok, str: message, float: latency_ms)
    """
    key = (api_key or "").strip() or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        return False, "❌ Chưa nhập Gemini API Key.", 0.0

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    start = time.perf_counter()
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "MarkItDown-GUI/1.0"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            elapsed = (time.perf_counter() - start) * 1000.0
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                models = data.get("models", [])
                gemini_models = [m["name"].split("/")[-1] for m in models if "gemini" in m.get("name", "").lower()]
                count = len(gemini_models)
                return True, f"✅ Kết nối thành công tới Google Gemini API ({elapsed:.0f}ms). Tìm thấy {count} mô hình AI sẵn sàng!", elapsed
            return False, f"⚠️ Máy chủ phản hồi mã {resp.status}.", elapsed
    except urllib.error.HTTPError as exc:
        elapsed = (time.perf_counter() - start) * 1000.0
        try:
            body = exc.read().decode("utf-8")
            err_json = json.loads(body)
            msg = err_json.get("error", {}).get("message", str(exc))
        except Exception:
            msg = str(exc)
        return False, f"❌ Lỗi xác thực API ({exc.code}): {msg}", elapsed
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000.0
        return False, f"❌ Lỗi kết nối mạng: {exc}", elapsed


def test_claude_cli_connection(claude_token=""):
    """Kiểm tra kết nối Claude Code CLI bằng phiên đăng nhập gói thuê bao tháng (Claude Pro/Team/Max).

    Trả về: (bool: is_ok, str: message, float: latency_ms)
    """
    from ai_engine import find_claude

    claude_bin = find_claude()
    if not claude_bin:
        return (
            False,
            "⚠️ Chưa tìm thấy lệnh 'claude' CLI trên hệ thống.\n\n"
            "👉 **Trên máy tính**: Cài đặt bằng `npm install -g @anthropic-ai/claude-code` và chạy `claude` để đăng nhập.\n"
            "👉 **Trên Web VPS**: Lệnh `claude` đã được tích hợp trong container.",
            0.0,
        )

    token = (claude_token or "").strip()
    env = os.environ.copy()
    env["DISABLE_AUTOUPDATER"] = "1"
    env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    if token:
        env["CLAUDE_CODE_SESSION_ACCESS_TOKEN"] = token
        env["ANTHROPIC_SESSION_KEY"] = token
        env["ANTHROPIC_API_KEY"] = token

    start = time.perf_counter()
    try:
        cmd = [
            claude_bin,
            "-p",
            "Say 'OK' in one word",
            "--disable-slash-commands",
            "--no-session-persistence",
        ]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            stdin=subprocess.DEVNULL,
            env=env,
            creationflags=flags,
        )
        elapsed = (time.perf_counter() - start) * 1000.0
        if proc.returncode == 0:
            return (
                True,
                f"✅ Kết nối thành công tới Claude Code CLI ({elapsed:.0f}ms)!\n"
                f"💎 Đang sử dụng phiên đăng nhập Thuê bao tháng (Claude Pro/Max/Team - 0đ phí API).",
                elapsed,
            )
        err = (proc.stderr or proc.stdout or "").strip()
        if not token:
            return (
                False,
                f"⚠️ Chưa nhập Session Token của Claude Code.\n\n"
                f"👉 Hãy lấy Token từ cookie `sessionKey` trên web claude.ai hoặc trong file `C:\\Users\\duongsinh\\.claude.json` và dán vào ô bên trên.",
                elapsed,
            )
        if "login" in err.lower() or "auth" in err.lower() or "session" in err.lower():
            return (
                False,
                f"⚠️ Phiên đăng nhập Claude Code chưa hợp lệ hoặc đã hết hạn.\n\n"
                f"👉 Hãy kiểm tra lại Session Token vừa dán (bắt đầu bằng `sk-ant-...`).",
                elapsed,
            )
        return False, f"⚠️ Claude Code phản hồi (exit {proc.returncode}): {err[:300]}", elapsed
    except subprocess.TimeoutExpired:
        elapsed = (time.perf_counter() - start) * 1000.0
        return False, f"⚠️ Quá thời gian kết nối tới Claude Code ({elapsed:.0f}ms).", elapsed
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000.0
        return False, f"❌ Lỗi thực thi Claude Code: {exc}", elapsed


def test_antigravity_cli_connection():
    """Kiểm tra kết nối Google Antigravity CLI bằng phiên đăng nhập gói thuê bao (Google Gemini Advanced).

    Trả về: (bool: is_ok, str: message, float: latency_ms)
    """
    from ai_engine import find_agy

    agy_bin = find_agy()
    if not agy_bin:
        return (
            False,
            "⚠️ Chưa tìm thấy Google Antigravity CLI ('agy') trong PATH.\n\n"
            "👉 Antigravity CLI được cài đặt khi chạy MarkItDown trên máy tính cá nhân (Desktop).",
            0.0,
        )

    start = time.perf_counter()
    try:
        cmd = [
            agy_bin,
            "-p",
            "Say 'OK' in one word",
            "--disable-slash-commands",
            "--dangerously-skip-permissions",
            "--output-format",
            "json",
        ]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            stdin=subprocess.DEVNULL,
            creationflags=flags,
        )
        elapsed = (time.perf_counter() - start) * 1000.0
        if proc.returncode == 0:
            return (
                True,
                f"✅ Kết nối thành công tới Google Antigravity CLI ({elapsed:.0f}ms)!\n"
                f"💎 Đang sử dụng phiên đăng nhập Thuê bao Google Antigravity (0đ phí API).",
                elapsed,
            )
        err = (proc.stderr or proc.stdout or "").strip()
        return False, f"⚠️ Antigravity phản hồi lỗi: {err[:300]}", elapsed
    except subprocess.TimeoutExpired:
        elapsed = (time.perf_counter() - start) * 1000.0
        return False, f"⚠️ Quá thời gian kết nối tới Antigravity ({elapsed:.0f}ms).", elapsed
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000.0
        return False, f"❌ Lỗi thực thi Antigravity: {exc}", elapsed


def get_infrastructure_status(api_key="", claude_token=""):
    """Quét toàn bộ trạng thái hạ tầng và các module của MarkItDown."""
    from ai_engine import find_agy, find_claude

    key = (api_key or "").strip() or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    c_token = (claude_token or "").strip() or os.environ.get("CLAUDE_CODE_SESSION_ACCESS_TOKEN") or os.environ.get("ANTHROPIC_SESSION_KEY")

    has_gemini_key = bool(key)
    has_claude_token = bool(c_token)
    has_agy_cli = bool(find_agy())
    has_claude_cli = bool(find_claude())

    # Trạng thái gói thuê bao tháng
    sub_status = "unconfigured"
    sub_desc = "Chưa kết nối phiên thuê bao CLI"
    if has_agy_cli:
        sub_status = "ready_agy"
        sub_desc = "⚡ Google Antigravity CLI (Thuê bao tháng - Sẵn sàng)"
    elif has_claude_cli and has_claude_token:
        sub_status = "ready_claude_token"
        sub_desc = "🟣 Claude Code CLI (Token thuê bao Pro/Max - Sẵn sàng)"
    elif has_claude_cli:
        sub_status = "ready_claude"
        sub_desc = "🟣 Claude Code CLI (Sẵn sàng phiên máy chủ)"

    # Trạng thái ONNX
    has_onnx = False
    onnx_desc = "Chưa nạp module nhận diện cờ vua"
    try:
        import chessboard_fen
        has_onnx = True
        onnx_desc = "ONNX Model sẵn sàng (Nhận diện bàn cờ & FEN)"
    except Exception as exc:
        onnx_desc = f"Không nạp được: {exc}"

    # Runtime Environment
    is_docker = bool(os.environ.get("DOCKER") or os.path.exists("/.dockerenv"))
    env_name = "Docker Container (Linux VPS)" if is_docker else f"Desktop / Native ({sys.platform})"

    return {
        "subscription": {
            "status": sub_status,
            "description": sub_desc,
            "has_agy": has_agy_cli,
            "has_claude": has_claude_cli,
            "has_claude_token": has_claude_token,
        },
        "api": {
            "has_gemini_key": has_gemini_key,
            "description": "Google Gemini REST API (Sẵn sàng)" if has_gemini_key else "Chưa nhập API Key",
        },
        "chessboard_onnx": {
            "available": has_onnx,
            "description": onnx_desc,
        },
        "environment": env_name,
    }


def render_infrastructure_html(api_key="", claude_token=""):
    """Sinh HTML hiển thị bảng trạng thái hạ tầng hệ thống cho giao diện Web."""
    status = get_infrastructure_status(api_key=api_key, claude_token=claude_token)

    def _badge(ok, true_text, false_text):
        if ok:
            return f'<span style="display:inline-flex;align-items:center;gap:4px;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700;background:rgba(31,169,143,0.15);color:#1FA98F;border:1px solid rgba(31,169,143,0.3)">● {true_text}</span>'
        return f'<span style="display:inline-flex;align-items:center;gap:4px;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700;background:rgba(245,158,11,0.15);color:#d97706;border:1px solid rgba(245,158,11,0.3)">○ {false_text}</span>'

    sub_ok = status["subscription"]["has_agy"] or status["subscription"]["has_claude_token"] or (status["subscription"]["has_claude"] and not status["environment"].startswith("Desktop"))
    sub_badge = _badge(sub_ok, status["subscription"]["description"], "Chưa kết nối CLI / Token thuê bao")
    api_badge = _badge(status["api"]["has_gemini_key"], status["api"]["description"], "Chưa cấu hình API Key")
    onnx_badge = _badge(status["chessboard_onnx"]["available"], "Sẵn sàng (ONNX FEN)", "Tắt")
    env_text = status["environment"]

    return f"""
<div class="infra-panel" style="background:var(--c-inset);border:1px solid var(--c-border);border-radius:12px;padding:16px;margin:10px 0;">
  <div style="font-size:13px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:var(--c-subtext);margin-bottom:12px;display:flex;align-items:center;gap:6px;">
    <span>⚡ Trạng thái Hạ tầng &amp; Phiên Đăng nhập AI</span>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(240px, 1fr));gap:10px;">
    <div style="background:var(--c-panel);border:1px solid var(--c-border);border-radius:10px;padding:10px 14px;">
      <div style="font-size:12px;color:var(--c-subtext);margin-bottom:4px;">💎 Gói Thuê bao Tháng (CLI Session)</div>
      <div>{sub_badge}</div>
    </div>
    <div style="background:var(--c-panel);border:1px solid var(--c-border);border-radius:10px;padding:10px 14px;">
      <div style="font-size:12px;color:var(--c-subtext);margin-bottom:4px;">🔑 Khóa API Dự phòng (Pay-as-you-go)</div>
      <div>{api_badge}</div>
    </div>
    <div style="background:var(--c-panel);border:1px solid var(--c-border);border-radius:10px;padding:10px 14px;">
      <div style="font-size:12px;color:var(--c-subtext);margin-bottom:4px;">♟️ Nhận diện Bàn cờ Cờ vua</div>
      <div>{onnx_badge}</div>
    </div>
    <div style="background:var(--c-panel);border:1px solid var(--c-border);border-radius:10px;padding:10px 14px;">
      <div style="font-size:12px;color:var(--c-subtext);margin-bottom:4px;">🌐 Môi trường Thực thi</div>
      <div style="font-size:13px;font-weight:600;color:var(--c-text);padding:3px 0;">{env_text}</div>
    </div>
  </div>
</div>
"""
