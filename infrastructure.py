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

    token = (claude_token or "").strip() or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    env = os.environ.copy()
    env["DISABLE_AUTOUPDATER"] = "1"
    env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    if token:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token

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
                f"⚠️ Chưa có OAuth Token của Claude Code.\n\n"
                f"👉 Chạy `claude setup-token` (xem hướng dẫn bên dưới ô) để lấy token sống 1 năm, dán vào ô bên trên.",
                elapsed,
            )
        if "login" in err.lower() or "auth" in err.lower() or "session" in err.lower():
            return (
                False,
                f"⚠️ Phiên đăng nhập Claude Code chưa hợp lệ hoặc đã hết hạn.\n\n"
                f"👉 Hãy chạy lại `claude setup-token` để lấy OAuth Token mới và dán vào ô bên trên.",
                elapsed,
            )
        return False, f"⚠️ Claude Code phản hồi (exit {proc.returncode}): {err[:300]}", elapsed
    except subprocess.TimeoutExpired:
        elapsed = (time.perf_counter() - start) * 1000.0
        return False, f"⚠️ Quá thời gian kết nối tới Claude Code ({elapsed:.0f}ms).", elapsed
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000.0
        return False, f"❌ Lỗi thực thi Claude Code: {exc}", elapsed


def save_antigravity_token(token_data: str) -> bool:
    """Lưu token xác thực Antigravity CLI vào thư mục cấu hình ~/.gemini/antigravity-cli/."""
    raw = (token_data or "").strip()
    if not raw:
        return False

    home = os.path.expanduser("~")
    gemini_cli_dir = os.path.join(home, ".gemini", "antigravity-cli")
    os.makedirs(gemini_cli_dir, exist_ok=True)

    token_file = os.path.join(gemini_cli_dir, "antigravity-oauth-token")
    settings_file = os.path.join(gemini_cli_dir, "settings.json")

    # Nếu chuỗi nhập vào là JSON đầy đủ
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            with open(token_file, "w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=2)
            if not os.path.exists(settings_file):
                with open(settings_file, "w", encoding="utf-8") as f:
                    json.dump({"auth_method": parsed.get("auth_method", "consumer")}, f, indent=2)
            return True
    except Exception:
        pass

    # Nếu chỉ dán access_token hoặc refresh_token đơn lẻ
    payload = {
        "token": {
            "access_token": raw,
            "token_type": "Bearer",
            "refresh_token": raw if raw.startswith("1//") else "",
            "expiry": "2030-01-01T00:00:00Z",
        },
        "auth_method": "consumer",
    }
    try:
        with open(token_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        if not os.path.exists(settings_file):
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump({"auth_method": "consumer"}, f, indent=2)
        return True
    except Exception:
        return False


def test_antigravity_cli_connection(agy_token=""):
    """Kiểm tra kết nối Google Antigravity CLI bằng phiên đăng nhập gói thuê bao (Google Gemini Advanced/Pro).

    Trả về: (bool: is_ok, str: message, float: latency_ms)
    """
    from ai_engine import find_agy

    if agy_token and agy_token.strip():
        save_antigravity_token(agy_token.strip())

    agy_bin = find_agy()
    if not agy_bin:
        return (
            False,
            "⚠️ Chưa tìm thấy Google Antigravity CLI ('agy') trên hệ thống.\n\n"
            "👉 **Trên máy tính**: Cài đặt Antigravity và chạy qua file `run_gui.bat`.\n"
            "👉 **Trên Web VPS**: Lệnh `agy` được cài đặt tự động trong Docker container.",
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
            timeout=20,
            stdin=subprocess.DEVNULL,
            creationflags=flags,
        )
        elapsed = (time.perf_counter() - start) * 1000.0
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()

        if proc.returncode == 0:
            return (
                True,
                f"✅ Kết nối thành công tới Google Antigravity CLI ({elapsed:.0f}ms)!\n"
                f"💎 Đang sử dụng phiên đăng nhập Thuê bao Google Antigravity (0đ phí API).",
                elapsed,
            )

        if "authentication" in err.lower() or "auth" in err.lower() or "login" in err.lower() or "token" in err.lower():
            return (
                False,
                "⚠️ Phiên đăng nhập Antigravity chưa được cấu hình hoặc đã hết hạn.\n\n"
                "👉 Hãy dán nội dung token từ `C:\\Users\\<tên_bạn>\\.gemini\\antigravity-cli\\antigravity-oauth-token` vào ô bên trên.",
                elapsed,
            )
        return False, f"⚠️ Antigravity phản hồi lỗi (exit {proc.returncode}): {err[:300] or out[:300]}", elapsed
    except subprocess.TimeoutExpired:
        elapsed = (time.perf_counter() - start) * 1000.0
        return False, f"⚠️ Quá thời gian kết nối tới Antigravity ({elapsed:.0f}ms).", elapsed
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000.0
        return False, f"❌ Lỗi thực thi Antigravity: {exc}", elapsed


def get_infrastructure_status(api_key="", claude_token="", agy_token=""):
    """Quét toàn bộ trạng thái hạ tầng và các module của MarkItDown."""
    from ai_engine import find_agy, find_claude

    if agy_token and agy_token.strip():
        save_antigravity_token(agy_token.strip())

    key = (api_key or "").strip() or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    c_token = (claude_token or "").strip() or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")

    has_gemini_key = bool(key)
    has_claude_token = bool(c_token)
    has_agy_cli = bool(find_agy())
    has_claude_cli = bool(find_claude())

    # Kiểm tra token Antigravity trên đĩa
    home = os.path.expanduser("~")
    has_agy_token_file = os.path.exists(os.path.join(home, ".gemini", "antigravity-cli", "antigravity-oauth-token")) or bool(agy_token)

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
        "antigravity": {
            "has_cli": has_agy_cli,
            "has_token": has_agy_token_file,
            "ready": has_agy_cli and has_agy_token_file,
            "description": "⚡ Google Antigravity CLI (Sẵn sàng)" if (has_agy_cli and has_agy_token_file) else ("CLI sẵn sàng, cần Token" if has_agy_cli else "Chưa có CLI"),
        },
        "claude": {
            "has_cli": has_claude_cli,
            "has_token": has_claude_token,
            "ready": has_claude_cli and (has_claude_token or not is_docker),
            "description": "🟣 Claude Code CLI (Sẵn sàng)" if (has_claude_cli and (has_claude_token or not is_docker)) else ("CLI sẵn sàng, cần Token" if has_claude_cli else "Chưa có CLI"),
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


def get_dropbox_token_from_refresh(refresh_token: str, app_key: str, app_secret: str):
    """Lấy Access Token mới từ Refresh Token + App Key + App Secret qua Dropbox OAuth2 API.

    Trả về: (str: access_token, str: error_msg)
    """
    rf = (refresh_token or "").strip()
    ak = (app_key or "").strip()
    as_ = (app_secret or "").strip()
    if not rf or not ak or not as_:
        return "", "Thiếu Refresh Token, App Key hoặc App Secret."

    url = "https://api.dropboxapi.com/oauth2/token"
    data = (
        f"grant_type=refresh_token&refresh_token={urllib.request.quote(rf)}"
        f"&client_id={urllib.request.quote(ak)}&client_secret={urllib.request.quote(as_)}"
    ).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "MarkItDown-GUI/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            if resp.status == 200:
                res = json.loads(resp.read().decode("utf-8"))
                access_token = res.get("access_token", "")
                if access_token:
                    return access_token, None
                return "", "Không nhận được access_token từ phản hồi của Dropbox."
            return "", f"Dropbox phản hồi mã HTTP {resp.status}."
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
            err_desc = body.get("error_description") or body.get("error", str(exc))
        except Exception:
            err_desc = str(exc)
        return "", f"Lỗi làm mới token ({exc.code}): {err_desc}"
    except Exception as exc:
        return "", f"Lỗi kết nối khi làm mới token: {exc}"


def resolve_dropbox_token(token="", refresh_token="", app_key="", app_secret=""):
    """Phân giải Dropbox Access Token hợp lệ từ các nguồn cấu hình (Token trực tiếp, Refresh Token hoặc Biến môi trường).

    Trả về: (str: access_token, str: error_msg)
    """
    tok = (token or "").strip() or os.environ.get("DROPBOX_ACCESS_TOKEN", "").strip()
    rf = (refresh_token or "").strip() or os.environ.get("DROPBOX_REFRESH_TOKEN", "").strip()
    ak = (app_key or "").strip() or os.environ.get("DROPBOX_APP_KEY", "").strip()
    as_ = (app_secret or "").strip() or os.environ.get("DROPBOX_APP_SECRET", "").strip()

    # Nếu có Refresh Token + Key + Secret -> ưu tiên lấy token mới nhất
    if rf and ak and as_:
        new_tok, err = get_dropbox_token_from_refresh(rf, ak, as_)
        if new_tok:
            return new_tok, None
        # Nếu refresh lỗi mà có token trực tiếp thì thử fallback
        if tok:
            return tok, f"Lưu ý: Không làm mới được từ Refresh Token ({err}), dùng Access Token có sẵn."
        return "", err

    if tok:
        return tok, None

    return "", "Chưa cung cấp Dropbox Access Token hoặc Refresh Token."


def test_dropbox_connection(token="", refresh_token="", app_key="", app_secret=""):
    """Kiểm tra kết nối tới tài khoản Dropbox, lấy thông tin người dùng và dung lượng lưu trữ.

    Trả về: (bool: is_ok, str: message, float: latency_ms)
    """
    start = time.perf_counter()
    access_token, err = resolve_dropbox_token(token, refresh_token, app_key, app_secret)
    if not access_token:
        elapsed = (time.perf_counter() - start) * 1000.0
        return False, f"❌ {err}", elapsed

    account_url = "https://api.dropboxapi.com/2/users/get_current_account"
    space_url = "https://api.dropboxapi.com/2/users/get_space_usage"

    try:
        # 1. Lấy thông tin tài khoản
        req_acc = urllib.request.Request(
            account_url,
            data=b"null",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "User-Agent": "MarkItDown-GUI/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req_acc, timeout=12) as resp_acc:
            acc_data = json.loads(resp_acc.read().decode("utf-8"))

        display_name = acc_data.get("name", {}).get("display_name", "Tài khoản Dropbox")
        email = acc_data.get("email", "")

        # 2. Lấy thông tin dung lượng
        space_info = ""
        try:
            req_sp = urllib.request.Request(
                space_url,
                data=b"null",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "User-Agent": "MarkItDown-GUI/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req_sp, timeout=10) as resp_sp:
                sp_data = json.loads(resp_sp.read().decode("utf-8"))
                used = sp_data.get("used", 0)
                alloc = sp_data.get("allocation", {})
                allocated = alloc.get("allocated", 0)
                if allocated > 0:
                    used_gb = used / (1024 ** 3)
                    alloc_gb = allocated / (1024 ** 3)
                    space_info = f" · Dung lượng: {used_gb:.2f} GB / {alloc_gb:.1f} GB"
        except Exception:
            pass

        elapsed = (time.perf_counter() - start) * 1000.0
        msg = f"✅ Kết nối thành công tới Dropbox ({elapsed:.0f}ms)!\n👤 Tài khoản: **{display_name}** ({email}){space_info}\n☁️ Sẵn sàng đồng bộ kết quả chuyển đổi."
        return True, msg, elapsed

    except urllib.error.HTTPError as exc:
        elapsed = (time.perf_counter() - start) * 1000.0
        try:
            body = exc.read().decode("utf-8")
            err_json = json.loads(body)
            msg = err_json.get("error_summary", str(exc))
        except Exception:
            msg = str(exc)
        if exc.code == 401:
            return False, f"❌ Lỗi xác thực Dropbox (401 Unauthorized): Token không hợp lệ hoặc đã hết hạn.\n\n👉 Mẹo: Hãy sử dụng cấu hình 'Refresh Token + App Key + App Secret' để tự động duy trì kết nối vĩnh viễn.", elapsed
        return False, f"❌ Lỗi Dropbox API ({exc.code}): {msg}", elapsed
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000.0
        return False, f"❌ Lỗi kết nối mạng tới Dropbox: {exc}", elapsed


def upload_to_dropbox(file_path: str, target_folder: str = "/MarkItDown", token="", refresh_token="", app_key="", app_secret=""):
    """Tải một tệp cục bộ lên thư mục chỉ định trên Dropbox.

    Trả về: (str: remote_path, str: error_msg)
    """
    if not file_path or not os.path.exists(file_path):
        return None, f"Tệp cục bộ không tồn tại: {file_path}"

    access_token, err = resolve_dropbox_token(token, refresh_token, app_key, app_secret)
    if not access_token:
        return None, f"Không thể xác thực Dropbox: {err}"

    folder = (target_folder or "/MarkItDown").strip()
    if not folder.startswith("/"):
        folder = "/" + folder
    if folder.endswith("/") and len(folder) > 1:
        folder = folder[:-1]

    filename = os.path.basename(file_path)
    remote_path = f"{folder}/{filename}" if folder != "/" else f"/{filename}"

    # Đọc dữ liệu file
    try:
        with open(file_path, "rb") as f:
            data = f.read()
    except Exception as exc:
        return None, f"Không đọc được tệp {file_path}: {exc}"

    upload_url = "https://content.dropboxapi.com/2/files/upload"
    api_args = {
        "path": remote_path,
        "mode": "overwrite",
        "autorename": False,
        "mute": False,
        "strict_conflict": False,
    }

    try:
        req = urllib.request.Request(
            upload_url,
            data=data,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Dropbox-API-Arg": json.dumps(api_args),
                "Content-Type": "application/octet-stream",
                "User-Agent": "MarkItDown-GUI/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 200:
                return remote_path, None
            return None, f"Dropbox phản hồi mã HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8")
            err_json = json.loads(body)
            msg = err_json.get("error_summary", str(exc))
        except Exception:
            msg = str(exc)
        return None, f"Lỗi tải lên Dropbox ({exc.code}): {msg}"
    except Exception as exc:
        return None, f"Lỗi kết nối khi tải lên Dropbox: {exc}"


def render_infrastructure_html(api_key="", claude_token="", agy_token=""):
    """Sinh HTML hiển thị bảng trạng thái hạ tầng hệ thống cho giao diện Web."""
    status = get_infrastructure_status(api_key=api_key, claude_token=claude_token, agy_token=agy_token)

    def _badge(ok, true_text, false_text):
        if ok:
            return f'<span style="display:inline-flex;align-items:center;gap:4px;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700;background:rgba(31,169,143,0.15);color:#1FA98F;border:1px solid rgba(31,169,143,0.3)">● {true_text}</span>'
        return f'<span style="display:inline-flex;align-items:center;gap:4px;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700;background:rgba(245,158,11,0.15);color:#d97706;border:1px solid rgba(245,158,11,0.3)">○ {false_text}</span>'

    agy_badge = _badge(status["antigravity"]["ready"], status["antigravity"]["description"], status["antigravity"]["description"])
    claude_badge = _badge(status["claude"]["ready"], status["claude"]["description"], status["claude"]["description"])
    api_badge = _badge(status["api"]["has_gemini_key"], status["api"]["description"], "Chưa cấu hình API Key")
    onnx_badge = _badge(status["chessboard_onnx"]["available"], "Sẵn sàng (ONNX FEN)", "Tắt")
    env_text = status["environment"]

    return f"""
<div class="infra-panel" style="background:var(--c-inset);border:1px solid var(--c-border);border-radius:12px;padding:16px;margin:10px 0;">
  <div style="font-size:13px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:var(--c-subtext);margin-bottom:12px;display:flex;align-items:center;gap:6px;">
    <span>⚡ Trạng thái Hạ tầng &amp; Phiên Đăng nhập AI</span>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));gap:10px;">
    <div style="background:var(--c-panel);border:1px solid var(--c-border);border-radius:10px;padding:10px 14px;">
      <div style="font-size:12px;color:var(--c-subtext);margin-bottom:4px;">⚡ Antigravity CLI (Google Thuê bao)</div>
      <div>{agy_badge}</div>
    </div>
    <div style="background:var(--c-panel);border:1px solid var(--c-border);border-radius:10px;padding:10px 14px;">
      <div style="font-size:12px;color:var(--c-subtext);margin-bottom:4px;">🟣 Claude Code CLI (Claude Thuê bao)</div>
      <div>{claude_badge}</div>
    </div>
    <div style="background:var(--c-panel);border:1px solid var(--c-border);border-radius:10px;padding:10px 14px;">
      <div style="font-size:12px;color:var(--c-subtext);margin-bottom:4px;">🔑 Khóa Gemini REST API (Dự phòng)</div>
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


