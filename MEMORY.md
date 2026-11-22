# MEMORY — Bộ nhớ dự án (sự thật bền vững cho các phiên sau)

> Mô tả mã nguồn tại commit `2c1df67b44` (2026-09-27); cập nhật lần cuối 2026-11-21.
> Đây là tệp **được commit cùng repo**, khác với bộ nhớ riêng của công cụ AI (nằm ngoài repo). Mục đích: để người hoặc AI mở phiên mới không
> phải khám phá lại. Chỉ ghi điều **không suy ra được từ mã/git**. Nhật ký từng phiên: `docs/LICH-SU-PHAT-TRIEN.md` mục 4.
> Quy tắc: mỗi dòng một sự kiện, kèm ngày; sự kiện sai thì **sửa hoặc xóa**, đừng để mâu thuẫn.

## 1. Chủ dự án và cách làm việc

- Chủ dự án: **Cờ vua Dương Sinh** (tài khoản git `covuaduongsinh`). Môi trường: Windows 10, PowerShell + Git Bash, Python 3.12 trong `.venv`.
- **Giao tiếp bằng tiếng Việt** ở mọi dự án (đã yêu cầu nhiều lần; ghi ở cấu hình cá nhân của chủ dự án). Mã, đường dẫn, lệnh giữ tiếng Anh. (2026-09-30)
- Chủ dự án muốn **tài liệu nằm ngay trong repo** (`AGENTS.md`, `CLAUDE.md`, `README.md`, `SKILLS.md`, `TECH.md`, `MEMORY.md`, `docs/`) để làm
  cơ sở rà soát, xây module mới và **nhân bản phần mềm**. (2026-09-30) Vì vậy bộ tài liệu này **không** đặt ở repo riêng như quy trình mặc định của skill `document-repo`.
- Chủ dự án dùng **gói thuê bao** (Google Antigravity, Claude) thay khoá API; dùng CLI chính chủ. Đừng đề xuất chuyển sang khoá API mà không nêu lý do chi phí.

## 2. Trạng thái dự án

- Web production: `https://markitdown.dsc.edu.vn` (Docker → Dokploy, VPS). Đang chạy commit `d72cc40` (mặc định `gemini-3.8-flash`, đã mount `/root/.gemini`). (2026-11-21)
- Tính năng mới nhất: Dropbox sync (`2c1df67`, 2026-09-27). Kế hoạch trước đó: Trung tâm cài đặt hạ tầng (2026-09-17).
- Bộ tài liệu 2026-09-30: xem `docs/README.md`. S10 đã sửa 2026-10-13 (xem bên dưới); các mục khác trong `docs/RA-SOAT-RUI-RO.md` chưa sửa.
- **2026-11-22: G0 đã merge `main` (fast-forward, `985e82b`, đã push; auto deploy Dokploy đang TẮT nên chưa lên production). Giai đoạn 2 (công việc nền) G2.1–G2.8 xong trên nhánh `feat/nang-cap-giao-dien`**: `jobs.py`, `proc_control.py`, `job_handlers.py`, `job_view.py`, tab Lịch sử, ô "Trang cần làm". **G2.9 (volume `/data` trên Dokploy) CHƯA làm** — cần chủ dự án duyệt và cho phép lên production; các bước ở `docs/tinh-nang/10-…`. Tài liệu: `docs/tinh-nang/13-cong-viec-nen.md`.
- Cây làm việc sạch; bộ tài liệu và kế hoạch đồng bộ đã được commit vào `main` ngày 2026-11-21.
- **2026-11-21: Giai đoạn 0 của kế hoạch nâng cấp giao diện đã xong trên nhánh `feat/nang-cap-giao-dien`** (chưa push/merge; `main` và production vẫn ở `d72cc40`). Gradio ghim 6.32.0 (`requirements-gui.txt`), engine giả `MID_FAKE_ENGINE=1`, `markitdown_gui.py` tách thành `pipeline.py`/`ui_theme.py`/`presets.py`/`ui_render.py` + `assets/ui/app.{css,js}`, đăng nhập web `MID_AUTH_USER`/`MID_AUTH_PASS` (mặc định tắt), `tests_gui/` 29 test. Kế hoạch: `docs/plans/2026-11-21-nang-cap-giao-dien-va-tinh-nang.md` (bảng Tiến độ ở cuối). Giai đoạn kế: G1 (giao diện) hoặc G2 (công việc nền) — G2.9 (volume `/data`) chỉ làm khi chủ dự án duyệt nhánh.
- 2026-11-21: Đồng bộ upstream `microsoft/markitdown` từ commit `945314a` lên `ed17895` (v0.1.9, 23 commit mới). Upstream nâng cấp DocIntel, sửa ExifTool Windows, nâng phụ thuộc và tái cấu trúc test suite. Test fork và upstream import đều đạt 100%.
- 2026-10-13: thêm `claude_login_bridge.py` (nút "Đăng nhập Claude Code" trên web, dùng `claude setup-token`)
  và sửa `_claude_env`/`infrastructure.py` dùng đúng biến `CLAUDE_CODE_OAUTH_TOKEN` thay vì 3 biến sai cũ
  (`CLAUDE_CODE_SESSION_ACCESS_TOKEN`, `ANTHROPIC_SESSION_KEY`, `ANTHROPIC_API_KEY`). Xem
  `docs/tinh-nang/12-dang-nhap-claude-code.md`. **Chưa thử thật trên VPS** — phần parse output của
  `claude setup-token` dựa trên tài liệu chính thức + CLI giả lập, chưa chạy với CLI thật.

## 3. Điều đã học được (bẫy và sự thật kỹ thuật)

| Ngày | Sự kiện | Hệ quả |
|---|---|---|
| 2026-09-30 | Mô hình ONNX nhận diện bàn cờ **không nằm trong repo**; `chessboard_fen.DEFAULT_MODELS_DIR` trỏ vào thư mục cá nhân ngoài repo | Trên VPS mặc định không có FEN cục bộ; nhân bản phải mang mô hình theo |
| 2026-09-30 | `DROPBOX_TARGET_FOLDER` có trong tài liệu nhưng **không có trong mã** | Đừng tin tài liệu cũ; thư mục Dropbox lấy từ ô giao diện |
| 2026-09-30 | `enable_plugins=False` cố định ở GUI → `markitdown-ocr` không chạy trong app dù Dockerfile cài | Hai hệ OCR độc lập |
| 2026-09-30 | `python` trên PATH của máy dev là 3.8.10; venv là 3.12 | Luôn dùng `.venv\Scripts\python.exe` |
| 2026-09-30 | Console Windows `cp1252`: `print()` tiếng Việt ném `UnicodeEncodeError` | Ghi ra tệp UTF-8 hoặc `PYTHONUTF8=1` |
| 2026-09-30 | Số dòng cuối do công cụ Read hiển thị có thể lệch 1 | Lấy số dòng bằng `wc -l`/script |
| (trích từ mã) | `gemini-3.1-pro` trên `agy` chỉ có effort `high`/`low`, không có `medium` | Preset Chính xác đặt `medium` cho dịch có thể không đúng ý (ghi ở `GUI_README.md`) |
| (trích từ mã) | Chú thích `_claude_fast_flags`: `effortLevel: xhigh` trong cài đặt người dùng khiến Claude "nghĩ" hàng chục nghìn token mỗi trang | Luôn truyền `--effort` cho `claude -p` |
| 2026-10-13 | Tài liệu chính thức Claude Code CLI: `ANTHROPIC_API_KEY` có độ ưu tiên xác thực **cao hơn** `CLAUDE_CODE_OAUTH_TOKEN`; mã cũ set cả hai bằng cùng một cookie `sessionKey` → CLI luôn thử xác thực sai kiểu qua API key giả | Không bao giờ set `ANTHROPIC_API_KEY` bằng giá trị không phải API key thật, kể cả "chỉ để thử" |
| 2026-10-13 | `claude setup-token` sinh OAuth token sống ~1 năm cho CI/server không trình duyệt; khi không reach được localhost callback (SSH/container), CLI tự chuyển sang hiện mã để dán ngược lại terminal | Dùng cơ chế này thay cookie `sessionKey` (hết hạn nhanh) cho mọi app chạy Claude Code trên server headless |
| 2026-10-13 | Container production (Dokploy) chạy trước đây không mount volume nào | Đã cấu hình bind mount `/root/.gemini` -> `/root/.gemini` trong Dokploy DB (2026-11-21) để giữ phiên đăng nhập Google Antigravity bền vững qua mọi lần deploy |
| 2026-11-21 | CLI `agy 1.5.14` đã loại bỏ các model cũ (`gemini-3.7-flash`, v.v.), chuyển sang thế hệ mới (`gemini-3.8-flash`, `gemini-4-neon`, `gemini-4-hydrogen`, `gemini-4-argon`, `claude-sonnet-5-5`, `claude-opus-5-5`) | Mặc định chuyển sang `gemini-3.8-flash` cho cả OCR và Dịch |
| 2026-11-21 | Upstream `microsoft/markitdown` bump lên v0.1.9, mở rộng Python 3.10-3.14, nâng cấp DocIntel API key & query fields | Toàn bộ 8 tệp fork giữ nguyên tương thích; test roundtrip FEN và smoke import đạt 100% |
| 2026-11-22 | `gr.BrowserState` mã hóa bằng khóa ngẫu nhiên MỖI LẦN app khởi động → sau redeploy trình duyệt không đọc lại được giá trị cũ | `job_state` dùng `secret` cố định; `prefs` (khóa/token) chưa (P6, chưa kiểm chứng) |
| 2026-11-22 | `allowed_paths` của `launch` phải gồm `MID_DATA_DIR`, nếu không mọi liên kết tải kết quả công việc nền trả 403 (test đơn vị không bắt được, chỉ thấy khi mở trình duyệt) | Luôn kiểm liên kết tải bằng trình duyệt thật sau khi đổi nơi lưu tệp |
| 2026-11-22 | `python` trên PATH (3.8) đọc script từ stdin theo cp1252 → lỗi `Non-UTF-8 code` với tiếng Việt | Dùng `PYTHONUTF8=1 .venv/Scripts/python.exe -` |
| 2026-11-22 | `_apply_preset` luôn bật tự lưu/Dropbox/tải về → chạy thử trên dev ghi tệp vào `Downloads` thật của người dùng | Chạy thử với `USERPROFILE` trỏ thư mục giả (P7, sửa ở G1.8) |
| 2026-11-21 | Trong công cụ Bash của Claude Code, heredoc chứa `\n`, dấu nháy lẫn lộn hoặc dòng trống dễ bị mangle/vỡ | Tạo tệp có chuỗi escape bằng công cụ Write/Edit, không bằng `cat <<EOF` |
| 2026-11-21 | `.venv` dùng `uv` (không có `pip`); đặt cp1252 làm script in tiếng Việt lỗi nếu quên `PYTHONUTF8=1` | Cài gói bằng `uv pip install --python .venv/Scripts/python.exe -r requirements-gui.txt` |
| 2026-11-21 | Chặn `subprocess.Popen` **trước** khi `import gradio` làm hỏng `asyncio` (`TypeError: function() argument 'code'…`) | Import app trước, rồi mới `mock.patch` `subprocess` (xem `tests_gui/test_fake_engine_flow.py`) |

## 4. Quyết định đã chốt (đừng đảo lại nếu không có lý do mới)

- Fork **không sửa lõi** `packages/markitdown`; mọi mã riêng ở thư mục gốc để merge upstream dễ. Đã merge upstream 3 lần (`46d5350`, `ba0a8ad`, `a722ceb`).
- Giao diện: **Phương án A** trong `design_handoff_markitdown_gui/` (hai cột, navy `#2B3990`, sun `#F6B92B`, teal `#1FA98F`).
- Ký hiệu nước đi đầu ra: `1.e4 e5` / `2.Mf3 Mc6`, V/H/X/T/M, nhập thành `0-0`. Chương → `#`, biến → `##`, ván → `###`.
- Sách Tây Ban Nha: nguồn `T` (Torre) → `X`, nguồn `A` (Alfil) → `T`. **Không** giữ nguyên chữ.
- Antigravity là engine **mặc định**, Claude Code là phương án 2, Gemini REST chỉ là dự phòng.

## 5. Việc dang dở / câu hỏi mở

- [ ] Mở web ra ngoài cần xác thực và tách phiên người dùng (S1, S2, S7 trong `docs/RA-SOAT-RUI-RO.md`). Chủ dự án chưa quyết.
- [ ] Đưa mô hình ONNX vào image Docker hoặc mount volume (O1). Chưa rõ giấy phép/nguồn mô hình để phân phối.
- [ ] Volume cho `~/.gemini` (Antigravity) trên Dokploy để giữ đăng nhập qua các lần deploy (O2, phần
      Antigravity) — chưa làm. Phần Claude Code đã giải quyết khác: không cần volume, chỉ cần biến môi
      trường `CLAUDE_CODE_OAUTH_TOKEN` trong cấu hình Dokploy (xem `docs/tinh-nang/12-dang-nhap-claude-code.md`).
- [ ] Thử thật trên VPS luồng "Đăng nhập Claude Code" (`claude_login_bridge.py`) — định dạng output thật
      của `claude setup-token` chưa được quan sát, chỉ dựa trên tài liệu chính thức + CLI giả lập.
- [ ] Quyết định xóa hay giữ gói `markitdown-ocr` khỏi Dockerfile (O5). (Gói `dropbox` đã bỏ ở G0.1, 2026-11-21.)
- [ ] Quyết định `DROPBOX_TARGET_FOLDER`: cài đặt hay xóa khỏi tài liệu (B12).
- [ ] Chưa có số liệu chất lượng thật cho OCR/FEN ("94%" trong `chessboard_fen.py` là số của dự án gốc).
- [ ] Các mục "❓ Suy ra" trong sổ rà soát cần thử với dịch vụ thật (B1, B4, S4…). S10 đã xử lý 2026-10-13.

- [ ] Chủ dự án duyệt nhánh `feat/nang-cap-giao-dien` trước khi merge `main` (push `main` = Dokploy tự deploy). Đặt `MID_AUTH_USER`/`MID_AUTH_PASS` trên Dokploy khi muốn bật đăng nhập (S1). Chưa kiểm chứng đăng nhập sau proxy Traefik/HTTPS.

## 6. Cách cập nhật tệp này

Khi kết thúc một phiên: thêm dòng vào mục 3 (điều học được), sửa mục 2 (trạng thái), đánh dấu/đóng mục 5. Đừng chép lại những gì đã có trong
`docs/`. Nếu một dòng ở đây trở nên sai (đã sửa mã), **xóa dòng đó** và ghi quyết định vào `docs/LICH-SU-PHAT-TRIEN.md`.
