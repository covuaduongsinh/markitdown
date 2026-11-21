# Hướng dẫn nhân bản phần mềm và thêm module mới

> Tài liệu này mô tả mã nguồn tại commit `2c1df67b44` (2026-09-27).
> Mọi "điểm chạm" (tệp + dòng) lấy từ mã hiện tại; số dòng sẽ lệch sau khi sửa — hãy tìm theo tên hàm/hằng.
> Đây là **hướng dẫn thực hiện**, chưa được chạy thử từng bước.

---

# Phần A — Nên làm gì trước

## Ba kiểu nhân bản thường gặp

| Nhu cầu | Mức công sức | Đường đi |
|---|---|---|
| **Chạy một bản y hệt cho tổ chức khác** (cùng sách cờ vua, khác thương hiệu/máy chủ) | Nhỏ | Mục 1 (danh sách việc cần đổi) |
| **Dùng cho loại sách khác** (luật, y khoa, giáo trình) | Vừa | Mục 1 + mục 3.5 (chế độ "tài liệu thường" đã có sẵn; thêm chế độ riêng nếu cần quy tắc như ký hiệu cờ) |
| **Thêm khả năng mới** (engine AI khác, ngôn ngữ ký hiệu mới, nơi đồng bộ khác) | Vừa | Mục 3 (các bài mẫu) |

## Nguyên tắc để không đau khi cập nhật từ upstream

1. **Không sửa** `packages/markitdown` (lõi) trừ khi bắt buộc; mọi thay đổi của fork nằm ở thư mục gốc. Nhờ vậy
   `git merge upstream/main` không xung đột.
2. Muốn thêm định dạng tệp mới → viết **plugin** (mẫu: `packages/markitdown-sample-plugin`), không sửa lõi.
3. Giữ mã riêng ở bảy tệp gốc; nếu một tệp phình (như `markitdown_gui.py` 1.985 dòng) thì tách trước khi thêm.

---

# Phần B — Kỹ thuật

## 1. Danh sách việc cần đổi khi nhân bản cho tổ chức khác

### 1.1 Thông tin cá nhân/hạ tầng đang nằm cứng trong mã

Quét bằng `grep -in "duongsinh|dsc.edu.vn|Dương Sinh|covuaduongsinh"`:

| Tệp | Dòng | Đang là | Việc cần làm |
|---|---:|---|---|
| `chessboard_fen.py` | 37 | `DEFAULT_MODELS_DIR = r"C:\Users\duongsinh\Documents\code\ocrchessboard\public\models"` | Đổi mặc định (thư mục trong repo, ví dụ `models/`) hoặc bắt buộc đặt `OCRCHESS_MODELS_DIR` |
| `infrastructure.py` | 123 | Chuỗi hướng dẫn chứa `C:\\Users\\duongsinh\\.claude.json` | Đổi thành `~/.claude.json` hoặc dùng `os.path.expanduser` |
| `markitdown_gui.py` | 479, 921 | Bình luận và tagline "Cờ vua Dương Sinh — tài liệu & sách cờ → Markdown" | Đổi thương hiệu (mục 1.2) |
| `GUI_README.md` | 1 | Tiêu đề | Đổi |
| `docs/DROPBOX_GUIDE.md`, `docs/plans/*` | vài dòng | Tên miền `markitdown.dsc.edu.vn`, tên repo `covuaduongsinh/markitdown`, dịch vụ Swarm và địa chỉ VPS | Đổi, hoặc bỏ khỏi bản sao |
| `README.md` | khối đầu | Khối "Bản fork Cờ vua Dương Sinh" | Đổi |

Mô hình bàn cờ (5 tệp `.onnx`) **không có trong repo**: phải lấy từ dự án `ocrchessboard` và đặt vào thư mục
mà `OCRCHESS_MODELS_DIR` trỏ tới. Đây là việc bắt buộc nếu muốn nhận diện FEN cục bộ.

### 1.2 Đổi thương hiệu giao diện

Toàn bộ nằm trong `markitdown_gui.py` và `assets/`:

| Việc | Nơi |
|---|---|
| Màu, phông | khối `CSS` (dòng ~676–906): biến `--navy`, `--sun`, `--teal`, `--c-*` ở hai theme; `_FONTS_LINK` (Google Fonts) |
| Logo, biểu tượng | `assets/symbol-white.svg`, `logo-horizontal-*.svg`; `_SYMBOL_WHITE` (dòng 499); `TOPBAR_HTML` |
| Tên "MarkItDown", tagline, huy hiệu định dạng | `TOPBAR_HTML` (dòng ~917–934) |
| Quân cờ vẽ trong xem trước | `assets/pieces/*.svg` (12 tệp `wp…bk`); `_PIECE_NAMES`, `_PIECES` |
| Màu ô bàn cờ | trong `_SCRIPT`, hàm `boardHTML` (`#F6F2E4`, `#46B49A`, viền `#2B3990`) |
| Tiêu đề trang | `gr.Blocks(title="MarkItDown")` |
| Thiết kế gốc để tham chiếu | `design_handoff_markitdown_gui/README.md` |

### 1.3 Cấu hình khi triển khai

| Việc | Ghi chú |
|---|---|
| Biến môi trường | Bảng ở [`../TECH.md`](../TECH.md) mục 6 |
| Đăng nhập thuê bao | Mỗi tổ chức cần tài khoản riêng; xem cảnh báo dùng chung token ở [`RA-SOAT-RUI-RO.md`](RA-SOAT-RUI-RO.md) |
| Mô hình ONNX | Mount volume hoặc `COPY` vào image, đặt `OCRCHESS_MODELS_DIR` |
| Lưu bền đăng nhập | Mount `~/.gemini` và `~/.claude.json` thành volume (repo chưa làm) |
| Dropbox | Tạo Dropbox App riêng; xem `docs/DROPBOX_GUIDE.md` |
| Ghim phiên bản | Ghim `gradio`, `onnxruntime`… trong Dockerfile (bảng ở TECH.md mục 2) |

## 2. Bản đồ "muốn đổi X thì sửa Y"

| Muốn… | Sửa |
|---|---|
| Thêm/đổi model AI | `ai_engine.py` bốn danh sách (dòng 32–59); preset ở `markitdown_gui.py` `_PRESET_OPTS_AGY/CLAUDE` |
| Đổi cách AI đọc trang (quy tắc OCR) | `claude_ocr.py` các hằng `_PROMPT_*` (dòng 30–143, 165–191, 240–268) |
| Đổi quy tắc dịch / ký hiệu | `claude_translate.py` `_CHESS_*` (dòng 36–152), `TRANSLATE_INSTRUCTION_GENERAL` (162) |
| Đổi kích thước đoạn dịch, số luồng | `_split_chunks(max_chars=6000)`, `TRANSLATE_WORKERS = 8`, `OCR_WORKERS = 8` |
| Đổi ngưỡng nhận diện bàn cờ | `chessboard_fen.py`: `_crop_to_chessboard`, `_board_squares_ensemble`, `_is_board_flipped`, `detect_boards` (tham số mặc định) |
| Đổi thư mục lưu tạm | `markitdown_gui.py` `_OUTPUT_DIR` (dòng 46) |
| Đổi thư mục Dropbox mặc định | `dropbox_folder_in` (dòng ~1627) và `infrastructure.upload_to_dropbox` (dòng 466) |
| Bật xác thực web | tham số `auth=` của `launch(...)` (dòng ~1975; chưa dùng — tự thử theo tài liệu Gradio) |

## 3. Các bài mẫu (playbook)

### 3.1 Thêm một ngôn ngữ ký hiệu cờ vua mới (ví dụ Pháp, Đức)

Đây là bài **hay gặp nhất** — sách Nga và Tây Ban Nha đã được thêm đúng cách này (commit `829a67e`, `2e264f9`).

| # | Tệp | Việc |
|---|---|---|
| 1 | `claude_translate.py` | Thêm `_CHESS_II_XX` (mục II: tên quân, bảng ký hiệu → V/H/X/T/M, figurine, thuật ngữ). **Kiểm chồng chữ cái**: nếu chữ nguồn trùng chữ đích (như `T` của Torre = Xe), phải ghi rõ trong prompt. Rồi `TRANSLATE_INSTRUCTION_CHESS_XX = _CHESS_HEAD + _CHESS_II_XX + _CHESS_TAIL` và thêm nhánh `elif chess_lang == "xx"` trong `translate_markdown_vn` (dòng ~439–446) |
| 2 | `claude_ocr.py` | Thêm `_PROMPT_FOOTER_XX` (giữ nguyên chữ quân cờ ngôn ngữ nguồn; figurine → chữ ngôn ngữ nguồn) và thêm khóa `"xx"` vào dict trong `_chess_footer` (dòng ~146) **và** dict `notation` trong `_merge_footer` (dòng ~203) |
| 3 | `markitdown_gui.py` | Thêm hằng `MODE_CHESS_XX`; nhánh trong `_chess_lang_from_mode` (dòng ~273); thêm vào `choices` của `mode` (dòng ~1658); thêm một thẻ vào `MODE_CARDS_HTML` **theo đúng thứ tự** với `data-mid-mode="N"` |
| 4 | `_test_translate_roundtrip.py` | Thêm kiểm tra: có `TRANSLATE_INSTRUCTION_CHESS_XX`, khác các bản còn lại |
| 5 | `docs/tinh-nang/02-dich-tieng-viet.md` | Thêm dòng vào bảng đối chiếu ký hiệu |

**Bẫy cần biết:**
- Thẻ chế độ (HTML) gắn với `gr.Radio` ẩn **theo chỉ số**: JS `midSelectMode(idx)` bấm `input[type=radio]` thứ `idx` trong
  `#mid-mode-radio`. Thứ tự thẻ trong `MODE_CARDS_HTML` **phải khớp** thứ tự `choices` của `mode`.
- `_is_chess_mode` = `label != MODE_GENERAL`, nên chế độ mới tự được coi là cờ vua, không cần sửa thêm.
- `_looks_untranslated` chỉ có nhánh đặc biệt cho `"ru"` (đếm chữ Cyrillic). Ngôn ngữ nguồn dùng chữ không-Latin khác
  (ví dụ Trung, Hy Lạp) thì cần thêm nhánh tương ứng.
- Sách Tây Ban Nha/Anh dùng chữ Latin, chỉ khác bảng chữ quân cờ — phần "chưa dịch" dựa vào dấu tiếng Việt vẫn đúng.

### 3.2 Thêm một động cơ AI mới (ví dụ OpenAI Codex CLI)

| # | Tệp | Việc |
|---|---|---|
| 1 | `ai_engine.py` | Hằng `ENGINE_XXX`; thêm vào `ENGINE_LABELS`; hai danh sách model `XXX_OCR_MODELS`, `XXX_TRANSLATE_MODELS`; hàm `find_xxx()`; nhánh `elif engine == ENGINE_XXX` trong `is_engine_available`; hàm `run_xxx_prompt(prompt, model, effort, img_dir, timeout, …)` trả **chuỗi Markdown** và ném `AIEngineError` khi lỗi |
| 2 | `claude_ocr.py` | `_run_engine_ocr` (dòng 535): hiện nhánh `else` mặc định là Claude → thêm `elif engine == "xxx"`. Nếu có thông điệp lỗi cứng theo engine (`ocr_pdf`, dòng ~768) thì thêm nhánh |
| 3 | `claude_translate.py` | `_call_engine_translate` (dòng 334): tương tự |
| 4 | `markitdown_gui.py` | Bảng `_PRESET_OPTS_XXX`; sửa `_apply_preset` (dòng 1367; hiện chọn bảng bằng `if engine == ENGINE_ANTIGRAVITY else`), `build_ui` (khởi tạo `init_ocr_choices`… dòng ~1730), và **bốn chỗ tính `engine_name`** (`_ocr_to_outputs` 360, `convert_file` 388, `_translate_to_vn` 1006, `claude_ocr.ocr_pdf` 768) — nên rút thành một hàm dùng chung |
| 5 | `infrastructure.py` | `test_xxx_connection`, thêm vào `get_infrastructure_status` và `render_infrastructure_html`; nút kiểm tra ở `build_ui` |
| 6 | `Dockerfile` | Cài CLI (nhớ cân nhắc `\|\| true` như đang làm — nó che lỗi cài đặt) |

Cách kiểm tra engine mới: gọi `run_xxx_prompt` với prompt đơn giản và một ảnh mẫu; kiểm đường dẫn ảnh CLI có đọc
được (mỗi CLI có cách cấp quyền thư mục riêng — `agy` dùng `--add-dir`, `claude` dùng `--add-dir` + `--tools Read`).

### 3.3 Thêm nơi đồng bộ khác ngoài Dropbox (ví dụ Google Drive, S3, WebDAV)

Hiện logic đồng bộ bị **lặp ba lần** trong `on_convert_files` (dòng 1202, 1261, 1284). Trước khi thêm nơi thứ hai:

1. Rút ba khối lặp thành một hàm `_publish_outputs(path, save_dir, ...)` trả chuỗi trạng thái.
2. Định nghĩa giao diện chung: `upload(file_path, target, **cred) -> (remote_path | None, error | None)` — đúng chữ ký của
   `infrastructure.upload_to_dropbox`.
3. Thêm hàm `test_<dịch vụ>_connection` cùng chữ ký `(ok, message, latency_ms)` như `test_dropbox_connection`.
4. Thêm nhóm ô cấu hình vào thẻ "⚙️ Cài đặt Hạ tầng & API", thêm khóa vào `prefs`, `_load_prefs`, `_save_prefs`.
5. Cập nhật `docs/tinh-nang/07-dong-bo-dropbox.md` (đổi tên thành "đồng bộ đám mây").

### 3.4 Thêm định dạng đầu vào mới

Viết **plugin**, không sửa lõi: sao chép `packages/markitdown-sample-plugin` (`accepts` theo đuôi + MIME, `convert`
trả `DocumentConverterResult`, `register_converters`, entry point `markitdown.plugin`). Ứng dụng web hiện đặt
`enable_plugins=False` (`markitdown_gui.py`, ô ẩn `enable_plugins`, dòng ~1791) → muốn dùng plugin trên web phải
bật ô này (đổi thành `value=True`) và **cài plugin vào image**.

### 3.5 Dùng cho loại sách khác, không phải cờ vua

Chế độ **"Tài liệu thường"** (`MODE_GENERAL`) đã bỏ hết phần bàn cờ: `chess=False` → không render ảnh độ phân giải kép, không
chạy ONNX, prompt OCR chỉ có `_PROMPT_HEADER + _PROMPT_FOOTER_PLAIN`, dịch dùng `TRANSLATE_INSTRUCTION_GENERAL` và bảo vệ mọi khối rào ```.

Muốn đặc thù hóa (ví dụ giữ nguyên số điều khoản pháp luật, thuật ngữ y khoa):
1. Sao chép nhóm hằng `_PROMPT_*` và `TRANSLATE_INSTRUCTION_GENERAL`, thêm quy tắc riêng.
2. Thêm một chế độ mới theo mẫu 3.1 (bước 3), nhưng `chess` vẫn `False`; cần sửa `_is_chess_mode` vì hiện `label != MODE_GENERAL`
   sẽ coi chế độ mới là cờ vua.
3. Có thể **xóa** `chessboard_fen.py` và mọi tham chiếu (`claude_ocr` bọc `import chessboard_fen` trong `try/except`, nên
   xóa tệp không làm gãy import).

### 3.6 Dịch sang ngôn ngữ đích khác tiếng Việt

Tiếng Việt cứng ở: tên tham số `translate_to="vi"`, hằng `_PROMPT_MERGE_*`, `_CHESS_*` (đích V/H/X/T/M),
`_VI_DIACRITICS` và `_looks_untranslated` (phát hiện "chưa dịch" bằng dấu tiếng Việt), tên tệp `_vn.md`,
nhãn giao diện. Đổi ngôn ngữ đích nghĩa là viết lại **cả bốn khối** này; riêng `_looks_untranslated` phải đổi
tiêu chí (ví dụ mật độ chữ cái đặc trưng của ngôn ngữ đích).

## 4. Danh mục kiểm tra trước khi giao bản sao

- [ ] Không còn `duongsinh` trong `*.py` (`grep -rn duongsinh --include=*.py .`)
- [ ] `OCRCHESS_MODELS_DIR` trỏ tới thư mục có đủ `fen.onnx`, `bbox.onnx` (và nên có `existence`, `rotation`, `orientation`)
- [ ] `python -c "import chessboard_fen; print(chessboard_fen.available())"` in `True`
- [ ] `agy` hoặc `claude` đã đăng nhập; nút "Kiểm tra kết nối" báo ✅
- [ ] Chuyển thử một PDF scan ngắn (2–3 trang) ở cả hai chế độ (cờ vua, thường) và có/không dịch
- [ ] Chạy `_test_translate_roundtrip.py` và `_test_dropbox_sync.py`
- [ ] Nếu mở web ra ngoài: đã có xác thực và HTTPS; đã đọc [`RA-SOAT-RUI-RO.md`](RA-SOAT-RUI-RO.md) mục "Bảo mật"
- [ ] Đổi thương hiệu (mục 1.2), cập nhật `README.md`, `docs/`
- [ ] Ghi lại phiên bản đã ghim của `gradio`, `onnxruntime`… vào `TECH.md`

## 5. Đường dẫn tham chiếu nhanh

| Muốn xem… | Mở |
|---|---|
| Mẫu thêm ngôn ngữ ký hiệu | Commit `829a67e` (Nga), `2e264f9` (Tây Ban Nha) — `git show <hash>` |
| Mẫu plugin | `packages/markitdown-sample-plugin/` |
| Danh sách rủi ro | [`RA-SOAT-RUI-RO.md`](RA-SOAT-RUI-RO.md) |
| Bảng cấu hình | [`../TECH.md`](../TECH.md) |
| Quy trình cho AI khi sửa mã | [`../SKILLS.md`](../SKILLS.md), [`../AGENTS.md`](../AGENTS.md) |
