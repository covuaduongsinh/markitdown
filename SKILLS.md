# SKILLS — Danh mục năng lực của phần mềm và các bài làm mẫu (playbook)

> Mô tả mã nguồn tại commit `2c1df67b44` (2026-09-27).
> Hai nửa: **(A)** phần mềm *làm được gì* (để rà soát đủ/thiếu và tìm nơi cắm tính năng mới); **(B)** *cách làm* các việc lặp lại
> cho người/AI bảo trì. Chi tiết thuật toán ở `docs/tinh-nang/`.

---

# A. Danh mục năng lực (capability registry)

Trạng thái: ✅ hoạt động theo mã · ⚠️ có điều kiện / có rủi ro đã biết · 🔌 có mã nhưng giao diện không dùng.

## A1. Chuyển đổi tài liệu

| Năng lực | Hàm vào | Tệp | Trạng thái | Ghi chú |
|---|---|---|:-:|---|
| Chuyển tệp thường (Word/Excel/PPT/HTML/CSV/EPUB/ZIP…) | `_convert` | `markitdown_gui.py:219` → lõi `MarkItDown.convert` | ✅ | `enable_plugins=False` |
| Chuyển URL (YouTube, Wikipedia, RSS, web) | `convert_url`, `on_convert_url` | `markitdown_gui.py:469, 1322` | ⚠️ | Có nguy cơ SSRF (S5) |
| OCR PDF scan | `ocr_pdf` | `claude_ocr.py:689` | ✅ | 8 luồng, thử lại 1 lần |
| OCR ảnh lẻ | `ocr_image_file` | `claude_ocr.py:786` | ✅ | |
| OCR nhiều trang một lần gọi | `ocr_image_group` | `claude_ocr.py:604` | ✅ | 1–3 trang, marker `HET_TRANG` |
| Bỏ header/footer/số trang | `_PROMPT_CLEANUP` | `claude_ocr.py:30` | ✅ | Do AI thực hiện qua prompt |
| Buộc OCR dù PDF có lớp chữ | ô "Buộc OCR toàn bộ" | `markitdown_gui.py:413` | ✅ | |
| Tự OCR khi PDF không có chữ | nhánh cuối `convert_file` | `markitdown_gui.py:445` | ✅ | |

## A2. Cờ vua

| Năng lực | Hàm vào | Tệp | Trạng thái |
|---|---|---|:-:|
| Tìm hình bàn cờ trong trang | `detect_boards` | `chessboard_fen.py:397` | ⚠️ cần mô hình ONNX ngoài repo |
| Bàn cờ → FEN | `infer_fen`, `fens_for_page` | `chessboard_fen.py:367, 478` | ⚠️ (O1) |
| Sửa lượt đi theo tình trạng chiếu | `refine_fen` | `chessboard_fen.py:343` | ✅ |
| AI tự nhận diện bàn cờ (khi không có ONNX) | `_PROMPT_CHESS_SELF` | `claude_ocr.py:60` | ✅ |
| Chuẩn hóa khối ```` ```chessboard ```` | `_normalize_chessboard_blocks` | `claude_ocr.py:330` | ✅ |
| Xuất `_fen.txt` | `extract_fens`, `_write_fen_file` | `claude_ocr.py:370`, `markitdown_gui.py:74` | ✅ |
| Vẽ bàn cờ trong xem trước | `midRenderBoards` (JS) | `markitdown_gui.py:576` | ✅ |
| Ký hiệu Anh → V/H/X/T/M | `_CHESS_II_EN` | `claude_translate.py:48` | ✅ |
| Ký hiệu Nga → V/H/X/T/M | `_CHESS_II_RU` | `claude_translate.py:66` | ✅ |
| Ký hiệu Tây Ban Nha → V/H/X/T/M | `_CHESS_II_ES` | `claude_translate.py:95` | ✅ |
| Giữ định dạng nước đi `1.e4 e5`, `0-0` | `_CHESS_TAIL` | `claude_translate.py:120` | ✅ |

## A3. Dịch

| Năng lực | Hàm vào | Tệp | Trạng thái |
|---|---|---|:-:|
| Dịch sách cờ vua | `translate_markdown_vn(chess=True)` | `claude_translate.py:422` | ✅ |
| Dịch tài liệu thường (giữ mọi khối code) | `translate_markdown_vn(chess=False)` | `claude_translate.py:422` | ✅ |
| Bảo vệ FEN/code bằng placeholder | `_extract_boards`, `_restore_boards` | `claude_translate.py:197, 213` | ✅ có test |
| Chia đoạn theo dòng trống / heading | `_split_chunks` | `claude_translate.py:225` | ✅ có test |
| Phát hiện "chưa dịch" | `_looks_untranslated` | `claude_translate.py:359` | ⚠️ ngưỡng 2% dấu Việt |
| Gộp OCR + dịch một lần | `translate_to="vi"` | `claude_ocr.py:165–233` | ✅ |
| Dịch lại trang gộp nhưng chưa dịch | `_ensure_translated` | `claude_ocr.py:557` | ✅ |

## A4. Động cơ AI

| Năng lực | Hàm vào | Tệp | Trạng thái |
|---|---|---|:-:|
| Antigravity (`agy`) | `run_agy_prompt` | `ai_engine.py:278` | ✅ |
| Claude Code (`claude`) | `_run_claude_ocr`, `_call_claude` | `claude_ocr.py:473`, `claude_translate.py:256` | ⚠️ hai `find_claude` khác nhau (B4) |
| Gemini REST (dự phòng) | `call_gemini_api_direct` | `ai_engine.py:203` | ⚠️ B1–B3 |
| Preset Tiết kiệm/Cân bằng/Chính xác × 2 engine | `_PRESET_OPTS_AGY`, `_PRESET_OPTS_CLAUDE` | `markitdown_gui.py:1348, 1357` | ✅ |
| Chọn engine mặc định | `get_default_engine` | `ai_engine.py:158` | ⚠️ B5 |

## A5. Giao diện và đầu ra

| Năng lực | Hàm vào | Tệp | Trạng thái |
|---|---|---|:-:|
| Kéo thả nhiều tệp | `gr.File` | `markitdown_gui.py:1473` | ✅ |
| Chọn tệp Windows giữ đường dẫn gốc | `on_pick_files`, `pick_files.py` | `markitdown_gui.py:1079` | ✅ Windows |
| Tiến độ theo trang/đoạn, giữ kết nối | `_stream_job` | `markitdown_gui.py:1026` | ✅ |
| Dừng | `btn_stop` | `markitdown_gui.py:1962` | ⚠️ B7 |
| Sáng/tối | `midToggleTheme` (JS) | `markitdown_gui.py:532` | ✅ |
| Nhớ tùy chọn | `gr.BrowserState` | `markitdown_gui.py:1812` | ⚠️ S3 |
| Tải về từng tệp / `.zip` | `_download_panel`, `_zip_all` | `markitdown_gui.py:140, 116` | ⚠️ S7 |
| Tự tải về trình duyệt | `midTriggerAutoDownloads` (JS) | `markitdown_gui.py:602` | ✅ |
| Lưu bản sao trên máy chủ | `_autosave`, `_resolve_save_dir` | `markitdown_gui.py:182, 205` | ⚠️ S6 |
| Đồng bộ Dropbox | `upload_to_dropbox` | `infrastructure.py:466` | ⚠️ O9 |

## A6. Hạ tầng và kết nối

| Năng lực | Hàm vào | Tệp | Trạng thái |
|---|---|---|:-:|
| Kiểm tra Antigravity / Claude / Gemini / Dropbox | `test_*_connection` | `infrastructure.py:23, 63, 189, 389` | ⚠️ B14 |
| Lưu token Antigravity phía máy chủ | `save_antigravity_token` | `infrastructure.py:142` | ⚠️ S2 |
| Bảng trạng thái hạ tầng | `get_infrastructure_status` | `infrastructure.py:259` | ⚠️ B6 |

## A7. Thư viện upstream (không do fork viết)

| Năng lực | Nơi | Trạng thái |
|---|---|:-:|
| 20+ converter (PDF, DOCX, PPTX, XLSX, EPUB, RSS, YouTube, Outlook…) | `packages/markitdown` | ✅ |
| OCR ảnh nhúng trong Office/PDF qua LLM vision | `packages/markitdown-ocr` | 🔌 |
| Công cụ MCP `convert_to_markdown` | `packages/markitdown-mcp` | 🔌 |
| Azure Document Intelligence / Content Understanding | lõi, khi truyền endpoint | 🔌 |
| Phiên âm âm thanh, mô tả ảnh bằng LLM | lõi | 🔌 (cần cấu hình) |

## A8. Chưa có (khoảng trống — ứng viên module mới)

| Khoảng trống | Ghi chú |
|---|---|
| Xác thực/tài khoản người dùng | S1, S2 |
| Hàng đợi công việc + hủy thật + lưu lịch sử | Hiện xử lý đồng bộ trong thread; không có DB |
| Tách phiên người dùng (thư mục tạm riêng) | S7 |
| Kiểm thử tự động cho OCR/GUI | T8 |
| Đánh giá chất lượng OCR/FEN (bộ dữ liệu chuẩn + chấm điểm) | Chưa có số liệu thật; "94%" là số của dự án gốc |
| Dịch sang ngôn ngữ khác tiếng Việt | Xem `docs/NHAN-BAN-VA-MO-RONG.md` 3.6 |
| Ngôn ngữ ký hiệu khác (Pháp, Đức, Ý…) | Xem `docs/NHAN-BAN-VA-MO-RONG.md` 3.1 |
| Nơi đồng bộ khác ngoài Dropbox | Xem 3.3 |
| Bảo vệ ngưỡng chi phí/hạn mức khi sách rất dài | Không có giới hạn số trang/đoạn |

---

# B. Bài làm mẫu (playbook)

### B1. Chạy ứng dụng và chuyển thử một cuốn sách

1. `.venv\Scripts\python.exe markitdown_gui.py`.
2. Thẻ **⚙️ Cài đặt Hạ tầng & API** → kiểm tra bảng trạng thái; bấm "Kiểm tra kết nối" cho engine sẽ dùng.
3. Kéo một PDF **ngắn (2–3 trang)** vào ô tải, chọn chế độ (Anh/Nga/Tây Ban Nha), preset **Tiết kiệm**.
4. Xem `<tên>.md`, `<tên>_vn.md`, `<tên>_fen.txt`; kiểm bàn cờ vẽ đúng trong "Xem trước".

### B2. Chẩn đoán "OCR ra trống / lỗi"

| Triệu chứng | Kiểm |
|---|---|
| `❌ Lỗi OCR: Không tìm thấy Google Antigravity CLI…` | `agy` có trong PATH? (`ai_engine.find_agy`); có API key Gemini không? |
| `*[Lỗi OCR trang N: …]*` | Nội dung sau dấu `:` là lỗi thô của CLI (`exit <mã>: …`); hết hạn mức? chưa đăng nhập? quá 600 s? |
| `OCR thất bại ở toàn bộ N trang` | Toàn bộ lời gọi hỏng → phiên đăng nhập/hạn mức/API Key |
| Trang ra thiếu/thừa khi dùng 2–3 trang/lần | Xem cảnh báo `*[Cảnh báo: model tách được số phần khác…]*`; thử `1 trang/lần` |
| Không có bàn cờ / FEN sai | `chessboard_fen.available()`; `OCRCHESS_MODELS_DIR` đúng chưa; xem tài liệu 03 |
| Bản dịch còn tiếng gốc | Tìm `*[Cảnh báo: đoạn này có thể chưa được dịch]*`; nâng effort dịch |
| Đoạn giữ nguyên văn kèm "mất khối bàn cờ/code" | Model đã nuốt placeholder; thử model mạnh hơn |

### B3. Kiểm chứng nhanh một hàm thuần mà không tốn hạn mức

```bat
:: từ thư mục gốc repo
.venv\Scripts\python.exe -c "import claude_ocr as c; print(c._board_field_valid('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR'))"
.venv\Scripts\python.exe _test_translate_roundtrip.py
```
Nếu in tiếng Việt lỗi `UnicodeEncodeError`, đặt `PYTHONUTF8=1` hoặc ghi ra tệp.

### B4. Thêm ngôn ngữ ký hiệu / engine / nơi đồng bộ
Xem `docs/NHAN-BAN-VA-MO-RONG.md` mục 3.1–3.3 (danh sách tệp và bẫy cụ thể).

### B5. Cập nhật tài liệu sau khi đổi mã
Theo bảng ở `AGENTS.md` mục 6. Số dòng lấy bằng `wc -l` hoặc đếm ký tự `\n` bằng script — **không** lấy từ số dòng cuối mà công cụ đọc
tệp hiển thị (có thể lệch 1). Đường dẫn trong tài liệu luôn **tương đối**.

### B6. Nhân bản cho tổ chức khác
Danh mục kiểm ở `docs/NHAN-BAN-VA-MO-RONG.md` mục 4.

### B7. Kỹ năng/agent ngoài repo có thể dùng (thuộc môi trường của chủ dự án, không nằm trong repo)

| Skill | Dùng khi |
|---|---|
| `document-repo` | Viết/cập nhật bộ tài liệu hai tầng cho repo |
| `ai-subscription-bridge` | Sửa `ai_engine.py`/`infrastructure.py`, thêm engine, đăng nhập thuê bao trên VPS |
| `superpowers:systematic-debugging` | Lỗi chưa rõ nguyên nhân |
| `superpowers:test-driven-development` | Viết test cho hàm thuần đã liệt kê ở A |
| `superpowers:verification-before-completion` | Trước khi báo "đã xong" |

Danh sách này là cấu hình cá nhân của chủ dự án (`~/.claude/skills`), có thể khác trên máy khác.
