# Tính năng 14 — Hiệu đính kết quả: bảng thế cờ, đối chiếu trang, thuật ngữ, xuất Obsidian

> Tài liệu này mô tả mã nguồn trên nhánh `feat/nang-cap-giao-dien` (Giai đoạn 3 của kế hoạch `docs/plans/2026-11-21-nang-cap-giao-dien-va-tinh-nang.md`).
> Tệp chính: `fen_tools.py`, `review.py`, `review_handlers.py`, `glossary.py`, `obsidian.py`; phần sửa ở `jobs.py`, `claude_ocr.py`, `claude_translate.py`, `markitdown_gui.py`.
> Số dòng không ghi — hãy tìm theo tên hàm.

---

# Phần A — Chức năng

## Bài toán

OCR và nhận diện bàn cờ không bao giờ đúng 100%. Trước đây muốn sửa một thế cờ sai hay xem trang gốc để đối chiếu, người dùng phải mở tệp `.md`
ở công cụ khác và dò tay. Bản dịch thì dùng thuật ngữ do AI tự chọn, mỗi lần một kiểu. Và kết quả chưa ở dạng thuận tiện để đưa vào Obsidian.

## Người dùng làm gì

**Tab ♟ Thế cờ** (cạnh *Xem trước* / *Mã .md*) — bảng mọi thế cờ của tệp đang xem: số thứ tự, trang, FEN, trạng thái (✅ hợp lệ / ⚠️ cần xem).
Chọn một dòng (hoặc gõ số, hoặc ◀ ▶) để thấy bàn cờ thật, ô FEN sửa được, liên kết **Mở trong Lichess**. Nút **↻ Lật bàn 180°** xoay thế cờ khi mô hình
nhận ngược hướng; **💾 Áp dụng** ghi thế cờ đã sửa vào *mọi* nơi liên quan (tệp `.md`, `_vn.md`, `_fen.txt`, `.zip`) và vẽ lại Xem trước/Mã .md ngay.

**Tab 🔍 Đối chiếu trang** — ảnh trang gốc bên trái, Markdown của *đúng trang đó* bên phải (bàn cờ vẽ thật). Chuyển trang bằng ◀ ▶ hoặc gõ số;
bộ lọc *Tất cả trang / Chỉ trang lỗi / Chỉ trang có bàn cờ* để đi thẳng tới chỗ cần xem. Trang OCR lỗi hiện cảnh báo thay cho văn bản.

**Bảng thuật ngữ dịch** (trang Cài đặt → thẻ 5): mỗi dòng một cặp `nguồn → đích` (ví dụ `zugzwang → thế bí`). Từ lần dịch kế tiếp, AI được yêu cầu *luôn* dùng đúng bản dịch bạn ghi,
cả ở chế độ OCR+dịch gộp lẫn dịch riêng. Tối đa 60 thuật ngữ.

**Xuất cho Obsidian** (Tùy chọn nâng cao, hai công tắc):
- *Thêm frontmatter YAML*: đầu mỗi tệp `.md` có khối `---` gồm tiêu đề, nguồn, ngày, engine, model, số trang (và `translated: true` cho bản dịch).
- *Tách chương trong .zip*: tách theo tiêu đề cấp `#` thành các tệp `01-….md` trong thư mục `<tên sách>/` của `.zip` (không liệt kê riêng trong danh sách tải).

## Điều cần biết khi dùng

- Hiệu đính chỉ làm được khi công việc **đã xong** (không phải đang chạy).
- Sửa thế cờ được ghi vào cả điểm lưu của trang tương ứng, nên **"Chạy tiếp" / "Chạy lại" không làm mất sửa đổi**.
- Ảnh trang gốc chỉ có với tệp PDF; ảnh được tạo lần đầu bạn xem trang đó (rồi lưu lại).
- Bảng thuật ngữ dùng chung cho mọi người dùng của máy chủ.

---

# Phần B — Kỹ thuật

## 1. `fen_tools.py` — hàm thuần

| Hàm | Việc |
|---|---|
| `list_boards(md)` | các khối ```` ```chessboard ```` theo thứ tự: `{n, fen, valid}` |
| `fen_is_valid(fen)` | trường vị trí 8×8 hợp lệ (`_board_field_valid`) **và** đúng một Vua mỗi bên |
| `replace_nth_fen(md, n, fen)` | thay FEN khối thứ n, chuẩn hóa bằng `_normalize_chessboard_blocks` (đủ 6 trường, một dòng `fen:`, `strict: false` nếu không đủ hai Vua); `ValueError` khi n sai/FEN sai cú pháp |
| `flip_fen(fen)` | xoay 180° = đảo cả chuỗi trường vị trí (test đối chiếu với `chessboard_fen._rotate_grid_180`) |
| `board_html(fen, px)` | bàn cờ HTML: lưới 64 ô `.mid-sq.l/.d`, quân `.mid-pc.<màu><quân>` (ảnh nền sinh bởi `ui_theme.piece_css()`) |
| `lichess_url(fen)` | `https://lichess.org/editor/<fen với _ thay dấu cách>` |

## 2. `review.py` — hiệu đính một công việc đã xong

- **Văn bản chính** = tệp `md` nếu có, không thì `vn` (gộp OCR+dịch chỉ ghi `_vn.md`).
- **Ánh xạ thế cờ → trang** (`_board_pages`): đếm khối chessboard trong từng `pages/NNNN.md` theo thứ tự trang; chỉ dùng khi tổng khớp đúng số khối của văn bản chính, ngược lại `page=None`.
- `apply_fen(mgr, job_id, file_idx, n, fen)`: **tính trước** nội dung mới của mọi tệp rồi mới ghi (lỗi không để lại tệp ghi dở) → các `.md`/`_vn.md`, `raw.md`, điểm lưu trang (`pages/NNNN.md`), `_fen.txt` (`fens_text`), rồi `JobManager.rebuild_obsidian` (làm lại chương/frontmatter nếu bật) và zip.
- `page_list(...)`, `page_thumb(...)`: danh sách trang có điểm lưu (lọc lỗi/bàn cờ); ảnh JPEG ≤ 900 px tạo **khi cần** từ bản sao nguồn trong `src/` (pypdfium2, scale 1,5, chất lượng 72) rồi lưu `pages/NNNN.jpg` (không ảnh hưởng nạp điểm lưu: chỉ `.md` được đếm).

## 3. Giao diện (`review_handlers.py`, `build_ui`)

- Handler nhận `(job_id, file_pick)`; `FEN_OUTPUTS_N = 7` đầu ra: `fen_info, fen_table, fen_idx, fen_text, fen_preview, fen_link, fen_msg`.
- `gr.Dataframe` chỉ-đọc + `.select` → `fen_select`; ô số có `.submit` **và** `.blur`; ◀ ▶ dùng `fen_step`. **Không đặt `minimum` cho `gr.Number`** (ô rỗng/0 làm Gradio ném lỗi *trước khi* vào handler).
- Sau "Áp dụng": chuỗi `.then` gọi `job_handlers.render_job(job, "", True, selected)` (chữ ký rỗng = buộc vẽ lại) để Xem trước/Mã .md/tải về phản ánh tệp mới.
- JS `midRenderBoards` vẽ bàn cờ ở `#mid-preview` **và** `#mid-cmp-md`.

## 4. Bảng thuật ngữ (`glossary.py`)

- Tệp `glossary.md` trong `MID_DATA_DIR`. `parse` nhận `→`, `->`, `=>`; `#` là chú thích; trùng nguồn thì dòng sau thắng; giới hạn 60 cặp, mỗi vế ≤ 60 ký tự, tệp ≤ 20.000 ký tự, khối prompt ≤ 2.500 ký tự.
- `GLOSSARY_HEADER` + `prompt_block()` là **nơi duy nhất** định nghĩa quy tắc (theo quy ước prompt ở `AGENTS.md` mục 4). Chèn ở: `claude_ocr._build_prompt`/`_build_prompt_multi` (chỉ khi `translate_to == "vi"`, đặt **trước** chỉ thị đầu ra cuối) và `claude_translate.translate_markdown_vn` (nối vào `instruction`). Không có thuật ngữ → prompt giữ nguyên từng chữ như trước.
- Khóa điểm lưu dịch (`chunk_cache_key`) có thêm `glossary.fingerprint(block)`: đổi thuật ngữ thì các đoạn đã dịch **không** được dùng lại.

## 5. Xuất Obsidian (`obsidian.py`, `JobManager.apply_obsidian`)

- `frontmatter(meta)` luôn quote giá trị chuỗi (thoát `\` và `"`, bỏ xuống dòng nên không "thoát" khỏi khối `---` được); `strip_frontmatter` làm cho việc áp lại là idempotent.
- `split_by_h1`: tiêu đề `#` ngoài khối code/chessboard (theo dõi hàng rào ``` và ~~~); phần trước tiêu đề đầu thành `00-Mở đầu.md`. Tên chương `NN-<tiêu đề an toàn>.md` (đệm số 0 theo tổng chương).
- `apply_obsidian` chạy sau khi các đầu ra đã có và **trước** `_publish_output` (nên bản tự lưu/Dropbox đã có frontmatter). Chương nằm ở `out/chapters/` và chỉ vào zip (`_chapter_files` → `pipeline._zip_all(..., extra=...)`); zip được tạo cả khi chỉ có một tệp kết quả nếu có chương.
- `raw.md` (xem trước) **không** có frontmatter. Văn bản được tách là bản cuối (vn nếu có, không thì md).
- `jobs._atomic_write` giờ ghi với `newline="\n"` (Windows không đổi thành CRLF) để tệp kết quả/điểm lưu giống nhau trên mọi hệ điều hành.

## 6. Điểm cần lưu ý và hạn chế

- **Thuật ngữ chưa thử với AI thật.** Khối chỉ thị được kiểm bằng test prompt và engine giả, nhưng chưa quan sát `agy`/`claude`/Gemini có tuân thủ ra sao; ghi "chưa kiểm chứng" (AGENTS.md mục 5.7).
- Bảng thuật ngữ **dùng chung** mọi người dùng; ai sửa cũng ảnh hưởng người khác (chưa có phân quyền — S2).
- Ánh xạ thế cờ → trang không suy ra được nếu số khối trong `pages/` lệch văn bản chính (ví dụ tệp đã bị sửa tay ngoài công cụ): cột *Trang* hiện "—" và sửa chỉ ghi vào các tệp văn bản, không ghi điểm lưu trang.
- Đối chiếu trang chỉ cho tệp **PDF OCR** (có `pages/`). Với "gộp OCR+dịch" khung phải hiện **bản dịch** từng trang; với dịch riêng hiện **bản OCR chưa dịch** (không có bản dịch theo trang).
- Sửa FEN ghi đè trực tiếp tệp kết quả; trình duyệt có thể còn giữ bản tải cũ — tải lại tệp sau khi áp dụng.
- Tách chương chỉ theo `#` (không theo `##`); tài liệu không có tiêu đề `#` thì không tách (trạng thái ghi rõ).
- `gr.Dataframe` của Gradio dựng hàng ảo: không thể kiểm bằng cách đếm `<tr>` trong trình duyệt; test dùng handler `fen_select` với `gr.SelectData` giả.

## 7. Đường dẫn tham chiếu nhanh

| Muốn xem… | Mở |
|---|---|
| Liệt kê/sửa/xoay FEN, vẽ bàn cờ HTML | `fen_tools.py` |
| Ghi FEN vào mọi tệp, ánh xạ thế cờ → trang | `review.py` `apply_fen`, `_board_pages`, `load_boards` |
| Danh sách trang, ảnh trang | `review.py` `page_list`, `page_thumb` |
| Handler hai tab hiệu đính | `review_handlers.py` |
| Ảnh quân cờ cho bàn cờ HTML | `ui_theme.py` `piece_css`; CSS `.mid-fenboard` trong `assets/ui/app.css` |
| Bảng thuật ngữ, khối prompt | `glossary.py`; chèn ở `claude_ocr._glossary_block`, `claude_translate.translate_markdown_vn` |
| Frontmatter/tách chương | `obsidian.py`; `jobs.py` `apply_obsidian`, `rebuild_obsidian`, `_chapter_files` |
| Test | `tests_gui/test_fen_tools.py`, `test_review.py`, `test_review_handlers.py`, `test_glossary.py`, `test_obsidian.py`, `test_obsidian_jobs.py` |
