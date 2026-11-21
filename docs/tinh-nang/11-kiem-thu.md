# Tính năng 11 — Kiểm thử

> Tài liệu này mô tả mã nguồn tại commit `2c1df67b44` (2026-09-27).
> Tệp của fork: `_test_dropbox_sync.py` (72 dòng), `_test_translate_roundtrip.py` (90 dòng).
> Kiểm thử upstream: `packages/*/tests/`.

---

# Phần A — Chức năng

Có **hai lớp** kiểm thử tách biệt:

| Lớp | Bảo vệ cái gì | Chạy tự động trên CI? |
|---|---|:-:|
| **Upstream** — `packages/markitdown/tests` (35 tệp), `markitdown-ocr`, `markitdown-mcp`, `markitdown-sample-plugin` | Thư viện chuyển đổi và các gói con | ✅ (GitHub Actions, khi `pull_request`) |
| **Fork** — hai tệp `_test_*.py` ở thư mục gốc | Đồng bộ Dropbox; bảo vệ khối bàn cờ khi dịch | ❌ (không có job nào gọi tới) |

Phần cốt lõi của bản fork — OCR, prompt, nhận diện bàn cờ, giao diện — **hầu như chưa có kiểm thử tự động**.

---

# Phần B — Kỹ thuật

## 1. Kiểm thử của fork

### `_test_translate_roundtrip.py` (90 dòng)

Kịch bản viết bằng các câu lệnh `assert` ở cấp mô-đun (không có hàm test), chạy trực tiếp bằng
`python _test_translate_roundtrip.py`, **không gọi AI**. Tám nhóm kiểm tra:

1. `_extract_boards` rồi `_restore_boards` cho đúng nguyên văn trên một mẫu Markdown có hai khối `chessboard`
   (một khối có `strict: false`, kèm dòng cảnh báo); mẫu phải tách được đúng 2 khối và không còn "```chessboard" trong phần văn bản.
2. `_split_chunks(max_chars=80)` cho ≥ 2 đoạn và `"\n".join(chunks) == text.strip()`.
3. `max_chars=10**6` cho đúng 1 đoạn.
4. `_placeholders_in` phát hiện placeholder bị mất, và chấp nhận placeholder còn nguyên.
5. Văn bản rỗng cho danh sách rỗng.
6. Chế độ tài liệu thường (`chess=False`): tách **cả ba** khối rào (`bash`, `chessboard`, `python`) và khôi phục
   nguyên vẹn.
7. Chế độ cờ vua trên cùng mẫu: chỉ tách khối `chessboard`.
8. `TRANSLATE_INSTRUCTION_CHESS` khác `TRANSLATE_INSTRUCTION_GENERAL`, và bản cờ vua chứa quy tắc `K → V`.

Đây là bảo hiểm cho thuật toán bảo vệ FEN ở [tài liệu 02](02-dich-tieng-viet.md). Nó **không** kiểm tra việc dịch,
`_looks_untranslated` hay `_translate_chunk`.

### `_test_dropbox_sync.py` (72 dòng, `unittest`)

| Ca | Kỳ vọng |
|---|---|
| `test_resolve_dropbox_token_empty` | `("", "Chưa cung cấp…")` |
| `test_resolve_dropbox_token_direct` | trả token trực tiếp, không lỗi |
| `test_test_dropbox_connection_invalid_token` | `ok=False`, thông điệp chứa `❌` hoặc `Lỗi` |
| `test_upload_to_dropbox_nonexistent_file` | `(None, "…không tồn tại")` |
| `test_upload_to_dropbox_missing_auth` | tệp tạm có thật, không token → `(None, "Không thể xác thực…")` |
| `test_gui_prefs_state` | `markitdown_gui._save_prefs(...)` giữ đúng `dropbox_token`, `dropbox_folder`, `dropbox_sync` |

**Lưu ý:** ca `test_test_dropbox_connection_invalid_token` truyền token sai nên **gọi mạng tới Dropbox**
(`api.dropboxapi.com`) — cần Internet; kỳ vọng chỉ là `ok=False`. Tệp import `markitdown_gui`, nên cần `gradio`
đã cài. Ca `test_gui_prefs_state` truyền `engine_v="Google Antigravity"` và `mode_v="Sách cờ vua"` — **không phải**
giá trị thật (`"antigravity"`, `MODE_CHESS`); test chỉ kiểm việc đóng gói dict, không kiểm giá trị hợp lệ.

## 2. Kiểm thử upstream — chạy thế nào

| Gói | Lệnh (thư mục gốc gói) | Số tệp test | Dòng test |
|---|---|---:|---:|
| `markitdown` | `hatch test` | 35 (`test_*.py`) | 10.424 (cả dữ liệu, `_test_vectors.py`) |
| `markitdown-ocr` | `pytest` (sau khi cài `./packages/markitdown ./packages/markitdown-ocr pytest`) | 9 | 2.149 |
| `markitdown-mcp` | `pytest` (sau khi cài `./packages/markitdown[all] ./packages/markitdown-mcp pytest`) | 4 | 611 |
| `markitdown-sample-plugin` | `pytest` | 2 | 46 |

Ma trận CI: Ubuntu × Python 3.10 / 3.11 / 3.12 / 3.13, cộng Windows và Windows ARM (3.12). Biến `PYTHONUTF8=1`
(giữ Unicode trong đầu ra CLI trên Windows), `PIP_CONSTRAINT` trỏ `.github/constraints.txt`.

Các nhóm kiểm thử của lõi (theo tên tệp): PDF (`test_pdf_tables`, `test_pdf_masterformat`, `test_pdf_memory`), DOCX (ảnh, công thức,
kiểu), PPTX (ghi chú, ảnh, SVG, tiêu đề rỗng), XLSX, EPUB, RSS, YouTube, CSV, Outlook, charset, CLI, đường dẫn tệp,
ZIP; test vector chung ở `_test_vectors.py` + `test_module_vectors.py` + `test_cli_vectors.py`.

## 3. Khoảng trống cần lấp (đề xuất — chưa thực hiện)

| Cần | Cách làm gợi ý |
|---|---|
| `_normalize_chessboard_blocks`, `_board_field_valid`, `extract_fens` | Hàm thuần, dễ kiểm bằng chuỗi vào/ra; không cần AI |
| `_split_chunks`, `_looks_untranslated` | Hàm thuần |
| `ocr_image_group` (tách marker `HET_TRANG`) | Giả `_run_engine_ocr` trả chuỗi có marker đủ/thiếu/thừa |
| `chessboard_fen` (`_mask_to_bbox`, `_dedupe_boxes`, `_reading_order`, `_grid_to_fen_board`, `refine_fen`) | Hàm thuần không cần mô hình |
| `_apply_preset` | Kiểm bảng preset ↔ danh sách model của từng engine |
| `find_agy`/`find_claude`/`is_engine_available` | Giả `shutil.which` và hệ thống tệp |
| Luồng `on_convert_files` | Giả `convert_file`, `_translate_to_vn`, `upload_to_dropbox` |

## 4. Điểm cần lưu ý và hạn chế

- Hai tệp `_test_*.py` **có tiền tố gạch dưới** nên `pytest` mặc định (chỉ nhặt `test_*.py` hoặc `*_test.py`)
  **không tự phát hiện** chúng. Chạy bằng `python _test_translate_roundtrip.py` hoặc `python -m unittest _test_dropbox_sync`.
- Chúng `import markitdown_gui`/`infrastructure`/`claude_translate` ở thư mục gốc → phải chạy **từ thư mục gốc repo**.
- Test Dropbox chạm mạng (xem trên).
- Không có test cho đường Antigravity, Claude CLI, Gemini REST vì chúng cần tài khoản và tiến trình con.

## 5. Đường dẫn tham chiếu nhanh

| Muốn xem… | Mở |
|---|---|
| Test bảo vệ FEN khi dịch | **`_test_translate_roundtrip.py`** |
| Test Dropbox | **`_test_dropbox_sync.py`** |
| Cấu hình CI | `.github/workflows/tests.yml` |
| Test lõi | `packages/markitdown/tests/` |
| Dữ liệu test OCR | `packages/markitdown-ocr/tests/ocr_test_data/` |
