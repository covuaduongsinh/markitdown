# AGENTS.md — Hướng dẫn cho mọi trợ lý AI / lập trình viên làm việc với repo này

> Mô tả mã nguồn tại commit `2c1df67b44` (2026-09-27). Claude Code đọc `CLAUDE.md` (nó nhập tệp này); các công cụ
> khác (Codex, Grok, Cursor…) đọc thẳng `AGENTS.md`.

## 1. Dự án là gì (30 giây)

Bản fork của `microsoft/markitdown` cho **Cờ vua Dương Sinh**. Phần **của fork** là các tệp Python ở thư mục gốc (xem bảng mục 2; từ 2026-11-21 `markitdown_gui.py` đã tách thành `pipeline.py`, `ui_theme.py`, `presets.py`, `ui_render.py`)
tạo thành một **ứng dụng web Gradio** chuyển sách cờ vua scan → Markdown: OCR bằng AI (CLI `agy` hoặc `claude`), nhận
diện bàn cờ → FEN bằng ONNX cục bộ, dịch sang tiếng Việt (ký hiệu Anh/Nga/Tây Ban Nha → V/H/X/T/M), đồng bộ Dropbox.
Thư mục `packages/` là **mã upstream** (lõi thư viện, plugin OCR, MCP, plugin mẫu) — **không sửa**.

## 2. Bản đồ nhanh

| Việc | Tệp | Tài liệu chi tiết |
|---|---|---|
| Giao diện: `build_ui`, handler, khởi chạy | `markitdown_gui.py` | `docs/tinh-nang/06-giao-dien-gradio.md` |
| Lõi chuyển đổi (không phụ thuộc Gradio): ghi tệp, `convert_file`, `_publish_output`, dịch | `pipeline.py` | `06-…` |
| Theme/CSS/JS (`assets/ui/app.css`, `app.js`), thẻ chế độ | `ui_theme.py` | `06-…` |
| Preset chất lượng, nhớ tùy chọn (`BrowserState`) | `presets.py` | `06-…` |
| HTML danh sách tải về | `ui_render.py` | `06-…` |
| Engine giả để kiểm thử (`MID_FAKE_ENGINE=1`) | `fake_engine.py` | `04-…` |
| Công việc nền (lưu đĩa, chạy tiếp, Dừng thật, Lịch sử) | `jobs.py`, `proc_control.py`, `job_handlers.py`, `job_view.py` | `docs/tinh-nang/13-cong-viec-nen.md` |
| OCR PDF/ảnh, prompt | `claude_ocr.py` | `docs/tinh-nang/01-ocr-pdf-anh.md` |
| Dịch, bảo vệ khối bàn cờ | `claude_translate.py` | `docs/tinh-nang/02-dich-tieng-viet.md` |
| Nhận diện bàn cờ (ONNX) | `chessboard_fen.py` | `docs/tinh-nang/03-nhan-dien-ban-co-fen.md` |
| Chọn engine, gọi `agy`/Gemini | `ai_engine.py` | `docs/tinh-nang/04-ai-engine.md` |
| Kiểm tra kết nối, token, Dropbox | `infrastructure.py` | `docs/tinh-nang/05-…`, `07-…` |
| Đăng nhập Claude Code trên web | `claude_login_bridge.py` | `docs/tinh-nang/12-dang-nhap-claude-code.md` |
| Chạy trên Windows / Docker | `run_gui.bat`, `Dockerfile` | `docs/tinh-nang/10-trien-khai-docker-vps.md` |

Tổng quan: `docs/TONG-QUAN-KIEN-TRUC.md`. Mục lục đầy đủ: `docs/README.md`. Cấu hình/phiên bản: `TECH.md`.
Rủi ro đã biết: `docs/RA-SOAT-RUI-RO.md`. Nhân bản/mở rộng: `docs/NHAN-BAN-VA-MO-RONG.md`.

## 3. Lệnh thường dùng

Dùng **`.venv\Scripts\python.exe`** (Python 3.12). `python` trên PATH của máy dev có thể là 3.8 và sẽ hỏng.

```bat
.venv\Scripts\python.exe markitdown_gui.py                    :: chạy web, http://127.0.0.1:7860
.venv\Scripts\python.exe _test_translate_roundtrip.py         :: test bảo vệ FEN khi dịch (không gọi AI)
.venv\Scripts\python.exe -m unittest discover tests_gui -v   :: test của fork (dùng engine giả, không gọi AI)
set MID_FAKE_ENGINE=1 && .venv\Scripts\python.exe markitdown_gui.py :: chạy web với engine giả (không tốn hạn mức)
.venv\Scripts\python.exe -m unittest _test_dropbox_sync -v    :: test Dropbox (có gọi mạng)
cd packages\markitdown && hatch test                          :: test thư viện upstream
```

Chạy test của fork **từ thư mục gốc repo** (chúng `import` các tệp ở gốc).

## 4. Quy ước mã nguồn (bắt chước khi thêm mã)

- Chú thích và chuỗi giao diện **tiếng Việt**; tên hàm/biến **tiếng Anh**; hàm nội bộ bắt đầu bằng `_`.
- Lỗi hiển thị cho người dùng là **chuỗi có biểu tượng** (✅ ⚠️ ❌ ⏳ ☁️ 💾 ⚡), không ném ra giao diện.
- Mọi lời gọi AI đi qua hàm điều phối theo engine: `_run_engine_ocr` (OCR) và `_call_engine_translate` (dịch).
- Tham số `engine, api_key, claude_token, agy_token` được truyền xuyên suốt — giữ nguyên mẫu này.
- Prompt gửi AI: chỉ thị bắt buộc viết **chữ HOA** (`BẮT BUỘC`, `KHÔNG`, `NGUYÊN VĂN`); một quy tắc chỉ nằm ở một hằng và được tái dùng
  (ví dụ `_CHESS_II_*` dùng chung cho OCR-gộp-dịch và dịch riêng).
- `import` bên trong hàm ở `claude_ocr`, `claude_translate`, `ai_engine`, `infrastructure` là **có chủ đích** (cắt vòng
  phụ thuộc). Đừng chuyển lên đầu tệp.
- Định dạng: `black` (pre-commit). Không có linter khác.

## 4b. Hằng số/định dạng không được phá

| Thứ | Vì sao |
|---|---|
| Placeholder `⟦CHESSBOARD_n⟧` | `claude_translate` dùng để bảo vệ FEN/code khi dịch |
| Marker `<<<<<--- HET_TRANG --->>>>>` | `claude_ocr` tách nhiều trang trong một lần gọi |
| `OperationCancelled` kế thừa `BaseException` (`proc_control.py`) | để `except Exception` sẵn có không nuốt tín hiệu Dừng; đừng đổi sang `Exception` |
| `jobs.data_dir()` nằm trong `allowed_paths` của `launch` | thiếu thì mọi liên kết tải kết quả công việc nền trả 403 |
| `secret` cố định của `job_state` (`BrowserState`) | đổi/bỏ thì sau mỗi redeploy trình duyệt mất mã công việc đang chạy |
| Cờ `ConvertResult.translated` (`pipeline.py`) | `on_convert_files` dùng để biết đã dịch chưa (thay cho việc dò chuỗi `"gộp 1 bước"`, B9; chuỗi đó nay chỉ để hiển thị) |
| Thứ tự thẻ chế độ ↔ `choices` của radio `mode` | JS `midSelectMode(idx)` bấm radio theo chỉ số |
| Thứ tự lớp `PIECE_TYPES` | Phải khớp mô hình ONNX gốc (`ocrchessboard`) |
| Định dạng khối ```` ```chessboard ```` một dòng `fen:` | Plugin Chessboard Viewer của Obsidian |
| Ký hiệu nước đi `1.e4 e5`, `0-0` | Quy ước đầu ra của bản dịch |

## 5. Ranh giới — điều KHÔNG được tự ý làm

1. **Không sửa `packages/markitdown*`** (mã upstream) trừ khi được yêu cầu rõ; sẽ xung đột khi `git merge upstream/main`.
2. **Không gọi `agy`, `claude`, Gemini, Dropbox thật** để "thử" nếu không được phép: chúng dùng hạn mức gói thuê bao/khoá
   của chủ dự án và Dropbox thật sẽ ghi tệp lên tài khoản của họ.
3. **Không commit khóa/token**: `~/.gemini/…`, `~/.claude.json`, `GEMINI_API_KEY`, `DROPBOX_*`, App Secret.
   Đừng dán chúng vào tài liệu, log, hay thông điệp commit.
4. **Không xóa `.omc/`** (trạng thái công cụ, đã trong `.gitignore`).
5. **Không đổi tên** `claude_ocr.py`/`claude_translate.py`/`ClaudeOCRError` mà chưa sửa mọi import (GUI, `infrastructure`, hai tệp test).
6. **Không thêm mã riêng vào lõi upstream**; nếu cần định dạng mới, viết plugin (mẫu ở `packages/markitdown-sample-plugin`).
7. **Không suy đoán hành vi của `agy`/`claude`**: chúng là công cụ ngoài; ghi "chưa kiểm chứng" thay vì khẳng định.

## 6. Quy trình làm việc

1. Đọc tài liệu tính năng liên quan (bảng mục 2) **trước khi** sửa; chúng ghi rõ điểm chạm và bẫy.
2. Kiểm `git status --short --branch` trước khi sửa (nhánh `main`, có thể có thay đổi chưa commit của chủ dự án).
3. Sửa nhỏ, đúng phạm vi. Hàm thuần (`_normalize_chessboard_blocks`, `_split_chunks`, `_looks_untranslated`, các hàm trong
   `chessboard_fen` không cần mô hình…) có thể kiểm tự động — nên viết test cho chúng khi đụng tới.
4. Sau khi sửa, **cập nhật tài liệu** theo bảng sau:

| Bạn đã đổi… | Cập nhật |
|---|---|
| Bất kỳ hành vi/thuật toán trong bảy tệp gốc | tài liệu tính năng tương ứng (`docs/tinh-nang/`) + số dòng trong bảng "Đường dẫn tham chiếu nhanh" |
| Thêm/xóa tệp, module | `docs/TONG-QUAN-KIEN-TRUC.md` (bản đồ module), `docs/README.md` |
| Biến môi trường, phiên bản, lệnh | `TECH.md` |
| Sửa một mục trong `RA-SOAT-RUI-RO.md` | đánh dấu đã xử lý (ghi commit) |
| Quyết định thiết kế | `docs/LICH-SU-PHAT-TRIEN.md` mục 3–4; điều chỉ phiên sau cần biết → `MEMORY.md` |

5. Commit theo thông điệp ngắn, kiểu `feat(phạm-vi): …` / `fix(phạm-vi): …` (lịch sử repo dùng kiểu này; commit sớm của fork
   là tiếng Việt không dấu hoặc tiếng Anh ngắn). Đẩy lên `origin main` → Dokploy tự deploy web (xem `docs/tinh-nang/10-…`), vì vậy
   **không push khi chưa được yêu cầu**.

## 7. Giao tiếp

Trả lời và viết tài liệu bằng **tiếng Việt**; giữ nguyên tiếng Anh cho mã, đường dẫn, tên lệnh, định danh. Tiêu đề mục
bằng tiếng Việt. (Chủ dự án đã yêu cầu điều này ở mọi dự án.)

## 8. Bẫy môi trường Windows

- Console `cp1252`: `print()` chuỗi tiếng Việt trong script Python ném `UnicodeEncodeError` → ghi ra tệp UTF-8 rồi đọc.
- Đặt `PYTHONUTF8=1` khi chạy công cụ in Unicode.
- Đường dẫn Windows có dấu cách và tiếng Việt (`markitdown giao diện.zip`): luôn đặt trong dấu nháy.
- `run_gui.bat` dùng `chcp 65001`.
