# -*- coding: utf-8 -*-
"""
Module Quản lý & Kiểm tra Hạ tầng (Infrastructure Manager) cho MarkItDown.

Cung cấp các tính năng:
1. Kiểm tra tính hợp lệ & đo độ trễ kết nối tới Google Gemini REST API.
2. Quét và tổng hợp trạng thái các thành phần hạ tầng (AI Engine, ONNX Chess Model,
   PDF/Office engines, CLI tools, runtime environment).
3. Tạo báo cáo trạng thái dạng HTML / Markdown trực quan cho giao diện người dùng.
"""

import json
import os
import shutil
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

    # Dùng endpoint v1beta models để kiểm tra nhanh tính hợp lệ và đo độ trễ
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


def get_infrastructure_status(api_key=""):
    """Quét toàn bộ trạng thái hạ tầng và các module của MarkItDown.

    Trả về dict chứa thông tin chi tiết từng module.
    """
    key = (api_key or "").strip() or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    
    # 1. AI Engine Status
    has_gemini_key = bool(key)
    has_agy_cli = bool(shutil.which("agy"))
    has_claude_cli = bool(shutil.which("claude"))
    
    ai_status = "unconfigured"
    ai_desc = "Chưa cấu hình API Key hoặc CLI"
    if has_gemini_key:
        ai_status = "ready_api"
        ai_desc = "Google Gemini REST API (Sẵn sàng)"
    elif has_agy_cli:
        ai_status = "ready_cli"
        ai_desc = "Google Antigravity CLI (Sẵn sàng trên máy cục bộ)"
    elif has_claude_cli:
        ai_status = "ready_cli"
        ai_desc = "Claude Code CLI (Sẵn sàng trên máy cục bộ)"

    # 2. ONNX Chessboard Recognizer
    has_onnx = False
    onnx_desc = "Chưa nạp module nhận diện cờ vua"
    try:
        import chessboard_fen
        has_onnx = True
        onnx_desc = "ONNX Model sẵn sàng (Nhận diện bàn cờ & FEN)"
    except Exception as exc:
        onnx_desc = f"Không nạp được: {exc}"

    # 3. Document Processing Modules
    doc_modules = {}
    for mod_name, label in [
        ("pypdfium2", "PDFium (Render PDF chất lượng cao)"),
        ("pdfminer", "PDFMiner (Trích xuất text PDF)"),
        ("docx", "Python-docx (Xử lý Word)"),
        ("pptx", "Python-pptx (Xử lý PowerPoint)"),
        ("openpyxl", "OpenPyXL (Xử lý Excel)"),
        ("PIL", "Pillow (Xử lý Ảnh)"),
    ]:
        try:
            __import__(mod_name)
            doc_modules[mod_name] = (True, label)
        except ImportError:
            doc_modules[mod_name] = (False, label)

    # 4. External CLI Tools
    has_ffmpeg = bool(shutil.which("ffmpeg") or os.environ.get("FFMPEG_PATH"))
    has_exiftool = bool(shutil.which("exiftool") or os.environ.get("EXIFTOOL_PATH"))

    # 5. Environment
    is_docker = bool(os.environ.get("DOCKER") or os.path.exists("/.dockerenv"))
    env_name = "Docker Container (Linux VPS)" if is_docker else f"Desktop / Native ({sys.platform})"

    return {
        "ai": {
            "status": ai_status,
            "description": ai_desc,
            "has_key": has_gemini_key,
            "has_agy": has_agy_cli,
            "has_claude": has_claude_cli,
        },
        "chessboard_onnx": {
            "available": has_onnx,
            "description": onnx_desc,
        },
        "doc_modules": doc_modules,
        "tools": {
            "ffmpeg": has_ffmpeg,
            "exiftool": has_exiftool,
        },
        "environment": env_name,
    }


def render_infrastructure_html(api_key=""):
    """Sinh HTML hiển thị bảng trạng thái hạ tầng hệ thống cho giao diện Web."""
    status = get_infrastructure_status(api_key=api_key)

    def _badge(ok, true_text, false_text):
        if ok:
            return f'<span style="display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:700;background:rgba(31,169,143,0.15);color:#1FA98F;border:1px solid rgba(31,169,143,0.3)">● {true_text}</span>'
        return f'<span style="display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:700;background:rgba(245,158,11,0.15);color:#d97706;border:1px solid rgba(245,158,11,0.3)">○ {false_text}</span>'

    ai_ok = status["ai"]["has_key"] or status["ai"]["has_agy"] or status["ai"]["has_claude"]
    ai_badge = _badge(ai_ok, status["ai"]["description"], "Chưa có API Key (Chỉ dùng MarkItDown thường)")
    onnx_badge = _badge(status["chessboard_onnx"]["available"], "Sẵn sàng (ONNX FEN)", "Tắt")
    env_text = status["environment"]

    return f"""
<div class="infra-panel" style="background:var(--c-inset);border:1px solid var(--c-border);border-radius:12px;padding:16px;margin:10px 0;">
  <div style="font-size:13px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:var(--c-subtext);margin-bottom:12px;display:flex;align-items:center;gap:6px;">
    <span>⚡ Trạng thái Hạ tầng &amp; Động cơ Chuyển đổi</span>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(240px, 1fr));gap:10px;">
    <div style="background:var(--c-panel);border:1px solid var(--c-border);border-radius:10px;padding:10px 14px;">
      <div style="font-size:12px;color:var(--c-subtext);margin-bottom:4px;">🤖 AI Engine (OCR &amp; Dịch thuật)</div>
      <div>{ai_badge}</div>
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
