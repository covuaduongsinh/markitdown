# -*- coding: utf-8 -*-
"""
Màn hình (GUI web) chạy MarkItDown bằng Gradio.

Cách chạy:
    .venv\\Scripts\\python.exe markitdown_gui.py
hoặc nhấp đúp run_gui.bat

Sau khi chạy, mở trình duyệt tại http://127.0.0.1:7860
"""

import os
import queue
import subprocess
import sys
import threading
import time
import traceback

import gradio as gr

from ai_engine import (
    ENGINE_ANTIGRAVITY,
    ENGINE_LABELS,
    ANTIGRAVITY_OCR_MODELS,
    ANTIGRAVITY_TRANSLATE_MODELS,
    CLAUDE_OCR_MODELS,
    CLAUDE_TRANSLATE_MODELS,
    get_default_engine,
)
import infrastructure
import claude_login_bridge
from pipeline import (
    _OUTPUT_DIR,
    AUTOSAVE_CUSTOM,
    AUTOSAVE_SRC,
    MODE_CHESS,
    MODE_CHESS_ES,
    MODE_CHESS_RU,
    MODE_GENERAL,
    _chess_lang_from_mode,
    _effort_from_label,
    _is_chess_mode,
    _model_from_label,
    _publish_output,
    _resolve_save_dir,
    _translate_to_vn,
    _write_fen_file,
    convert_file,
    convert_url,
)
from presets import (
    PRESET_ACCURATE,
    PRESET_BALANCED,
    PRESET_SAVER,
    _PRESET_HINTS,
    _apply_preset,
    _load_prefs,
    _save_prefs,
)
from ui_render import _download_panel
from ui_theme import (
    _ASSETS_DIR,
    CSS,
    HEAD,
    MODE_CARDS_HTML,
    THEME,
    TOPBAR_HTML,
)



_STATUS_HINT = "👋 Chọn tệp hoặc dán URL rồi bấm **Chuyển đổi**."


def _with_download_update(result, auto_download=False):
    """Đổi đường dẫn tải về thành bảng HTML chứa nút tải."""
    preview_md, raw_md, path, status_md = result
    return preview_md, raw_md, _download_panel([path] if path else [], auto_download=auto_download), status_md



def _stream_job(func, kwargs, label, unit):
    """Chạy func(**kwargs, progress=...) trong thread nền, generator yield
    dòng tiến độ đều đặn (≤5s/lần) để kết nối SSE của Gradio không bị rớt
    khi tác vụ kéo dài. Kết thúc trả về kết quả của func (qua StopIteration).

    unit: tên đơn vị tiến độ hiển thị ("trang", "đoạn"...).
    """
    q = queue.Queue()
    out = {}

    def run():
        try:
            out["result"] = func(progress=lambda i, n: q.put((i, n)), **kwargs)
        except BaseException as exc:
            out["error"] = exc
        finally:
            q.put(None)  # báo hiệu kết thúc

    threading.Thread(target=run, daemon=True).start()
    start = time.monotonic()
    suffix = ""
    finished = False
    while not finished:
        try:
            msgs = [q.get(timeout=5)]
        except queue.Empty:
            msgs = []  # không có tiến độ mới -> vẫn yield keep-alive
        while True:  # gộp các message dồn lại, chỉ giữ cái mới nhất
            try:
                msgs.append(q.get_nowait())
            except queue.Empty:
                break
        for m in msgs:
            if m is None:
                finished = True
            else:
                suffix = f" — {unit} {m[0]}/{m[1]}"
        if finished:
            break
        yield f"{label}{suffix} · {int(time.monotonic() - start)}s…"
    if "error" in out:
        raise out["error"]
    return out.get("result")


def _picked_display(paths):
    """Markdown liệt kê các tệp đã chọn bằng hộp thoại (giữ đường dẫn gốc)."""
    if not paths:
        return ""
    rows = "\n".join(f"- `{p}`" for p in paths)
    return f"**📂 Đã chọn {len(paths)} tệp (giữ đường dẫn gốc):**\n{rows}"


def on_pick_files():
    """Mở hộp thoại chọn tệp gốc của Windows (qua tiến trình con pick_files.py).

    Trả về (danh sách đường dẫn THẬT, Markdown hiển thị) để cập nhật State + view.
    """
    if sys.platform != "win32" or os.environ.get("DOCKER"):
        return [], "ℹ️ Hộp thoại chọn tệp hệ thống chỉ dùng khi chạy ứng dụng trên máy tính cá nhân (Windows). Trên Web, vui lòng kéo-thả hoặc bấm vào ô tải tệp."
    helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pick_files.py")
    # Ẩn cửa sổ console của tiến trình con (hộp thoại tkinter vẫn hiện bình thường).
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        res = subprocess.run(
            [sys.executable, helper],
            capture_output=True, text=True, encoding="utf-8", timeout=300,
            creationflags=flags,
        )
        paths = [ln for ln in res.stdout.splitlines() if ln.strip()]
    except Exception as exc:
        return [], f"⚠️ Không mở được hộp thoại chọn tệp: {exc}"
    return paths, _picked_display(paths)


def on_convert_files(
    file_paths, mode_label, enable_plugins, use_ocr,
    model_label, ocr_effort_label, translate_model_label, translate_effort_label,
    force_ocr, board_dpi_label, translate_vn, merge_ocr_translate, ocr_pages_label,
    autosave_on, auto_download_on, autosave_dir, picked_paths, autosave_target, engine,
    api_key="", claude_token="", agy_token="",
    dropbox_sync_on=True, dropbox_folder="/MarkItDown",
    dropbox_token="", dropbox_refresh_token="", dropbox_app_key="", dropbox_app_secret="",
):
    try:
        raw_sources = picked_paths if picked_paths else file_paths
        sources_are_real = bool(picked_paths)
        sources = []
        if raw_sources:
            if isinstance(raw_sources, (str, bytes)):
                sources = [str(raw_sources)]
            elif isinstance(raw_sources, list):
                for item in raw_sources:
                    if not item:
                        continue
                    if isinstance(item, str):
                        sources.append(item)
                    elif isinstance(item, dict) and "path" in item:
                        sources.append(item["path"])
                    elif hasattr(item, "path"):
                        sources.append(getattr(item, "path"))
                    else:
                        sources.append(str(item))

        if not sources:
            yield (
                "",
                "",
                "",
                "⚠️ **Chưa có tệp nào được tải lên.**\n\nVui lòng kéo-thả tệp vào khung tải tệp ở trên trước khi bấm **Chuyển đổi**.",
            )
            return

        dropbox_cfg = dict(
            folder=dropbox_folder, token=dropbox_token, refresh_token=dropbox_refresh_token,
            app_key=dropbox_app_key, app_secret=dropbox_app_secret,
        )
        chess = _is_chess_mode(mode_label)
        chess_lang = _chess_lang_from_mode(mode_label)
        # Gộp OCR+dịch chỉ có nghĩa khi người dùng cũng bật dịch tiếng Việt.
        merge = bool(merge_ocr_translate and translate_vn)
        total = len(sources)
        n_ok = 0  # số tệp nguồn chuyển đổi thành công (không tính tệp _vn)
        done_paths, previews, raws, lines = [], [], [], []

        # Phản hồi tức thì ngay tại frame đầu tiên
        yield (
            "",
            "",
            "",
            f"🚀 **Đang khởi động tiến trình chuyển đổi ({total} tệp)...**",
        )

        for i, fp in enumerate(sources, 1):
            name = os.path.basename(fp)
            # Báo tiến độ trước khi xử lý, giữ nguyên kết quả các tệp đã xong.
            progress = "\n\n".join(lines + [f"⏳ Đang xử lý {i}/{total}: **{name}**… (Đang phân tích định dạng)"])
            yield (
                "\n\n---\n\n".join(previews),
                "\n\n".join(raws),
                _download_panel(done_paths, auto_download=auto_download_on),
                progress,
            )

            try:
                # Chạy trong thread nền, yield tiến độ từng trang để giữ kết nối.
                job = _stream_job(
                    convert_file,
                    dict(
                        file_path=fp, enable_plugins=enable_plugins, use_ocr=use_ocr,
                        model_label=model_label, force_ocr=force_ocr,
                        board_dpi_label=board_dpi_label, used_paths=done_paths,
                        chess=chess, chess_lang=chess_lang,
                        ocr_effort_label=ocr_effort_label,
                        merge_translate=merge, ocr_pages_label=ocr_pages_label,
                        engine=engine, api_key=api_key or None,
                        claude_token=claude_token or None,
                        agy_token=agy_token or None,
                    ),
                    label=f"⏳ Đang xử lý {i}/{total}: **{name}**",
                    unit="trang",
                )
                while True:
                    try:
                        st_line = next(job)
                    except StopIteration as stop:
                        preview, raw_md, path, st, translated = stop.value
                        break
                    # Yield tiến độ chỉ cập nhật status (gr.skip các ô còn lại
                    # để giảm payload gửi về trình duyệt).
                    yield gr.skip(), gr.skip(), gr.skip(), "\n\n".join(lines + [st_line])

                # Thư mục đích tính một lần cho mỗi tệp nguồn, dùng chung cho tệp gốc
                # lẫn tệp _vn.md.
                save_dir, save_note = _resolve_save_dir(
                    fp, autosave_target, autosave_dir, sources_are_real
                )
                if path:
                    st += _publish_output(
                        path, save_dir, save_note=save_note, dropbox_cfg=dropbox_cfg,
                        autosave_on=autosave_on, dropbox_sync_on=dropbox_sync_on,
                        auto_download_on=auto_download_on,
                    )
                if path:
                    n_ok += 1
                    done_paths.append(path)

                # Dịch sang tiếng Việt -> tạo thêm tệp _vn.md (nếu được bật).
                if translate_vn and not translated and path and (raw_md or "").strip():
                    yield (
                        "\n\n---\n\n".join(previews),
                        "\n\n".join(raws),
                        _download_panel(done_paths, auto_download=auto_download_on),
                        "\n\n".join(
                            lines + [f"**{name}** — {st}",
                                     f"⏳ Đang dịch sang tiếng Việt {i}/{total}: **{name}**…"]
                        ),
                    )
                    model = _model_from_label(translate_model_label)
                    translate_effort = _effort_from_label(
                        translate_effort_label, default="low"
                    )
                    job = _stream_job(
                        _translate_to_vn,
                        dict(
                            raw_md=raw_md, orig_path=path, model=model,
                            done_paths=done_paths, chess=chess, chess_lang=chess_lang,
                            effort=translate_effort, engine=engine,
                            api_key=api_key or None, claude_token=claude_token or None,
                            agy_token=agy_token or None,
                        ),
                        label=f"⏳ Đang dịch sang tiếng Việt {i}/{total}: **{name}**",
                        unit="đoạn",
                    )
                    while True:
                        try:
                            st_line = next(job)
                        except StopIteration as stop:
                            vn_path, vn_st = stop.value
                            break
                        yield (
                            gr.skip(), gr.skip(), gr.skip(),
                            "\n\n".join(lines + [f"**{name}** — {st}", st_line]),
                        )
                    st += f"\n  {vn_st}"
                    if vn_path:
                        st += _publish_output(
                            vn_path, save_dir, dropbox_cfg=dropbox_cfg, inline=True,
                            autosave_on=autosave_on, dropbox_sync_on=dropbox_sync_on,
                            auto_download_on=auto_download_on,
                        )
                        done_paths.append(vn_path)

                # Sách cờ vua (mặc định): gom FEN các thế cờ -> tệp <tên gốc>_fen.txt
                if chess and path and (raw_md or "").strip():
                    fen_base = os.path.splitext(os.path.basename(fp))[0]
                    fen_path, n_fen = _write_fen_file(raw_md, fen_base, done_paths)
                    if fen_path:
                        st += f"\n  ♟️ Đã gom {n_fen} thế cờ → `{os.path.basename(fen_path)}`"
                        st += _publish_output(
                            fen_path, save_dir, dropbox_cfg=dropbox_cfg, inline=True,
                            autosave_on=autosave_on, dropbox_sync_on=dropbox_sync_on,
                            auto_download_on=auto_download_on,
                        )
                        done_paths.append(fen_path)
                lines.append(f"**{name}** — {st}")
                if preview:
                    previews.append(f"## 📄 {name}\n\n{preview}")
                if raw_md:
                    raws.append(raw_md)

            except Exception as exc:
                err_msg = f"❌ Lỗi xử lý {name}: {type(exc).__name__}: {exc}"
                lines.append(f"**{name}** — {err_msg}")
                traceback.print_exc()

            # Tệp xong tới đâu hiện kết quả và cho tải về ngay tới đó.
            summary = "\n\n".join(lines)
            if i == total:
                summary = f"🏁 Xong {n_ok}/{total} tệp.\n\n" + summary
            yield (
                "\n\n---\n\n".join(previews),
                "\n\n".join(raws),
                _download_panel(done_paths, auto_download=auto_download_on),
                summary,
            )
    except Exception as top_exc:
        yield "", "", "", f"❌ Đã xảy ra lỗi không mong muốn: {top_exc}"


def on_convert_url(
    url, enable_plugins, auto_download_on=True,
    dropbox_sync_on=False, dropbox_folder="/MarkItDown",
    dropbox_token="", dropbox_refresh_token="", dropbox_app_key="", dropbox_app_secret="",
):
    preview, raw_md, path, st = convert_url(url, enable_plugins)
    if path and dropbox_sync_on:
        dbx_path, dbx_err = infrastructure.upload_to_dropbox(
            path, target_folder=dropbox_folder,
            token=dropbox_token, refresh_token=dropbox_refresh_token,
            app_key=dropbox_app_key, app_secret=dropbox_app_secret,
        )
        if dbx_path:
            st += f"\n  ☁️ [Dropbox] Đã đồng bộ: `{dbx_path}`"
        elif dbx_err:
            st += f"\n  ⚠️ [Dropbox] {dbx_err}"
    paths = [path] if path else []
    return preview, raw_md, _download_panel(paths, auto_download=auto_download_on), st


def on_clear():
    # Xoá kết quả + danh sách tệp đã chọn bằng hộp thoại.
    return "", "", "", _STATUS_HINT, [], ""


def _convert_btn_label(n):
    return f"Chuyển đổi {n} tệp" if n else "Chuyển đổi"


def _set_running(running):
    """Đang chạy -> ẩn nút Chuyển đổi, hiện nút Dừng (và ngược lại khi xong)."""
    return gr.update(visible=not running), gr.update(visible=running)


def _on_files_change(files):
    """Kéo-thả tệp mới -> xoá lựa chọn từ hộp thoại + cập nhật nhãn nút."""
    n = len(files) if files else 0
    return [], "", gr.update(value=_convert_btn_label(n))


def build_ui():
    default_eng = get_default_engine()

    with gr.Blocks(title="MarkItDown") as demo:
        # ---- thanh tiêu đề navy (sticky) ----
        gr.HTML(TOPBAR_HTML)

        with gr.Row(elem_id="mid-workspace"):
            # ============ CỘT TRÁI — nhập liệu & điều khiển ============
            with gr.Column(elem_classes="mid-col-left"):

                # --- panel nhập liệu ---
                with gr.Group(elem_classes=["mid-card", "mid-input-card"]):
                    with gr.Tabs(elem_classes="mid-input-tabs"):
                        with gr.Tab("Từ tệp"):
                            gr.HTML(
                                '<div class="mid-drop-caption"><b>Kéo-thả tệp vào đây</b> '
                                "— hoặc bấm để chọn (PDF, Word, Excel, PPT, ảnh)</div>"
                            )
                            file_in = gr.File(
                                show_label=False,
                                type="filepath",
                                file_count="multiple",
                                height=130,
                                elem_id="mid-file",
                            )
                            picked_state = gr.State([])  # đường dẫn THẬT từ hộp thoại
                            btn_pick = gr.Button(
                                "Chọn tệp từ máy (giữ đường dẫn gốc để lưu cạnh file)",
                                elem_classes="mid-pick-btn",
                            )
                            picked_view = gr.Markdown(elem_classes="mid-picked-view")
                        with gr.Tab("Từ URL"):
                            url_in = gr.Textbox(
                                label="",
                                show_label=False,
                                placeholder="https://… hoặc link YouTube / Wikipedia",
                                info="Hỗ trợ YouTube, Wikipedia, RSS và trang web bất kỳ. Nội dung được tải về và chuyển thành Markdown.",
                                elem_classes="mid-url-box",
                            )
                            btn_url = gr.Button(
                                "Chuyển đổi URL", variant="primary", elem_id="mid-convert-url"
                            )
                        with gr.Tab("⚙️ Cài đặt Hạ tầng & API"):
                            infra_status_html = gr.HTML(
                                infrastructure.render_infrastructure_html(),
                                elem_id="mid-infra-status",
                            )
                            with gr.Group():
                                gr.HTML(
                                    '<div style="font-size:13px;font-weight:700;color:var(--c-text);margin-bottom:6px;">'
                                    '⚡ 1. Google Antigravity CLI (Gói Thuê bao Google Gemini Advanced - 0đ phí API)'
                                    '</div>'
                                )
                                agy_token_in = gr.Textbox(
                                    label="Google Antigravity OAuth Token / JSON Credentials",
                                    placeholder='Dán chuỗi token hoặc toàn bộ nội dung file antigravity-oauth-token / oauth_creds.json',
                                    type="password",
                                    value="",
                                    elem_classes="mid-agy-token",
                                    info="Dùng gói thuê bao Google Antigravity / Gemini Advanced trên VPS (0đ token API).",
                                )
                                with gr.Row():
                                    btn_test_agy = gr.Button(
                                        "🔍 Kiểm tra kết nối Antigravity CLI",
                                        variant="secondary",
                                        size="sm",
                                    )
                                agy_test_status = gr.Markdown(
                                    "",
                                    elem_id="mid-agy-test-status",
                                )
                                gr.HTML(
                                    '<div style="margin-top:8px;padding:10px 14px;border-radius:8px;'
                                    'background:rgba(31,169,143,0.06);border:1px solid rgba(31,169,143,0.18);'
                                    'font-size:12.5px;color:var(--c-text);line-height:1.6;">'
                                    '⚡ <b>Cách lấy Token Antigravity từ máy tính để dùng trên VPS:</b><br>'
                                    '• Mở tệp: <code>C:\\Users\\&lt;tên_bạn&gt;\\.gemini\\antigravity-cli\\antigravity-oauth-token</code> (hoặc <code>oauth_creds.json</code>).<br>'
                                    '• Copy toàn bộ nội dung trong tệp và dán vào ô trên → bấm <b>Kiểm tra kết nối Antigravity CLI</b>.<br>'
                                    '• Hệ thống sẽ tự động lưu và kết nối phiên Google Antigravity của bạn vĩnh viễn trên VPS!</div>'
                                )

                            gr.HTML('<div style="height:1px;background:var(--c-border);margin:12px 0;"></div>')

                            with gr.Group():
                                gr.HTML(
                                    '<div style="font-size:13px;font-weight:700;color:var(--c-text);margin-bottom:6px;">'
                                    '🟣 2. Claude Code CLI (Gói Thuê bao Claude Pro / Team / Max - 0đ phí API)'
                                    '</div>'
                                )
                                claude_token_in = gr.Textbox(
                                    label="Claude Code OAuth Token",
                                    placeholder="Dán token sinh bởi lệnh `claude setup-token` (hạn dùng ~1 năm)",
                                    type="password",
                                    value="",
                                    elem_classes="mid-claude-token",
                                    info="Dùng gói thuê bao tháng Claude Pro/Team/Max để OCR và dịch thuật miễn phí 100% (không tính phí token API).",
                                )
                                with gr.Row():
                                    btn_test_sub = gr.Button(
                                        "🔍 Kiểm tra kết nối Claude Code CLI",
                                        variant="secondary",
                                        size="sm",
                                    )
                                sub_test_status = gr.Markdown(
                                    "",
                                    elem_id="mid-sub-test-status",
                                )
                                gr.HTML(
                                    '<div style="margin-top:8px;padding:10px 14px;border-radius:8px;'
                                    'background:rgba(43,57,144,0.06);border:1px solid rgba(43,57,144,0.18);'
                                    'font-size:12.5px;color:var(--c-text);line-height:1.6;">'
                                    '🟣 <b>Cách lấy Claude Code OAuth Token (hạn dùng ~1 năm):</b><br>'
                                    '• Trên máy có cài Claude Code CLI (hoặc SSH vào server), chạy lệnh <code>claude setup-token</code>.<br>'
                                    '• Mở URL hiện ra trên trình duyệt của bạn, đăng nhập bằng tài khoản Claude Pro/Max, dán mã xác nhận ngược lại terminal nếu được hỏi.<br>'
                                    '• Copy token được in ra, dán vào ô trên và bấm <b>Kiểm tra kết nối Claude Code CLI</b>.</div>'
                                )

                                gr.HTML('<div style="height:1px;background:var(--c-border);margin:10px 0;"></div>')
                                gr.HTML(
                                    '<div style="font-size:12.5px;font-weight:700;color:var(--c-text);margin-bottom:4px;">'
                                    '🔐 Hoặc đăng nhập trực tiếp ngay tại đây (không cần SSH vào VPS)'
                                    '</div>'
                                )
                                with gr.Row():
                                    btn_claude_login_start = gr.Button(
                                        "🔐 Đăng nhập Claude Code", variant="secondary", size="sm"
                                    )
                                    btn_claude_login_cancel = gr.Button(
                                        "✖ Hủy", variant="stop", size="sm", visible=False
                                    )
                                claude_login_url_md = gr.Markdown("", visible=False)
                                claude_login_code_in = gr.Textbox(
                                    label="Dán mã xác nhận (nếu trang web yêu cầu)",
                                    placeholder="Dán mã hiện trên trình duyệt sau khi đăng nhập claude.ai",
                                    visible=False,
                                )
                                btn_claude_login_submit = gr.Button(
                                    "✅ Xác nhận mã", variant="primary", size="sm", visible=False
                                )
                                claude_login_result_md = gr.Markdown("")
                                claude_login_session_state = gr.State("")

                            gr.HTML('<div style="height:1px;background:var(--c-border);margin:12px 0;"></div>')

                            with gr.Group():
                                gr.HTML(
                                    '<div style="font-size:13px;font-weight:700;color:var(--c-text);margin-bottom:6px;">'
                                    '🔑 3. Khóa API Google Gemini (Dự phòng cho REST API)'
                                    '</div>'
                                )
                                api_key_in = gr.Textbox(
                                    label="Google Gemini API Key (Dùng trực tiếp trên Web)",
                                    placeholder="AIzaSy... (lưu an toàn trên trình duyệt của bạn)",
                                    type="password",
                                    value="",
                                    elem_classes="mid-api-key",
                                    info="Dùng cho OCR nhận diện thế cờ & dịch tiếng Việt trực tiếp qua REST API (không cần cài CLI).",
                                )
                                with gr.Row():
                                    btn_test_api = gr.Button(
                                        "🔍 Kiểm tra kết nối API Key",
                                        variant="secondary",
                                        size="sm",
                                    )
                                api_test_status = gr.Markdown(
                                    "",
                                    elem_id="mid-api-test-status",
                                )
                                gr.HTML('<div style="height:1px;background:var(--c-border);margin:12px 0;"></div>')

                            with gr.Group():
                                gr.HTML(
                                    '<div style="font-size:13px;font-weight:700;color:var(--c-text);margin-bottom:6px;">'
                                    '☁️ 4. Cấu hình Đồng bộ Đám mây Dropbox (Dropbox Cloud Sync)'
                                    '</div>'
                                )
                                dropbox_token_in = gr.Textbox(
                                    label="Dropbox Access Token hoặc Refresh Token",
                                    placeholder="sl.u... hoặc Refresh Token (lưu an toàn trên trình duyệt)",
                                    type="password",
                                    value="",
                                    elem_classes="mid-api-key",
                                    info="Dùng để tự động đồng bộ tất cả tệp kết quả (.md, _vn.md, _fen.txt) lên tài khoản Dropbox của bạn.",
                                )
                                with gr.Row():
                                    dropbox_app_key_in = gr.Textbox(
                                        label="Dropbox App Key (Dành cho Refresh Token)",
                                        placeholder="vd: abc123xyz...",
                                        value="",
                                        elem_classes="mid-api-key",
                                    )
                                    dropbox_app_secret_in = gr.Textbox(
                                        label="Dropbox App Secret (Dành cho Refresh Token)",
                                        placeholder="vd: sec123...",
                                        type="password",
                                        value="",
                                        elem_classes="mid-api-key",
                                    )
                                dropbox_folder_in = gr.Textbox(
                                    label="Thư mục mặc định trên Dropbox",
                                    value="/MarkItDown",
                                    elem_classes="mid-autosave-dir",
                                    info="Các tệp chuyển đổi sẽ được lưu vào thư mục này trên Dropbox (mặc định: /MarkItDown).",
                                )
                                with gr.Row():
                                    btn_test_dropbox = gr.Button(
                                        "🔍 Kiểm tra kết nối Dropbox",
                                        variant="secondary",
                                        size="sm",
                                    )
                                dropbox_test_status = gr.Markdown(
                                    "",
                                    elem_id="mid-dropbox-test-status",
                                )
                                gr.HTML(
                                    '<div style="margin-top:6px;padding:8px 12px;border-radius:8px;'
                                    'background:rgba(0,97,254,0.06);border:1px solid rgba(0,97,254,0.2);'
                                    'font-size:12.5px;color:var(--c-text);line-height:1.6;">'
                                    '☁️ <b>Cách lấy Token Dropbox (1 phút):</b><br>'
                                    '• Truy cập <a href="https://www.dropbox.com/developers/apps" target="_blank" style="color:#0061FE;font-weight:700;text-decoration:underline;">Dropbox App Console</a> → Tạo App (chọn <b>Scoped Access</b> → <b>Full Dropbox</b> hoặc <b>App Folder</b>).<br>'
                                    '• Tab <b>Permissions</b>: tick chọn <code>files.content.write</code>, <code>files.content.read</code>, <code>account_info.read</code> → Bấm <b>Submit</b>.<br>'
                                    '• Tab <b>Settings</b>: Bấm <b>Generate Access Token</b> hoặc copy <b>App Key</b> &amp; <b>App Secret</b> để dán vào đây.</div>'
                                )

                # --- panel chế độ xử lý (thẻ HTML + radio ẩn để giữ backend) ---
                with gr.Group(elem_classes=["mid-card", "mid-mode-card"]):
                    gr.HTML('<div class="mid-section-title">Chế độ xử lý</div>')
                    gr.HTML(MODE_CARDS_HTML)
                    mode = gr.Radio(
                        choices=[MODE_CHESS, MODE_CHESS_RU, MODE_CHESS_ES, MODE_GENERAL],
                        value=MODE_CHESS,
                        show_label=False,
                        elem_id="mid-mode-radio",
                        elem_classes="mid-hidden",
                    )

                # --- panel chất lượng + chuyển đổi ---
                with gr.Group(elem_classes=["mid-card", "mid-quality-card"]):
                    with gr.Row(elem_classes="mid-quality-head"):
                        gr.HTML('<div class="mid-section-title">Mức chất lượng</div>')
                        preset_hint = gr.HTML(
                            _PRESET_HINTS[PRESET_BALANCED], elem_id="mid-preset-hint"
                        )
                    preset = gr.Radio(
                        choices=[PRESET_SAVER, PRESET_BALANCED, PRESET_ACCURATE],
                        value=PRESET_BALANCED,
                        show_label=False,
                        elem_id="mid-preset",
                        elem_classes="mid-preset",
                    )
                    btn_file = gr.Button(
                        "Chuyển đổi", variant="primary", elem_id="mid-convert"
                    )
                    btn_stop = gr.Button(
                        "⏹ Dừng", variant="stop", visible=False, elem_id="mid-stop"
                    )

                    with gr.Accordion(
                        "Tùy chọn nâng cao", open=False, elem_classes="mid-adv"
                    ):
                        engine_select = gr.Radio(
                            choices=ENGINE_LABELS,
                            value=default_eng,
                            label="Công cụ AI (Engine)",
                            elem_classes="mid-engine-select",
                            info="Antigravity (mặc định) tối ưu cho Gemini Flash/Pro, bàn cờ & dịch thuật. Claude Code (phương án 2) dùng claude CLI.",
                        )

                        force_ocr = gr.Checkbox(
                            label="Buộc OCR toàn bộ", value=True,
                            info="Bỏ lớp text rác trong PDF scan, OCR lại bằng AI Engine.",
                            elem_classes="mid-toggle", container=False,
                        )
                        translate_vn = gr.Checkbox(
                            label="Dịch sang tiếng Việt", value=True,
                            info="Tạo thêm tệp _vn.md. Ký hiệu cờ → V/H/X/T/M.",
                            elem_classes="mid-toggle", container=False,
                        )
                        merge_ocr_translate = gr.Checkbox(
                            label="OCR + dịch gộp 1 bước", value=True,
                            info="Mỗi trang vừa OCR vừa dịch — tiết kiệm ~30–40% thời gian/quota.",
                            elem_classes="mid-toggle", container=False,
                        )
                        auto_download_on = gr.Checkbox(
                            label="Tự động tải về máy tính (Trình duyệt)", value=True,
                            info="Tự động tải các tệp kết quả (.md / .txt) về máy tính cá nhân qua trình duyệt khi xử lý xong.",
                            elem_classes="mid-toggle", container=False,
                        )
                        dropbox_sync_on = gr.Checkbox(
                            label="Tự động đồng bộ lên Dropbox", value=True,
                            info="Tự động tải tệp kết quả (.md / .txt) lên Dropbox để các phần mềm khác cùng sử dụng.",
                            elem_classes="mid-toggle", container=False,
                        )
                        autosave_on = gr.Checkbox(
                            label="Lưu bản sao trên máy chủ (VPS)", value=True,
                            info="Lưu trên ổ đĩa máy chủ/VPS cạnh file gốc hoặc thư mục chỉ định.",
                            elem_classes="mid-toggle", container=False,
                        )

                        gr.HTML('<div style="height:1px;background:var(--c-border);"></div>')

                        init_ocr_choices = ANTIGRAVITY_OCR_MODELS if default_eng == ENGINE_ANTIGRAVITY else CLAUDE_OCR_MODELS
                        init_tr_choices = ANTIGRAVITY_TRANSLATE_MODELS if default_eng == ENGINE_ANTIGRAVITY else CLAUDE_TRANSLATE_MODELS
                        init_ocr_val = "gemini-3.8-flash" if default_eng == ENGINE_ANTIGRAVITY else "sonnet"
                        init_tr_val = "gemini-3.8-flash" if default_eng == ENGINE_ANTIGRAVITY else "haiku"

                        with gr.Row(elem_classes="mid-selects"):
                            ocr_model = gr.Dropdown(
                                choices=init_ocr_choices,
                                value=init_ocr_val, label="Model OCR",
                                filterable=False, elem_classes="mid-select",
                            )
                            ocr_effort = gr.Dropdown(
                                choices=[("Thấp", "low"), ("Auto", "auto"),
                                         ("Trung bình", "medium"), ("Cao", "high")],
                                value="auto", label="Effort OCR",
                                filterable=False, elem_classes="mid-select",
                            )
                        with gr.Row(elem_classes="mid-selects"):
                            translate_model = gr.Dropdown(
                                choices=init_tr_choices,
                                value=init_tr_val, label="Model dịch",
                                filterable=False, elem_classes="mid-select",
                            )
                            translate_effort = gr.Dropdown(
                                choices=[("Thấp", "low"), ("Trung bình", "medium"),
                                         ("Cao", "high")],
                                value="low", label="Effort dịch",
                                filterable=False, elem_classes="mid-select",
                            )
                        with gr.Row(elem_classes="mid-selects"):
                            board_dpi = gr.Dropdown(
                                choices=[("250 — nhanh", "250"),
                                         ("400 — nét nhất", "400")],
                                value="250", label="DPI bàn cờ",
                                filterable=False, elem_classes="mid-select",
                            )
                            ocr_pages_per_call = gr.Dropdown(
                                choices=[("1 trang", "1"), ("2 trang", "2"),
                                         ("3 trang", "3")],
                                value="1", label="Trang / lần OCR",
                                filterable=False, elem_classes="mid-select",
                            )

                        gr.HTML('<div style="height:1px;background:var(--c-border);"></div>')

                        autosave_target = gr.Radio(
                            choices=[AUTOSAVE_SRC, AUTOSAVE_CUSTOM],
                            value=AUTOSAVE_SRC,
                            label="Nơi lưu .md trên VPS",
                            elem_classes="mid-autosave-target",
                            info=(
                                "'Cùng thư mục với file gốc' chỉ áp dụng cho tệp chọn "
                                "bằng nút 'Chọn tệp từ máy'; tệp kéo-thả lùi về thư mục "
                                "tùy chọn bên dưới."
                            ),
                        )
                        autosave_dir = gr.Textbox(
                            label="Thư mục tùy chọn trên VPS",
                            value=os.path.join(os.path.expanduser("~"), "Downloads"),
                            elem_classes="mid-autosave-dir",
                        )
                        enable_plugins = gr.Checkbox(value=False, visible=False)
                        use_ocr = gr.Checkbox(value=True, visible=False)

            # ============ CỘT PHẢI — xem trước / kết quả ============
            with gr.Column(elem_classes="mid-col-right"):
                with gr.Group(elem_classes=["mid-card", "mid-preview-card"]):
                    status = gr.Markdown(_STATUS_HINT, elem_id="mid-status")
                    with gr.Tabs():
                        with gr.Tab("Xem trước"):
                            preview = gr.Markdown(elem_id="mid-preview")
                        with gr.Tab("Mã .md"):
                            raw = gr.Code(
                                language="markdown", show_label=False,
                                elem_id="mid-raw",
                            )
                    downloads = gr.HTML(elem_id="mid-downloads")
                btn_clear = gr.Button(
                    "Xóa kết quả", variant="secondary", elem_classes="mid-clear-btn"
                )

        # Ghi nhớ lựa chọn giữa các lần mở (lưu vào localStorage trình duyệt).
        prefs = gr.BrowserState(
            {
                "preset": PRESET_BALANCED,
                "mode": MODE_CHESS,
                "dir": os.path.join(os.path.expanduser("~"), "Downloads"),
                "engine": default_eng,
                "api_key": "",
                "claude_token": "",
                "agy_token": "",
                "auto_download": True,
                "dropbox_token": "",
                "dropbox_app_key": "",
                "dropbox_app_secret": "",
                "dropbox_folder": "/MarkItDown",
                "dropbox_sync": True,
            }
        )

        # ---------------- wiring sự kiện ----------------
        outputs = [preview, raw, downloads, status]
        preset_outputs = [
            force_ocr, translate_vn, merge_ocr_translate, autosave_on, auto_download_on, dropbox_sync_on,
            ocr_model, ocr_effort, translate_model, translate_effort,
            board_dpi, ocr_pages_per_call, preset_hint,
        ]

        # Chọn preset / đổi chế độ / đổi engine -> tính lại tham số nâng cao.
        preset.change(_apply_preset, [preset, mode, engine_select], preset_outputs)
        mode.change(_apply_preset, [preset, mode, engine_select], preset_outputs)
        engine_select.change(_apply_preset, [preset, mode, engine_select], preset_outputs)

        # Khôi phục lựa chọn đã lưu khi tải trang -> đặt component -> tính lại
        demo.load(
            _load_prefs,
            prefs,
            [
                preset, mode, autosave_dir, engine_select,
                api_key_in, claude_token_in, agy_token_in, auto_download_on,
                dropbox_token_in, dropbox_app_key_in, dropbox_app_secret_in, dropbox_folder_in, dropbox_sync_on,
            ],
        ).then(
            _apply_preset, [preset, mode, engine_select], preset_outputs
        ).then(
            None, None, None,
            js="() => window.midSyncModeCards && window.midSyncModeCards()",
        )

        # Lưu lại mỗi khi đổi preset / chế độ / thư mục lưu / engine / api_key / claude_token / agy_token / auto_download / dropbox.
        for _comp in (
            preset, mode, autosave_dir, engine_select,
            api_key_in, claude_token_in, agy_token_in, auto_download_on,
            dropbox_token_in, dropbox_app_key_in, dropbox_app_secret_in, dropbox_folder_in, dropbox_sync_on,
        ):
            _comp.change(
                _save_prefs,
                [
                    preset, mode, autosave_dir, engine_select,
                    api_key_in, claude_token_in, agy_token_in, auto_download_on,
                    dropbox_token_in, dropbox_app_key_in, dropbox_app_secret_in, dropbox_folder_in, dropbox_sync_on,
                ],
                prefs,
            )

        # Kiểm tra kết nối Antigravity CLI
        def _on_test_agy(a_tok, c_tok, k_api):
            _ok, _msg, _lat = infrastructure.test_antigravity_cli_connection(a_tok)
            _html = infrastructure.render_infrastructure_html(api_key=k_api, claude_token=c_tok, agy_token=a_tok)
            return _msg, _html

        btn_test_agy.click(_on_test_agy, [agy_token_in, claude_token_in, api_key_in], [agy_test_status, infra_status_html])
        agy_token_in.change(lambda a, c, k: infrastructure.render_infrastructure_html(api_key=k, claude_token=c, agy_token=a), [agy_token_in, claude_token_in, api_key_in], infra_status_html)

        # Kiểm tra kết nối Claude Code CLI
        def _on_test_claude(c_tok, a_tok, k_api):
            _ok, _msg, _lat = infrastructure.test_claude_cli_connection(c_tok)
            _html = infrastructure.render_infrastructure_html(api_key=k_api, claude_token=c_tok, agy_token=a_tok)
            return _msg, _html

        btn_test_sub.click(_on_test_claude, [claude_token_in, agy_token_in, api_key_in], [sub_test_status, infra_status_html])
        claude_token_in.change(lambda c, a, k: infrastructure.render_infrastructure_html(api_key=k, claude_token=c, agy_token=a), [claude_token_in, agy_token_in, api_key_in], infra_status_html)

        # Đăng nhập Claude Code ngay trên giao diện (claude setup-token qua pipe, không cần SSH)
        def _on_claude_login_start():
            res = claude_login_bridge.start_claude_login()
            status, url, token, err, sid = (
                res.get("status"), res.get("url"), res.get("token"), res.get("error"), res.get("session_id", ""),
            )
            if status == "success" and token:
                return (
                    gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                    f"🎉 **Đăng nhập thành công!** Token đã tự điền vào ô Token Claude Code ở trên để dùng ngay.\n\n"
                    f"👉 **Để dùng vĩnh viễn**, copy chuỗi dưới đây và dán vào biến môi trường "
                    f"`CLAUDE_CODE_OAUTH_TOKEN` trong cấu hình Dokploy (Environment Variables) rồi redeploy:\n\n"
                    f"```\n{token}\n```",
                    sid, gr.update(value=token), gr.update(visible=False),
                )
            if status == "success" and not token:
                tail = "\n".join(res.get("tail", []))
                return (
                    gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                    f"⚠️ CLI báo thành công nhưng không tự nhận ra token trong output. "
                    f"Hãy tự copy dòng token (thường là dòng cuối, dài, không khoảng trắng) từ log dưới:\n\n```\n{tail}\n```",
                    sid, gr.update(), gr.update(visible=False),
                )
            if url:
                return (
                    gr.update(visible=True, value=f"🔗 Mở link này **trên máy của bạn** (không phải VPS) để đăng nhập:\n\n{url}"),
                    gr.update(visible=True, value=""),
                    gr.update(visible=True),
                    "⏳ Đăng nhập xong trên trình duyệt, nếu trang yêu cầu dán mã — dán vào ô trên rồi bấm Xác nhận.",
                    sid, gr.update(), gr.update(visible=True),
                )
            return (
                gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                f"❌ {err or 'Không khởi động được, thử lại.'}", sid, gr.update(), gr.update(visible=False),
            )

        btn_claude_login_start.click(
            _on_claude_login_start, None,
            [claude_login_url_md, claude_login_code_in, btn_claude_login_submit,
             claude_login_result_md, claude_login_session_state, claude_token_in, btn_claude_login_cancel],
        )

        def _on_claude_login_submit(code, sid):
            res = claude_login_bridge.submit_claude_login_code(code, session_id=sid)
            status, token, err = res.get("status"), res.get("token"), res.get("error")
            if status == "success" and token:
                return (
                    gr.update(visible=False), gr.update(visible=False),
                    f"🎉 Lấy token thành công! Đã tự điền vào ô Token ở trên.\n\n"
                    f"👉 Copy và dán vào `CLAUDE_CODE_OAUTH_TOKEN` trên Dokploy:\n\n```\n{token}\n```",
                    gr.update(value=token),
                )
            if status == "success" and not token:
                tail = "\n".join(res.get("tail", []))
                return (
                    gr.update(visible=False), gr.update(visible=False),
                    f"⚠️ Thành công nhưng không tự nhận ra token. Tự copy từ log dưới:\n\n```\n{tail}\n```",
                    gr.update(),
                )
            if status == "unknown":
                return (
                    gr.update(visible=True), gr.update(visible=True),
                    "⚠️ Chưa rõ kết quả (quá thời gian chờ) — có thể đã thành công. "
                    "Hãy bấm 'Kiểm tra kết nối Claude Code CLI' ở trên, hoặc thử lại.",
                    gr.update(),
                )
            return (
                gr.update(visible=False), gr.update(visible=False),
                f"❌ {err or 'Mã không hợp lệ hoặc đã hết hạn.'} Hãy bấm 'Đăng nhập Claude Code' để thử lại.",
                gr.update(),
            )

        btn_claude_login_submit.click(
            _on_claude_login_submit, [claude_login_code_in, claude_login_session_state],
            [claude_login_code_in, btn_claude_login_submit, claude_login_result_md, claude_token_in],
        ).then(
            lambda c, a, k: infrastructure.render_infrastructure_html(api_key=k, claude_token=c, agy_token=a),
            [claude_token_in, agy_token_in, api_key_in], infra_status_html,
        )

        def _on_claude_login_cancel():
            claude_login_bridge.cleanup_claude_login(force=True)
            return (
                gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                "⏹ Đã hủy phiên đăng nhập.",
            )

        btn_claude_login_cancel.click(
            _on_claude_login_cancel, None,
            [claude_login_url_md, claude_login_code_in, btn_claude_login_submit, claude_login_result_md],
        )

        # Kiểm tra kết nối API Key thời gian thực & cập nhật bảng trạng thái
        def _on_test_api(k, c_tok, a_tok):
            _ok, _msg, _lat = infrastructure.test_gemini_connection(k)
            _html = infrastructure.render_infrastructure_html(api_key=k, claude_token=c_tok, agy_token=a_tok)
            return _msg, _html

        btn_test_api.click(_on_test_api, [api_key_in, claude_token_in, agy_token_in], [api_test_status, infra_status_html])
        api_key_in.change(lambda k, c, a: infrastructure.render_infrastructure_html(api_key=k, claude_token=c, agy_token=a), [api_key_in, claude_token_in, agy_token_in], infra_status_html)

        # Kiểm tra kết nối Dropbox thời gian thực
        def _on_test_dropbox(tok, ak, as_):
            _ok, _msg, _lat = infrastructure.test_dropbox_connection(token=tok, refresh_token=tok, app_key=ak, app_secret=as_)
            return _msg

        btn_test_dropbox.click(_on_test_dropbox, [dropbox_token_in, dropbox_app_key_in, dropbox_app_secret_in], dropbox_test_status)

        # Mở hộp thoại Windows -> nạp đường dẫn thật vào State + hiển thị.
        btn_pick.click(on_pick_files, None, [picked_state, picked_view]).then(
            lambda p: gr.update(value=_convert_btn_label(len(p) if p else 0)),
            picked_state, btn_file,
        )
        file_in.change(_on_files_change, file_in, [picked_state, picked_view, btn_file])

        proc = btn_file.click(
            lambda: _set_running(True), None, [btn_file, btn_stop]
        ).then(
            on_convert_files,
            [
                file_in, mode, enable_plugins, use_ocr,
                ocr_model, ocr_effort, translate_model, translate_effort,
                force_ocr, board_dpi, translate_vn, merge_ocr_translate,
                ocr_pages_per_call, autosave_on, auto_download_on, autosave_dir,
                picked_state, autosave_target, engine_select,
                api_key_in, claude_token_in, agy_token_in,
                dropbox_sync_on, dropbox_folder_in,
                dropbox_token_in, dropbox_token_in, dropbox_app_key_in, dropbox_app_secret_in,
            ],
            outputs,
            show_progress="full",
        )
        proc.then(lambda: _set_running(False), None, [btn_file, btn_stop])

        ev_url = btn_url.click(
            lambda: _set_running(True), None, [btn_file, btn_stop]
        ).then(
            on_convert_url,
            [
                url_in, enable_plugins, auto_download_on,
                dropbox_sync_on, dropbox_folder_in,
                dropbox_token_in, dropbox_token_in, dropbox_app_key_in, dropbox_app_secret_in,
            ],
            outputs,
            show_progress="full",
        )
        ev_url.then(lambda: _set_running(False), None, [btn_file, btn_stop])
        ev_urls = url_in.submit(
            lambda: _set_running(True), None, [btn_file, btn_stop]
        ).then(
            on_convert_url,
            [
                url_in, enable_plugins, auto_download_on,
                dropbox_sync_on, dropbox_folder_in,
                dropbox_token_in, dropbox_token_in, dropbox_app_key_in, dropbox_app_secret_in,
            ],
            outputs,
            show_progress="full",
        )
        ev_urls.then(lambda: _set_running(False), None, [btn_file, btn_stop])

        btn_stop.click(
            lambda: _set_running(False), None, [btn_file, btn_stop],
            cancels=[proc, ev_url, ev_urls],
        )
        btn_clear.click(on_clear, None, outputs + [picked_state, picked_view])

    return demo


if __name__ == "__main__":
    server_name = os.environ.get("GRADIO_SERVER_NAME", "127.0.0.1" if sys.platform == "win32" and not os.environ.get("DOCKER") else "0.0.0.0")
    server_port = int(os.environ.get("PORT", os.environ.get("GRADIO_SERVER_PORT", "7860")))
    inbrowser = os.environ.get("GRADIO_INBROWSER", "true" if sys.platform == "win32" and not os.environ.get("DOCKER") else "false").lower() in ("1", "true", "yes")
    build_ui().launch(
        server_name=server_name,
        server_port=server_port,
        inbrowser=inbrowser,
        theme=THEME,
        css=CSS,
        head=HEAD,
        allowed_paths=[_OUTPUT_DIR, _ASSETS_DIR],
    )



