# -*- coding: utf-8 -*-
"""
Màn hình (GUI web) chạy MarkItDown bằng Gradio.

Cách chạy:
    .venv\\Scripts\\python.exe markitdown_gui.py
hoặc nhấp đúp run_gui.bat

Sau khi chạy, mở trình duyệt tại http://127.0.0.1:7860
"""

import os
import subprocess
import sys

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
import job_handlers
import job_view
import jobs
import review_handlers
from pipeline import (
    _OUTPUT_DIR,
    _chess_lang_from_mode,
    _effort_from_label,
    _is_chess_mode,
    _model_from_label,
    _publish_output,
    _translate_to_vn,
    AUTOSAVE_CUSTOM,
    AUTOSAVE_SRC,
    MODE_CHESS,
    MODE_CHESS_ES,
    MODE_CHESS_RU,
    MODE_GENERAL,
    convert_url,
)
from presets import (
    PRESET_ACCURATE,
    PRESET_BALANCED,
    PRESET_SAVER,
    _apply_preset,
    _load_prefs,
    _on_mode_change,
    preset_hint_text,
    _save_prefs,
)
from ui_render import _download_panel
from ui_theme import (
    _ASSETS_DIR,
    CSS,
    HEAD,
    MID_SETTINGS_HEAD_HTML,
    MODE_CARDS_HTML,
    THEME,
    TOPBAR_HTML,
)





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


def on_convert_url(
    url, enable_plugins, auto_download_on=True,
    dropbox_sync_on=False, dropbox_folder="/MarkItDown",
    dropbox_token="", dropbox_refresh_token="", dropbox_app_key="", dropbox_app_secret="",
    translate_vn=False, translate_model="gemini-3.8-flash", translate_effort="low", engine=ENGINE_ANTIGRAVITY,
    autosave_on=False, autosave_dir="", api_key="", claude_token="", agy_token="", mode_label=MODE_GENERAL,
):
    """Chuyển một URL sang Markdown. Ngang hàng với chuyển từ tệp: có tùy chọn dịch sang tiếng Việt và dùng chung
    `_publish_output` (thư mục tự lưu, Dropbox, tải về máy). Chạy ngay trong sự kiện, không qua công việc nền."""
    preview, raw_md, path, st = convert_url(url, enable_plugins)
    notes = [st] if st else []
    done = []
    if path:
        done.append(path)
        if translate_vn and (raw_md or "").strip():
            vn_path, vn_st = _translate_to_vn(
                raw_md, "ketqua_url.md", _model_from_label(translate_model), done,
                chess=_is_chess_mode(mode_label), chess_lang=_chess_lang_from_mode(mode_label),
                effort=_effort_from_label(translate_effort, default="low"), engine=engine,
                api_key=api_key or None, claude_token=claude_token or None, agy_token=agy_token or None,
            )
            notes.append(vn_st)
            if vn_path:
                done.append(vn_path)
        cfg = dict(
            folder=dropbox_folder, token=dropbox_token, refresh_token=dropbox_refresh_token,
            app_key=dropbox_app_key, app_secret=dropbox_app_secret,
        )
        for k, p in enumerate(done):
            notes.append(f"`{os.path.basename(p)}`" + _publish_output(
                p, autosave_dir, dropbox_cfg=cfg, inline=k > 0, autosave_on=bool(autosave_on),
                dropbox_sync_on=bool(dropbox_sync_on), auto_download_on=bool(auto_download_on),
            ))
    kind = "ok" if path else "warn"
    return preview, raw_md, _download_panel(done, auto_download=auto_download_on), job_view.message_html("\n".join(notes), kind)


def on_clear():
    # Xoá kết quả hiển thị + danh sách tệp đã chọn bằng hộp thoại + liên kết tới công việc hiện tại.
    # (Công việc vẫn nằm trong tab Lịch sử; muốn dừng việc đang chạy thì bấm Dừng.)
    return (
        "", "", "", job_view.idle_html(), [], "", "", "",
        gr.update(visible=False), job_view.flag_html(None), gr.update(visible=False),
    )


def _convert_btn_label(n):
    return f"Chuyển đổi {n} tệp" if n else "Chuyển đổi"


def _convert_btn_update(n):
    """Nhãn "Chuyển đổi N tệp"; vô hiệu khi chưa có tệp (thiết kế: không có tệp thì không bấm được)."""
    return gr.update(value=_convert_btn_label(n), interactive=bool(n))


def _set_running(running):
    """Đang chạy -> ẩn nút Chuyển đổi, hiện nút Dừng (và ngược lại khi xong)."""
    return gr.update(visible=not running), gr.update(visible=running)


def _buttons_after_stop(job_id):
    """Sau khi bấm Dừng: công việc còn đang dừng dở thì giữ nút Dừng, ngược lại về nút Chuyển đổi."""
    job = jobs.get_manager().get(job_id) if job_id else None
    active = bool(job and job["status"] in job_view.ACTIVE)
    return gr.update(visible=not active), gr.update(visible=active)


def _on_files_change(files):
    """Kéo-thả tệp mới -> xoá lựa chọn từ hộp thoại + cập nhật nhãn nút."""
    n = len(files) if files else 0
    return [], "", _convert_btn_update(n)


def build_ui():
    default_eng = get_default_engine()

    with gr.Blocks(title="MarkItDown") as demo:
        # ---- thanh tiêu đề navy (sticky) ----
        gr.HTML(TOPBAR_HTML)

        with gr.Row(elem_id="mid-workspace"):
            # ============ CỘT TRÁI — nhập liệu & điều khiển ============
            with gr.Column(elem_classes="mid-col-left"):

                # --- panel nhập liệu ---
                with gr.Column(elem_classes=["mid-card", "mid-input-card"]):
                    with gr.Tabs(elem_classes="mid-input-tabs"):
                        with gr.Tab("Từ tệp"):
                            file_in = gr.File(
                                show_label=False,
                                type="filepath",
                                file_count="multiple",
                                height=130,
                                elem_id="mid-file",
                            )
                            # Hàng đợi tệp tự vẽ (tên, loại, dung lượng, số trang, nút ×). Hộp thoại Gradio gốc bị ẩn bằng CSS;
                            # nút × / Xóa hết / Thêm tệp được JS bắc cầu sang các nút gốc của gr.File.
                            queue_view = gr.HTML(elem_id="mid-queue")
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
                # --- panel chế độ xử lý (thẻ HTML + radio ẩn để giữ backend) ---
                with gr.Column(elem_classes=["mid-card", "mid-mode-card"]):
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
                with gr.Column(elem_classes=["mid-card", "mid-quality-card"]):
                    with gr.Row(elem_classes="mid-quality-head"):
                        gr.HTML('<div class="mid-section-title">Mức chất lượng</div>')
                        preset_hint = gr.HTML(
                            preset_hint_text(PRESET_BALANCED, default_eng), elem_id="mid-preset-hint"
                        )
                    preset = gr.Radio(
                        choices=[PRESET_SAVER, PRESET_BALANCED, PRESET_ACCURATE],
                        value=PRESET_BALANCED,
                        show_label=False,
                        elem_id="mid-preset",
                        elem_classes="mid-preset",
                    )
                    # Thanh hành động: trên di động (<780 px) CSS ghim nó xuống đáy màn hình (G1.7)
                    with gr.Column(elem_id="mid-actionbar"):
                        btn_file = gr.Button(
                            "Chuyển đổi", variant="primary", elem_id="mid-convert", interactive=False
                        )
                        btn_stop = gr.Button(
                            "⏹ Dừng", variant="stop", visible=False, elem_id="mid-stop"
                        )
                        btn_resume = gr.Button(
                            "▶ Chạy tiếp", variant="secondary", visible=False, elem_id="mid-resume"
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

                        page_spec = gr.Textbox(
                            label="Trang cần làm",
                            placeholder="Để trống = tất cả. Ví dụ: 1-5, 20, 31-40",
                            info="Chỉ OCR các trang này của PDF (đếm từ 1). Kết quả chỉ gồm các trang đã chọn.",
                            elem_id="mid-pages", elem_classes="mid-select",
                        )
                        page_estimate = gr.Markdown(elem_id="mid-page-estimate")

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
                with gr.Column(elem_classes=["mid-card", "mid-preview-card"]):
                    status = gr.HTML(job_view.idle_html(), elem_id="mid-status")
                    # Chọn xem từng tệp (chỉ hiện khi có ≥2 tệp đã xong)
                    file_pick = gr.Radio(
                        choices=[], value=None, visible=False, show_label=False, elem_id="mid-file-pick",
                        elem_classes="mid-chips",
                    )
                    with gr.Tabs(elem_classes="mid-result-tabs"):
                        with gr.Tab("Xem trước"):
                            preview = gr.Markdown(elem_id="mid-preview")
                        with gr.Tab("Mã .md"):
                            gr.HTML(
                                '<div class="mid-rawbar"><button type="button" class="mid-copy-btn" data-mid-action="copy-raw">'
                                '<span data-mid-copy-label>Sao chép Markdown</span></button></div>'
                            )
                            raw = gr.Code(
                                language="markdown", show_label=False,
                                elem_id="mid-raw",
                            )
                        with gr.Tab("♟ Thế cờ") as fen_tab:
                            fen_info = gr.HTML()
                            fen_table = gr.Dataframe(
                                headers=["#", "Trang", "FEN", "Trạng thái"], datatype=["number", "str", "str", "str"],
                                column_widths=["9%", "11%", "62%", "18%"],
                                interactive=False, wrap=True, show_label=False, max_height=230,
                                elem_id="mid-fen-table",
                            )
                            with gr.Row(elem_classes="mid-fen-nav"):
                                btn_fen_prev = gr.Button("◀", size="sm", elem_classes="mid-fen-step")
                                # không đặt minimum: ô rỗng/0 làm Gradio ném lỗi trước khi vào handler; handler tự kẹp giá trị
                                fen_idx = gr.Number(label="Thế cờ số", value=1, precision=0, elem_id="mid-fen-idx")
                                btn_fen_next = gr.Button("▶", size="sm", elem_classes="mid-fen-step")
                            with gr.Row(elem_classes="mid-fen-edit"):
                                fen_preview = gr.HTML(elem_id="mid-fen-preview")
                                with gr.Column(elem_classes="mid-fen-form"):
                                    fen_text = gr.Textbox(label="FEN (sửa được)", lines=2, max_lines=3, elem_id="mid-fen-text")
                                    fen_link = gr.HTML()
                                    with gr.Row():
                                        btn_fen_flip = gr.Button("↻ Lật bàn 180°", elem_classes="mid-fen-btn")
                                        btn_fen_apply = gr.Button("💾 Áp dụng", variant="primary", elem_classes="mid-fen-btn")
                            fen_msg = gr.HTML()
                        with gr.Tab("🔍 Đối chiếu trang") as cmp_tab:
                            cmp_info = gr.HTML()
                            with gr.Row(elem_classes="mid-cmp-nav"):
                                cmp_filter = gr.Radio(
                                    choices=review_handlers.CMP_FILTERS, value=review_handlers.CMP_FILTERS[0],
                                    show_label=False, elem_id="mid-cmp-filter", elem_classes="mid-chips",
                                )
                            with gr.Row(elem_classes="mid-fen-nav"):
                                btn_cmp_prev = gr.Button("◀", size="sm", elem_classes="mid-fen-step")
                                cmp_page = gr.Number(label="Trang", value=None, precision=0, elem_id="mid-cmp-page")
                                btn_cmp_next = gr.Button("▶", size="sm", elem_classes="mid-fen-step")
                            with gr.Row(elem_classes="mid-cmp-row"):
                                cmp_img = gr.HTML(elem_id="mid-cmp-img")
                                cmp_md = gr.Markdown(elem_id="mid-cmp-md")
                        with gr.Tab("🕘 Lịch sử") as history_tab:
                            history_usage = gr.Markdown()
                            history_pick = gr.Dropdown(
                                choices=[], value=None, label="Công việc đã chạy",
                                filterable=False, elem_id="mid-history-pick",
                            )
                            with gr.Row():
                                btn_hist_open = gr.Button("Mở kết quả", variant="primary", elem_id="mid-hist-open")
                                btn_hist_refresh = gr.Button("Làm mới", variant="secondary", elem_id="mid-hist-refresh")
                                btn_hist_delete = gr.Button("Xóa", variant="stop", elem_id="mid-hist-delete")
                    downloads = gr.HTML(elem_id="mid-downloads")
                    job_flag = gr.HTML(job_view.flag_html(None), elem_id="mid-job-flag-wrap")
                btn_clear = gr.Button(
                    "Xóa kết quả", variant="secondary", elem_classes="mid-clear-btn"
                )
                # Nút ẩn: JS bấm hộ khi người dùng bấm "Chạy lại" trong danh sách tải về
                btn_rerun = gr.Button("Chạy lại", elem_id="mid-rerun", elem_classes="mid-hidden")

        # ============ TRANG CÀI ĐẶT (toàn chiều rộng; bật/tắt bằng nút bánh răng ở thanh tiêu đề, JS) ============
        with gr.Column(elem_id="mid-settings"):
            gr.HTML(MID_SETTINGS_HEAD_HTML)
            infra_status_html = gr.HTML(
                infrastructure.render_infrastructure_html(),
                elem_id="mid-infra-status",
            )
            with gr.Row(elem_classes="mid-set-grid"):
                with gr.Column(elem_classes=["mid-card", "mid-set-card"]):
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
                    with gr.Accordion("Hướng dẫn chi tiết", open=False, elem_classes="mid-set-guide"):
                        gr.HTML(
                            '<div style="margin-top:8px;padding:10px 14px;border-radius:8px;'
                            'background:rgba(31,169,143,0.06);border:1px solid rgba(31,169,143,0.18);'
                            'font-size:12.5px;color:var(--c-text);line-height:1.6;">'
                            '⚡ <b>Cách lấy Token Antigravity từ máy tính để dùng trên VPS:</b><br>'
                            '• Mở tệp: <code>C:\\Users\\&lt;tên_bạn&gt;\\.gemini\\antigravity-cli\\antigravity-oauth-token</code> (hoặc <code>oauth_creds.json</code>).<br>'
                            '• Copy toàn bộ nội dung trong tệp và dán vào ô trên → bấm <b>Kiểm tra kết nối Antigravity CLI</b>.<br>'
                            '• Hệ thống sẽ tự động lưu và kết nối phiên Google Antigravity của bạn vĩnh viễn trên VPS!</div>'
                        )
    
    
                with gr.Column(elem_classes=["mid-card", "mid-set-card"]):
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
                    with gr.Accordion("Hướng dẫn chi tiết", open=False, elem_classes="mid-set-guide"):
                        gr.HTML(
                            '<div style="margin-top:8px;padding:10px 14px;border-radius:8px;'
                            'background:rgba(43,57,144,0.06);border:1px solid rgba(43,57,144,0.18);'
                            'font-size:12.5px;color:var(--c-text);line-height:1.6;">'
                            '🟣 <b>Cách lấy Claude Code OAuth Token (hạn dùng ~1 năm):</b><br>'
                            '• Trên máy có cài Claude Code CLI (hoặc SSH vào server), chạy lệnh <code>claude setup-token</code>.<br>'
                            '• Mở URL hiện ra trên trình duyệt của bạn, đăng nhập bằng tài khoản Claude Pro/Max, dán mã xác nhận ngược lại terminal nếu được hỏi.<br>'
                            '• Copy token được in ra, dán vào ô trên và bấm <b>Kiểm tra kết nối Claude Code CLI</b>.</div>'
                        )
    
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
    
    
            with gr.Row(elem_classes="mid-set-grid"):
                with gr.Column(elem_classes=["mid-card", "mid-set-card"]):
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
    
                with gr.Column(elem_classes=["mid-card", "mid-set-card"]):
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
                    with gr.Accordion("Hướng dẫn chi tiết", open=False, elem_classes="mid-set-guide"):
                        gr.HTML(
                            '<div style="margin-top:6px;padding:8px 12px;border-radius:8px;'
                            'background:rgba(0,97,254,0.06);border:1px solid rgba(0,97,254,0.2);'
                            'font-size:12.5px;color:var(--c-text);line-height:1.6;">'
                            '☁️ <b>Cách lấy Token Dropbox (1 phút):</b><br>'
                            '• Truy cập <a href="https://www.dropbox.com/developers/apps" target="_blank" style="color:#0061FE;font-weight:700;text-decoration:underline;">Dropbox App Console</a> → Tạo App (chọn <b>Scoped Access</b> → <b>Full Dropbox</b> hoặc <b>App Folder</b>).<br>'
                            '• Tab <b>Permissions</b>: tick chọn <code>files.content.write</code>, <code>files.content.read</code>, <code>account_info.read</code> → Bấm <b>Submit</b>.<br>'
                            '• Tab <b>Settings</b>: Bấm <b>Generate Access Token</b> hoặc copy <b>App Key</b> &amp; <b>App Secret</b> để dán vào đây.</div>'
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
                "translate_vn": True,
                "autosave_on": True,
            }
        )

        # ---------------- wiring sự kiện ----------------
        outputs = [preview, raw, downloads, status]
        # Preset chỉ đặt model/effort/DPI/trang-mỗi-lần/gộp (không đụng công tắc dịch/tự lưu/tự tải/Dropbox của người dùng).
        preset_outputs = [
            merge_ocr_translate, ocr_model, ocr_effort, translate_model, translate_effort,
            board_dpi, ocr_pages_per_call, preset_hint,
        ]

        # Chọn preset / đổi engine -> tính lại tham số nâng cao; đổi chế độ -> chỉ đặt lại "Buộc OCR".
        preset.change(_apply_preset, [preset, engine_select], preset_outputs)
        engine_select.change(_apply_preset, [preset, engine_select], preset_outputs)
        mode.change(_on_mode_change, mode, force_ocr)

        # Khôi phục lựa chọn đã lưu khi tải trang -> đặt component -> tính lại
        demo.load(
            _load_prefs,
            prefs,
            [
                preset, mode, autosave_dir, engine_select,
                api_key_in, claude_token_in, agy_token_in, auto_download_on,
                dropbox_token_in, dropbox_app_key_in, dropbox_app_secret_in, dropbox_folder_in, dropbox_sync_on,
                translate_vn, autosave_on,
            ],
        ).then(
            _apply_preset, [preset, engine_select], preset_outputs
        ).then(
            _on_mode_change, mode, force_ocr
        ).then(
            None, None, None,
            js="() => window.midSyncModeCards && window.midSyncModeCards()",
        )

        # Lưu lại mỗi khi đổi preset / chế độ / thư mục lưu / engine / api_key / claude_token / agy_token / auto_download / dropbox.
        for _comp in (
            preset, mode, autosave_dir, engine_select,
            api_key_in, claude_token_in, agy_token_in, auto_download_on,
            dropbox_token_in, dropbox_app_key_in, dropbox_app_secret_in, dropbox_folder_in, dropbox_sync_on,
            translate_vn, autosave_on,
        ):
            _comp.change(
                _save_prefs,
                [
                    preset, mode, autosave_dir, engine_select,
                    api_key_in, claude_token_in, agy_token_in, auto_download_on,
                    dropbox_token_in, dropbox_app_key_in, dropbox_app_secret_in, dropbox_folder_in, dropbox_sync_on,
                    translate_vn, autosave_on,
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
            lambda p: _convert_btn_update(len(p) if p else 0),
            picked_state, btn_file,
        ).then(
            job_handlers.on_estimate, [file_in, picked_state, page_spec, ocr_pages_per_call], page_estimate,
            show_progress="hidden",
        ).then(
            job_handlers.on_queue, [file_in, picked_state], queue_view, show_progress="hidden",
        )
        file_in.change(_on_files_change, file_in, [picked_state, picked_view, btn_file]).then(
            job_handlers.on_queue, [file_in, picked_state], queue_view, show_progress="hidden",
        )

        # ---------------- công việc nền (jobs.py) ----------------
        # Bấm Chuyển đổi chỉ TẠO công việc; giao diện hỏi trạng thái mỗi vài giây (gr.Timer, chỉ bật khi có việc đang chạy).
        # job_state nhớ mã công việc trong trình duyệt -> mở lại trang tự gắn vào việc đang chạy.
        # secret cố định: mặc định Gradio mã hóa bằng khóa ngẫu nhiên MỖI LẦN app khởi động, nên sau khi redeploy trình duyệt
        # không đọc lại được mã công việc. Mã công việc không phải bí mật (nó chỉ là một chuỗi ngẫu nhiên khó đoán).
        job_state = gr.BrowserState("", storage_key="markitdown_active_job", secret="markitdown-job-state-v1")
        sig_state = gr.State("")
        job_timer = gr.Timer(job_handlers.TICK_SECONDS, active=False)
        job_outputs = [
            status, preview, raw, downloads, sig_state, job_timer,
            btn_file, btn_stop, btn_resume, job_flag, file_pick,
        ]
        creds_inputs = [
            api_key_in, claude_token_in, agy_token_in,
            dropbox_token_in, dropbox_token_in, dropbox_app_key_in, dropbox_app_secret_in,
        ]

        btn_file.click(
            job_handlers.on_start_job,
            [
                file_in, mode, enable_plugins, use_ocr,
                ocr_model, ocr_effort, translate_model, translate_effort,
                force_ocr, board_dpi, translate_vn, merge_ocr_translate,
                ocr_pages_per_call, autosave_on, auto_download_on, autosave_dir,
                picked_state, autosave_target, engine_select,
                api_key_in, claude_token_in, agy_token_in,
                dropbox_sync_on, dropbox_folder_in,
                dropbox_token_in, dropbox_token_in, dropbox_app_key_in, dropbox_app_secret_in,
                page_spec,
            ],
            [job_state] + job_outputs,
            show_progress="hidden",
        )
        job_timer.tick(job_handlers.on_tick, [job_state, sig_state, file_pick], job_outputs, show_progress="hidden")
        file_pick.input(job_handlers.on_tick, [job_state, sig_state, file_pick], job_outputs, show_progress="hidden")
        btn_rerun.click(
            job_handlers.on_rerun_job, [job_state] + creds_inputs, [job_state] + job_outputs, show_progress="hidden",
        )
        demo.load(job_handlers.on_reattach, job_state, job_outputs, show_progress="hidden")
        btn_resume.click(
            job_handlers.on_resume_job, [job_state] + creds_inputs, job_outputs, show_progress="hidden",
        )

        # ---------------- hiệu đính: bảng thế cờ (G3.1) và đối chiếu trang (G3.2) ----------------
        fen_outputs = [fen_info, fen_table, fen_idx, fen_text, fen_preview, fen_link, fen_msg]
        fen_ctx = [job_state, file_pick]
        fen_tab.select(review_handlers.fen_refresh, fen_ctx, fen_outputs, show_progress="hidden")
        fen_table.select(review_handlers.fen_select, fen_ctx, fen_outputs, show_progress="hidden")
        fen_idx.submit(review_handlers.fen_goto, fen_ctx + [fen_idx], fen_outputs, show_progress="hidden")
        fen_idx.blur(review_handlers.fen_goto, fen_ctx + [fen_idx], fen_outputs, show_progress="hidden")
        btn_fen_prev.click(
            lambda j, s, n: review_handlers.fen_step(j, s, n, -1), fen_ctx + [fen_idx], fen_outputs, show_progress="hidden",
        )
        btn_fen_next.click(
            lambda j, s, n: review_handlers.fen_step(j, s, n, 1), fen_ctx + [fen_idx], fen_outputs, show_progress="hidden",
        )
        fen_text.input(review_handlers.fen_preview, fen_text, [fen_preview, fen_link], show_progress="hidden")
        btn_fen_flip.click(review_handlers.fen_flip, fen_text, [fen_text, fen_preview, fen_link], show_progress="hidden")
        btn_fen_apply.click(
            review_handlers.fen_apply, fen_ctx + [fen_idx, fen_text], fen_outputs, show_progress="hidden",
        ).then(
            # tệp kết quả đã đổi trên đĩa -> vẽ lại Xem trước / Mã .md / danh sách tải về (chữ ký rỗng = buộc vẽ lại)
            lambda j, s, sel: job_handlers.render_job(j, "", True, sel), [job_state, sig_state, file_pick], job_outputs,
            show_progress="hidden",
        )

        cmp_outputs = [cmp_page, cmp_img, cmp_md, cmp_info]
        cmp_ctx = [job_state, file_pick, cmp_filter, cmp_page]
        cmp_tab.select(review_handlers.cmp_load, cmp_ctx, cmp_outputs, show_progress="hidden")
        cmp_filter.change(review_handlers.cmp_load, cmp_ctx, cmp_outputs, show_progress="hidden")
        cmp_page.submit(review_handlers.cmp_load, cmp_ctx, cmp_outputs, show_progress="hidden")
        btn_cmp_prev.click(
            lambda j, s, f, p: review_handlers.cmp_step(j, s, f, p, -1), cmp_ctx, cmp_outputs, show_progress="hidden",
        )
        btn_cmp_next.click(
            lambda j, s, f, p: review_handlers.cmp_step(j, s, f, p, 1), cmp_ctx, cmp_outputs, show_progress="hidden",
        )

        # Lịch sử công việc
        history_outputs = [history_pick, history_usage]
        demo.load(job_handlers.history_refresh, None, history_outputs)
        history_tab.select(job_handlers.history_refresh, None, history_outputs)
        btn_hist_refresh.click(job_handlers.history_refresh, None, history_outputs)
        btn_hist_open.click(job_handlers.history_open, history_pick, [job_state] + job_outputs)
        btn_hist_delete.click(
            job_handlers.history_delete, [history_pick, job_state], history_outputs + [job_state],
        )

        # Ước lượng "N trang → M lượt gọi OCR" khi đổi tệp / khoảng trang / số trang mỗi lần
        estimate_inputs = [file_in, picked_state, page_spec, ocr_pages_per_call]
        for _c in (file_in, page_spec, ocr_pages_per_call):
            _c.change(
                job_handlers.on_estimate, estimate_inputs, page_estimate,
                show_progress="hidden", trigger_mode="always_last",
            )

        # Chuyển từ URL: nhanh, chạy ngay trong sự kiện (không qua công việc nền)
        ev_url = btn_url.click(
            lambda: _set_running(True), None, [btn_file, btn_stop]
        ).then(
            on_convert_url,
            [
                url_in, enable_plugins, auto_download_on,
                dropbox_sync_on, dropbox_folder_in,
                dropbox_token_in, dropbox_token_in, dropbox_app_key_in, dropbox_app_secret_in,
                translate_vn, translate_model, translate_effort, engine_select,
                autosave_on, autosave_dir, api_key_in, claude_token_in, agy_token_in, mode,
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
                translate_vn, translate_model, translate_effort, engine_select,
                autosave_on, autosave_dir, api_key_in, claude_token_in, agy_token_in, mode,
            ],
            outputs,
            show_progress="full",
        )
        ev_urls.then(lambda: _set_running(False), None, [btn_file, btn_stop])

        # Dừng: diệt tiến trình AI của công việc nền (thật) và hủy các sự kiện URL đang chạy.
        btn_stop.click(
            job_handlers.on_stop_job, job_state, status, cancels=[ev_url, ev_urls],
        ).then(_buttons_after_stop, job_state, [btn_file, btn_stop])
        btn_clear.click(
            on_clear, None,
            outputs + [picked_state, picked_view, job_state, sig_state, btn_resume, job_flag, file_pick],
        )

    return demo


def _auth_from_env(env=None):
    """Đọc MID_AUTH_USER / MID_AUTH_PASS -> (user, pass) hoặc None (không bật đăng nhập).

    Cả hai biến cùng có giá trị mới bật. Chỉ đặt một trong hai là cấu hình sai: ném ValueError
    thay vì lặng lẽ chạy không khóa (an toàn hơn cho một ứng dụng mở ra Internet).
    """
    env = os.environ if env is None else env
    user = (env.get("MID_AUTH_USER") or "").strip()
    pw = env.get("MID_AUTH_PASS") or ""
    if not user and not pw:
        return None
    if not user or not pw:
        raise ValueError(
            "Chỉ đặt một trong hai biến MID_AUTH_USER / MID_AUTH_PASS. "
            "Hãy đặt cả hai để bật đăng nhập, hoặc bỏ cả hai để tắt."
        )
    return (user, pw)


if __name__ == "__main__":
    server_name = os.environ.get("GRADIO_SERVER_NAME", "127.0.0.1" if sys.platform == "win32" and not os.environ.get("DOCKER") else "0.0.0.0")
    server_port = int(os.environ.get("PORT", os.environ.get("GRADIO_SERVER_PORT", "7860")))
    inbrowser = os.environ.get("GRADIO_INBROWSER", "true" if sys.platform == "win32" and not os.environ.get("DOCKER") else "false").lower() in ("1", "true", "yes")
    try:
        auth = _auth_from_env()
    except ValueError as exc:
        sys.exit(f"❌ {exc}")
    build_ui().launch(
        server_name=server_name,
        server_port=server_port,
        inbrowser=inbrowser,
        theme=THEME,
        css=CSS,
        head=HEAD,
        allowed_paths=[_OUTPUT_DIR, _ASSETS_DIR, jobs.data_dir()],  # thư mục dữ liệu: để tải được tệp kết quả của công việc nền
        auth=auth,
        auth_message="Đăng nhập để dùng MarkItDown — Cờ vua Dương Sinh." if auth else None,
    )
