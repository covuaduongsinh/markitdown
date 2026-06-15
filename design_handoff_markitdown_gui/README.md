# Handoff: Giao diện MarkItDown — Cờ vua Dương Sinh

## Overview
Thiết kế lại giao diện cho công cụ **MarkItDown** đã tùy biến (bản trong `markitdown_gui.py`, chạy bằng **Gradio**): chuyển PDF / Word / Excel / PowerPoint / ảnh / URL sang **Markdown**, với trọng tâm là chế độ **OCR sách cờ vua** (nhận diện sơ đồ bàn cờ → block FEN, dịch ký hiệu Anh/Nga → tiếng Việt V/H/X/T/M) qua Claude Code, kèm dịch tiếng Việt và tự động lưu `.md`.

Mục tiêu giao diện: **đẹp, gọn gàng, hiệu quả, tiện dụng**, theo bộ nhận diện **Cờ vua Dương Sinh** (navy/“xanh than”, sạch, cao cấp; điểm nhấn vàng Sun cho nội dung cờ vua).

## About the Design Files
Các file trong gói này là **bản thiết kế tham chiếu viết bằng HTML** (Design Component — một biến thể React render runtime) — chúng minh hoạ *diện mạo* và *hành vi* mong muốn, **không phải code production để copy thẳng**.

Nhiệm vụ: **tái tạo các thiết kế này trong môi trường của codebase đích**. Codebase hiện tại là **Python + Gradio** (`markitdown_gui.py`). Có 2 hướng triển khai:
1. **Giữ Gradio**: tái tạo bằng `gr.Blocks` + CSS tùy biến (`css=...`) + `gr.HTML` cho các phần đặc thù (thẻ chế độ, bàn cờ FEN, danh sách kết quả). Phần lớn logic backend đã có sẵn — chỉ cần thay lớp trình bày (theme, layout, copywriting, màu).
2. **Tách frontend web** (React/Vue) gọi backend qua API: nếu muốn kiểm soát tương tác cao hơn (kéo-thả thật, animation, tiến độ realtime), dùng `MarkItDown.dc.html` làm đặc tả pixel.

Logic nghiệp vụ (chế độ, preset → tham số model/effort/DPI, luồng OCR/dịch, tự động lưu) **đã tồn tại** trong `markitdown_gui.py` / `claude_ocr.py` / `claude_translate.py`. Handoff này tập trung vào **lớp UI/UX**.

## Fidelity
**High-fidelity (hifi)** — màu, typography, spacing, bo góc, đổ bóng và tương tác đều là giá trị cuối. Hãy tái tạo **đúng pixel** bằng thư viện/pattern của codebase đích. Mọi giá trị hex/spacing/khoảng cách nêu dưới đây là chuẩn để bám theo.

---

## Screens / Views

### File thiết kế
- **`MarkItDown.dc.html`** — prototype tương tác chính (Phương án A đã chốt). Mở trực tiếp bằng trình duyệt.
- **`MarkItDown — Phương án bố cục.dc.html`** — trang so sánh 3 hướng bố cục (A/B/C). Chỉ để tham khảo định hướng; **A là bản chốt**.

Bố cục tổng thể của bản chốt: **2 cột** trong khung `max-width: 1340px`, `grid-template-columns: 412px minmax(0,1fr)`, `gap: 22px`, padding `24px 26px 60px`. Cột trái = nhập liệu & điều khiển; cột phải = xem trước/kết quả. Phía trên là **thanh tiêu đề navy dính (sticky)**.

---

### 1. Top bar (thanh tiêu đề)
- **Purpose**: nhận diện thương hiệu + chuyển theme sáng/tối.
- **Layout**: `position: sticky; top:0; z-index:20`, `display:flex; align-items:center; gap:14px`, padding `13px 26px`. Nền **navy `#2B3990`** ở **cả hai theme** (giữ thương hiệu nhất quán). Bóng `0 2px 14px rgba(21,29,73,.28)`.
- **Components**:
  - Logo symbol `assets/symbol-white.svg` (24×26px) + chữ **“MarkItDown”** (Roboto 900, 19px, letter-spacing −0.01em, màu trắng).
  - Dải phân cách `border-left: 1px solid rgba(255,255,255,.25)` + tagline “Cờ vua Dương Sinh — tài liệu & sách cờ → Markdown” (Roboto 300, 12.5px, opacity .85).
  - Cụm **badge định dạng** (đẩy về phải bằng `margin-left:auto`): pill nền `rgba(255,255,255,.14)`, viền `rgba(255,255,255,.22)`, radius 999px, padding `3px 10px`, 11px — “PDF”, “Word · Excel”, “Ảnh · URL”. Badge **“Sách cờ vua”** nổi bật: nền `rgba(246,185,43,.22)`, viền `rgba(246,185,43,.5)`, chữ `#FCE29A`, weight 600.
  - **Nút theme**: pill `rgba(255,255,255,.12)` + viền `rgba(255,255,255,.22)`, padding `6px 13px`, icon (mặt trăng khi đang sáng / mặt trời `#F6B92B` khi đang tối) + nhãn “Tối”/“Sáng”.

### 2. Cột trái — Panel nhập liệu
Card: nền `c.panel`, viền `1px solid c.border`, radius **18px**, bóng `c.shadow`, `overflow:hidden`.
- **Tabs nhập** (segmented): dải trên nền `c.inset`, padding 6px, 2 nút bằng nhau. Nút đang chọn: nền `c.panel`, chữ navy `#2B3990`, bóng `0 2px 6px rgba(21,29,73,.10)`, radius 9px. Nút tắt: trong suốt, chữ `c.subtext`. Mỗi nút có icon (thư mục / mắt xích) + nhãn “Từ tệp” / “Từ URL”.
- **Tab Từ tệp**:
  - **Khu kéo-thả**: `border:2px dashed c.borderStrong`, nền `c.dropBg`, radius 14px, padding `22px 18px`, căn giữa, con trỏ pointer. Bên trong: vòng tròn 46×46 nền `c.navySoft` chứa icon upload navy; tiêu đề “Kéo-thả tệp vào đây” (700, 14.5px); phụ đề “hoặc bấm để chọn — PDF, Word, Excel, PPT, ảnh” (12px, `c.subtext`).
  - **Hàng đợi tệp**: tiêu đề nhỏ “{n} tệp trong hàng đợi” (Roboto Condensed 700, 12px, uppercase, tracking .08em) + nút “Xóa hết”. Mỗi item: `display:flex; gap:11px`, padding `10px 12px`, nền `c.inset`, viền `c.border`, radius 11px — ô icon 34×34 (radius 9px, nền theo loại tệp), tên tệp (600, 13.5px, ellipsis), meta (“PDF sách cờ · 4.2 MB · 12 trang”, 11.5px), nút “×” xóa.
- **Tab Từ URL**: ô input có icon mắt-xích bên trái; placeholder “https://… hoặc link YouTube / Wikipedia”; viền `c.borderStrong`, nền `c.dropBg`, radius 12px, padding `13px 14px 13px 38px`. Dòng gợi ý 12px bên dưới.

### 3. Cột trái — Panel chế độ xử lý
Card như trên, padding 16px. Tiêu đề “CHẾ ĐỘ XỬ LÝ” (Roboto Condensed 700, 12px, uppercase). 3 thẻ xếp dọc, mỗi thẻ `display:flex; align-items:center; gap:12px`, padding `12px 13px`, radius 12px:
- **Trạng thái chọn**: nền `c.sunSoft`, viền `1.5px solid #F6B92B`, bóng `0 4px 14px rgba(246,185,43,.18)`; ô check tròn 20px nền `#F6B92B` có dấu ✓ màu `#2B2207`.
- **Trạng thái thường**: nền `c.inset`, viền `1px solid c.border`; ô tròn rỗng 18px viền `c.borderStrong`.
- Nội dung 3 thẻ:
  1. Icon quân mã trắng `assets/pieces/wn.svg` — **“Sách cờ vua — ký hiệu Anh”** — “Nhận diện bàn cờ → FEN · K/Q/R/B/N → V/H/X/T/M”.
  2. Icon quân mã đen `assets/pieces/bn.svg` — **“Sách cờ vua — ký hiệu Nga”** — “Кр/Ф/Л/С/К → V/H/X/T/M · xử lý figurine”.
  3. Icon tài liệu (lucide file-text) — **“Tài liệu thường”** — “Chuyển đổi gốc của MarkItDown + dịch thông thường”.

### 4. Cột trái — Panel chất lượng + chuyển đổi
Card padding 16px.
- Header: “MỨC CHẤT LƯỢNG” (Condensed 700 uppercase) + dòng hint động bên phải (vd “sonnet · auto · dịch riêng”).
- **Preset (segmented 3 nút)**: dải nền `c.inset`, viền `c.border`, radius 12px, padding 4px. Nút chọn: nền navy `#2B3990`, chữ trắng 700, bóng `0 4px 12px rgba(43,57,144,.30)`, radius 9px, `white-space:nowrap`. Nhãn: **“Tiết kiệm” / “Cân bằng” / “Chính xác”**.
- **Nút Chuyển đổi** (primary): full-width, radius 12px, padding 14px, Roboto 700 15px. Khi bật: nền `#2B3990`, chữ trắng, bóng `0 10px 26px rgba(43,57,144,.28)`, icon chevrons-right. Khi chạy: nền `c.inset`, chữ `c.faint`, spinner xoay, nhãn “Đang chuyển đổi…”. Khi không có tệp: disabled (nền `c.inset`, `cursor:not-allowed`). Nhãn động: “Chuyển đổi {n} tệp”.
- **Nút “Tùy chọn nâng cao”** (accordion): full-width, viền `c.border`, radius 11px, icon bánh răng + nhãn + chevron xoay 180° khi mở.
- **Panel nâng cao** (khi mở):
  - **4 công tắc** (toggle), mỗi cái: switch 38×22 (bật = navy `#2B3990`, núm trắng 18px trượt), tiêu đề 13px 600 + mô tả 11px:
    - “Buộc OCR toàn bộ” — “Bỏ lớp text rác trong PDF scan, OCR lại bằng Claude Code.”
    - “Dịch sang tiếng Việt” — “Tạo thêm tệp _vn.md. Ký hiệu cờ → V/H/X/T/M.”
    - “OCR + dịch gộp 1 bước” — “Mỗi trang vừa OCR vừa dịch — tiết kiệm ~30–40% hạn mức.”
    - “Tự động lưu .md ra đĩa” — “Lưu cạnh file gốc ngay khi mỗi tệp xong.”
  - Đường kẻ `1px c.border`.
  - **6 dropdown** (grid 2 cột, gap 11px), mỗi cái có nhãn 11px 600 + `<select>` tùy biến (appearance:none, padding `9px 28px 9px 11px`, viền `c.border`, nền `c.inset`, radius 9px) + mũi tên chevron tuyệt đối bên phải:
    - **Model OCR**: Haiku — nhanh / Sonnet — cân bằng / Opus — chính xác
    - **Effort OCR**: Thấp / Auto / Trung bình / Cao
    - **Model dịch**: Haiku — tiết kiệm / Sonnet / Opus
    - **Effort dịch**: Thấp / Trung bình / Cao
    - **DPI bàn cờ**: 250 — nhanh / 400 — nét nhất
    - **Trang / lần OCR**: 1 trang / 2 trang / 3 trang

### 5. Cột phải — Panel xem trước / kết quả
Card radius 18px, `min-height:640px`, `display:flex; flex-direction:column`.
- **Header**: tabs “Xem trước” / “Mã .md” (nút chọn nền navy chữ trắng radius 8px; nút tắt chữ `c.subtext`) + **chip trạng thái** đẩy phải:
  - Chưa chạy: “Chưa chạy” (xám `c.faint`).
  - Đang chạy: chấm vàng nhấp nháy + “Đang xử lý…” (màu `#D99A12`).
  - Xong: chấm teal + “Xong {n}/{n} tệp” (màu `#1FA98F`).
- **Trạng thái Idle** (chưa chạy): căn giữa — ô 78×78 nền `c.navySoft` + icon file-text navy; tiêu đề “Kết quả Markdown sẽ hiện ở đây” (800, 18px); mô tả hướng dẫn (14px).
- **Trạng thái Running**: spinner + “Đang chuyển đổi {n} tệp”; dòng phụ mô tả (chess: “OCR bằng Claude Code · nhận diện sơ đồ cờ → FEN · dịch sang tiếng Việt”). **Thanh tiến độ** cao 9px, nền `c.inset`, radius 999px, phần chạy `linear-gradient(90deg,#2B3990,#F6B92B)`, `transition:width .25s ease`. Danh sách từng tệp: icon trạng thái (chờ = vòng rỗng / đang chạy = spinner navy / xong = vòng teal `#DFF3EE` có ✓ `#1FA98F`), tên, chi tiết (“Đang OCR + nhận diện bàn cờ…”), tag bên phải (“trang 6/12” màu `#D99A12` / “Xong” màu `#1FA98F`).
- **Trạng thái Done — tab Xem trước**: render Markdown mẫu — H1 “Chương 2 — Khai cuộc Ý” (900, 28px); đoạn văn (15px, line-height 1.7, màu `c.body`); H2 “Thế cờ cơ bản”; **khối bàn cờ FEN** (xem mục Bàn cờ); dòng nước đi mono trong khung `c.inset`; bảng 2 cột (Nước đi / Ý tưởng) viền `c.border`, header viền dưới `2px c.borderStrong`.
- **Trạng thái Done — tab Mã .md**: `<pre>` Roboto Mono 12.5px, `white-space:pre-wrap`, hiển thị nguồn `.md` gồm cả fence ```` ```chessboard ```` + dòng `fen:` + bảng Markdown.
- **Footer tải về** (khi xong): nền `c.inset`, viền trên `c.border`, padding `14px 18px`. Tiêu đề “TỆP .MD KẾT QUẢ · {n} tệp” + nút “Chạy lại” (icon refresh, navy). Mỗi kết quả: icon file teal, tên (`khai_cuoc_y_vn.md`), meta (“12 trang · 6 sơ đồ → FEN · 41.600 ký tự”), nút **“Tải về”** pill navy chữ trắng có icon download.

### Bàn cờ FEN (component đặc trưng)
Render từ chuỗi FEN: lưới `8×8` (`display:grid; grid-template-columns:repeat(8,1fr)`), kích thước 188px ở xem trước. Ô sáng `#F6F2E4`, ô tối `#46B49A` (ô sáng khi `(hàng+cột) % 2 === 0`). Khung viền `5px solid #2B3990`, radius 8px, bóng `0 8px 22px rgba(43,57,144,.22)`. Quân cờ = ảnh trong `assets/pieces/` (kích thước ô × 0.82). Map ký tự FEN → file: `pP→ wp/bp`, `nN→wn/bn`, `bB→wb/bb`, `rR→wr/br`, `qQ→wq/bq`, `kK→wk/bk` (chữ HOA = trắng `w`, thường = đen `b`). FEN mẫu: `r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R`.

---

## Interactions & Behavior
- **Theme toggle**: đổi toàn bộ palette bề mặt (xem Design Tokens → 2 theme). Top bar luôn navy. Accent (navy/sun/teal/coral) không đổi giữa 2 theme. Không cần transition trên `background` (gây giật khi đổi theme — đã bỏ).
- **Tabs nhập**: chuyển giữa khu kéo-thả và ô URL.
- **Khu kéo-thả**: bấm để thêm tệp (prototype thêm tệp mẫu; bản thật mở hộp thoại như `pick_files.py` đã có). Hỗ trợ kéo-thả thật.
- **Hàng đợi**: xóa từng tệp (×) hoặc “Xóa hết”.
- **Chọn chế độ**: 1 trong 3 thẻ. Đổi chế độ → tự đặt lại `forceOcr` (bật cho sách cờ, tắt cho tài liệu thường) và tính lại tham số theo preset hiện tại.
- **Preset → tham số** (rất quan trọng, ánh xạ vào tham số có sẵn trong `markitdown_gui.py`):
  - **Tiết kiệm**: ocrModel `haiku`, ocrEffort `low`, trModel `haiku`, trEffort `low`, dpi `250`, pages `2`, merge `true`.
  - **Cân bằng** (mặc định): ocrModel `sonnet`, ocrEffort `auto`, trModel `haiku`, trEffort `low`, dpi `250`, pages `1`, merge `true`.
  - **Chính xác**: ocrModel `opus`, ocrEffort `high`, trModel `sonnet`, trEffort `medium`, dpi `400`, pages `1`, merge `false`.
  - Trong cả 3: `translateVn = true`, `plugins = false`, `autosave = true`, `forceOcr = (chế độ là sách cờ)`.
  - Người dùng vẫn chỉnh tay từng dropdown/công tắc trong panel nâng cao (ghi đè preset).
- **Chuyển đổi**: vô hiệu khi không có tệp/URL. Khi chạy: tiến độ theo từng trang của từng tệp; xong từng tệp thì cho tải ngay. Trong prototype mô phỏng bằng timer ~150ms/trang; bản thật nối với luồng streaming đã có (`_stream_job`, `on_convert_files`).
- **Kết quả**: tab Xem trước (Markdown render, có bàn cờ) ↔ tab Mã .md (nguồn thô). Nút “Tải về” mỗi tệp + “Chạy lại”.
- **Easing/motion**: `cubic-bezier(.22,1,.36,1)`, thời lượng 140–220ms; chỉ fade/nâng nhẹ, không bồng bềnh. Spinner `mid-spin .8s linear infinite`; chấm “đang xử lý” `mid-pulse 1s`.

## State Management
State của prototype (ánh xạ thẳng sang state Gradio/component thật):
- `theme`: `'light' | 'dark'`
- `inputTab`: `'file' | 'url'`; `url`: string
- `files`: mảng `{ id, name, type('chesspdf'|'pdf'|'doc'|'img'), pages, size }`
- `mode`: `'chess_en' | 'chess_ru' | 'general'`
- `preset`: `'saver' | 'balanced' | 'accurate'`
- `advancedOpen`: bool
- `opt`: `{ forceOcr, translateVn, merge, plugins, autosave, ocrModel, ocrEffort, trModel, trEffort, dpi, pages }`
- `running`, `done`, `progress` (0–100), `runFiles` (trạng thái từng tệp khi chạy), `results` (mảng `{ name, meta }`), `previewTab`: `'preview' | 'raw'`
- Chuyển trạng thái: chọn preset/mode → tính lại `opt`; bấm Chuyển đổi → `running=true`, lặp tiến độ → `done=true` + `results`. Mọi tham số `opt` đã có hàm xử lý tương ứng trong `markitdown_gui.py` (`_model_from_label`, `_effort_from_label`, `_dpi_from_label`, `_pages_from_label`…).

## Design Tokens
Nguồn gốc: `colors_and_type.css` của design system Cờ vua Dương Sinh. Các giá trị dùng trong thiết kế:

**Màu thương hiệu / accent (không đổi theo theme)**
- Navy `#2B3990` (primary), Navy deep `#1E2A6B`, Navy ink `#151D49`
- Sun `#F6B92B`, Sun deep `#D99A12`; on-sun (chữ trên vàng) `#2B2207`
- Teal `#1FA98F` (thành công), Teal soft `#DFF3EE`; Coral `#EE5A52`; Sky `#3DA0E3`
- Bàn cờ: ô sáng `#F6F2E4`, ô tối `#46B49A`, khung `#2B3990`

**Palette theme Sáng**
- bg `#F1F3F9` · panel `#FFFFFF` · inset `#F5F6FB` · dropBg `#FCFCFE`
- text `#16203A` · body `#3A4254` · subtext `#6E7486` · faint `#A2A7B6`
- border `#E3E5EC` · borderStrong `#D2D6E4` · navySoft `#E9EBF6` · sunSoft `#FDF1D2`
- shadow `0 12px 32px rgba(21,29,73,0.10)`

**Palette theme Tối**
- bg `#0E1430` · panel `#1A2356` · inset `#141C49` · dropBg `#141C49`
- text `#F2F4FB` · body `#D4D9EE` · subtext `#A6AED2` · faint `#7C84AC`
- border `rgba(255,255,255,0.10)` · borderStrong `rgba(255,255,255,0.20)` · navySoft `rgba(99,120,214,0.20)` · sunSoft `rgba(246,185,43,0.16)`
- shadow `0 16px 40px rgba(0,0,0,0.34)`

**Typography** — **Roboto** (body/UI) + **Roboto Condensed** (nhãn dày, overline) + **Roboto Mono** (FEN, mã, nước đi).
- H1 28px/900 · H2 19px/800 · tiêu đề panel/section overline 12px/700 uppercase tracking .08–.10em
- Body 15px/1.7 · UI 13–14px · caption 11–12px · weight 400/500/600/700/900
- letter-spacing tiêu đề lớn −0.01…−0.02em

**Spacing** (gốc 4px): 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64.
**Radius**: xs 4 · sm 8/9 · md 11–12 · lg 14 · xl 18 · pill 999.
**Bóng**: xem từng palette ở trên; thêm `0 10px 26px rgba(43,57,144,.28)` (nút navy), `0 8px 22px rgba(246,185,43,.34)` (glow vàng — chỉ cho điểm nhấn đặc biệt).

## Assets
Tất cả nằm trong `assets/` (đi kèm gói này, lấy từ design system Cờ vua Dương Sinh):
- `symbol-white.svg`, `symbol-navy.svg` — biểu tượng vương miện/mặt trời (logo).
- `logo-horizontal-navy.svg`, `logo-horizontal-white.svg` — lockup ngang (dự phòng).
- `pattern-tile-navy.svg`, `pattern-tile-white.svg` — họa tiết tessellation (dùng làm watermark; ở Phương án C dùng nền navy + pattern opacity ~0.06).
- `pieces/` — 12 quân cờ SVG (`wk wq wr wb wn wp` + `bk bq br bb bn bp`) cho bàn cờ FEN.
- **Icon UI**: bộ **Lucide** (stroke ~2px, rounded). Trong prototype được nhúng inline SVG; bản thật nên dùng package Lucide của codebase. Các icon đã dùng: upload, file/file-text, link, x, settings (gear), chevron-down, chevrons-right, check, refresh-cw, download, image, sun, moon.
- **Font**: Roboto / Roboto Condensed / Roboto Mono (Google Fonts hoặc self-host theo design system).

## Files
- `MarkItDown.dc.html` — prototype tương tác (Phương án A, bản chốt) — đặc tả chính.
- `MarkItDown — Phương án bố cục.dc.html` — 3 hướng bố cục để tham khảo.
- `assets/` — toàn bộ logo, pattern, quân cờ.
- Tham chiếu backend (trong dự án gốc, không nằm trong gói): `markitdown_gui.py` (UI + luồng), `claude_ocr.py` (OCR + nhận diện FEN), `claude_translate.py` (dịch VN), `pick_files.py` (hộp thoại chọn tệp), `chessboard_fen.py`.

> **Lưu ý**: các file `.dc.html` là **bản tham chiếu thiết kế**, không phải code production. Hãy tái tạo trong môi trường đích (giữ Gradio + CSS tùy biến, hoặc tách frontend) theo pattern/thư viện sẵn có của dự án.
