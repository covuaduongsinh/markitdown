# Tính năng 06 — Giao diện web Gradio và điều phối chuyển đổi

> Tài liệu này mô tả mã nguồn tại commit `2c1df67b44` (2026-09-27).
> Tệp chính: `markitdown_gui.py` (1.985 dòng), `pick_files.py` (24 dòng).
> Thiết kế giao diện gốc: `design_handoff_markitdown_gui/README.md` (bản HTML tham chiếu, Phương án A đã chốt).

---

# Phần A — Chức năng

## Người dùng làm gì trên màn hình

Màn hình hai cột dưới một thanh tiêu đề xanh navy (có huy hiệu **AI: Sẵn sàng / Cần đăng nhập**, nút **⚙ Cài đặt**, nút sáng/tối).
Trên điện thoại (< 780 px) là **một cột**, nút Chuyển đổi/Dừng **dính đáy màn hình**:

**Cột trái — nhập liệu và điều khiển**
1. **Hai thẻ nhập:** *Từ tệp* (vùng "Kéo-thả tệp vào đây", nhiều tệp, hoặc nút chọn tệp từ máy Windows; dưới vùng thả là
   **hàng đợi tệp** có loại, dung lượng, số trang và nút ×), *Từ URL* (YouTube, Wikipedia, RSS, trang web; có thể dịch và dùng
   cùng đường lưu/Dropbox như tệp). **Cài đặt hạ tầng & API** nay là **trang riêng** (nút ⚙ trên thanh tiêu đề).
2. **Chế độ xử lý** — bốn thẻ lớn: sách cờ vua ký hiệu Anh / Nga / Tây Ban Nha, hoặc tài liệu thường.
3. **Mức chất lượng** — ba nút: *Tiết kiệm*, *Cân bằng*, *Chính xác*. Chọn một nút là hệ thống tự đặt
   model, effort, DPI, số trang mỗi lần gọi, gộp/tách OCR-dịch.
4. **Nút "Chuyển đổi N tệp"** (vô hiệu khi chưa có tệp; đổi thành **⏹ Dừng** khi đang chạy, **▶ Chạy tiếp** khi cần) và **Tùy chọn
   nâng cao** (công tắc, model, effort, DPI, trang/lần, **Trang cần làm**).

**Cột phải — kết quả:** bảng trạng thái (chip *Chưa chạy / Đang xử lý / Xong n/n / Có lỗi / Đã dừng*, thanh tiến độ gradient
navy→vàng, danh sách từng tệp với "trang 6/12"), chip chọn xem từng tệp, tab *Xem trước* (bàn cờ vẽ thật từ FEN), tab *Mã .md*
(có nút **Sao chép Markdown**), tab *Lịch sử*, và danh sách tải về (meta số ký tự/số thế cờ, "Tải tất cả .zip", **Chạy lại**).

## Trải nghiệm đáng chú ý

- **Phản hồi tức thì:** bấm là hiện ngay chip "Đang xử lý…", thanh tiến độ và từng tệp (`OCR trang 7/120 · 43s`).
- **Tệp xong tới đâu hiện tới đó**, có thể tải ngay trong lúc các tệp sau còn chạy; công việc chạy nền nên đóng trình duyệt không mất việc
  (xem [13](13-cong-viec-nen.md)).
- **Bàn cờ hiện ngay trong xem trước** — khối ```` ```chessboard ```` được JavaScript thay bằng bàn cờ
  256 px với quân cờ SVG của Cờ vua Dương Sinh.
- **Sáng/tối** bằng nút trên thanh tiêu đề; nhớ lựa chọn.
- **Nhớ mọi thiết lập** giữa các lần mở (chế độ, preset, engine, thư mục, khoá/token, cấu hình Dropbox).

## Bảng preset

Giá trị thật từ `_PRESET_OPTS_AGY` (dòng 1348) và `_PRESET_OPTS_CLAUDE` (dòng 1357):

| Preset | Engine | Gộp OCR+dịch | Model OCR | Effort OCR | Model dịch | Effort dịch | DPI bàn cờ | Trang/lần |
|---|---|:-:|---|---|---|---|---:|---:|
| Tiết kiệm | Antigravity | ✅ | `gemini-4-hydrogen` | low | `gemini-4-hydrogen` | low | 250 | 2 |
| Cân bằng | Antigravity | ✅ | `gemini-3.8-flash` | auto | `gemini-3.8-flash` | low | 250 | 1 |
| Chính xác | Antigravity | ❌ | `gemini-4-argon` | high | `gemini-4-argon` | medium | 400 | 1 |
| Tiết kiệm | Claude Code | ✅ | `haiku` | low | `haiku` | low | 250 | 2 |
| Cân bằng | Claude Code | ✅ | `sonnet` | auto | `haiku` | low | 250 | 1 |
| Chính xác | Claude Code | ❌ | `opus` | high | `sonnet` | medium | 400 | 1 |

**Hành vi preset (G1.8, 2026-11-22):** chọn preset/đổi engine chỉ đặt *model, effort, DPI, trang/lần, gộp OCR+dịch* và dòng gợi ý
(`presets.preset_hint_text`, sinh từ bảng trên). Nó **không** đụng tới công tắc *Dịch tiếng Việt*, *Tự lưu*, *Tự tải về*, *Dropbox*
(trước đây bật lại cả bốn — B10); các công tắc này và preset được **lưu vào trình duyệt**. *Buộc OCR* chỉ đặt lại khi **đổi chế độ**.
Mã: `presets.py` (`_apply_preset`, `_on_mode_change`).

---

# Phần B — Kỹ thuật

## 10. Giao diện sau Giai đoạn 1 (2026-11-22)

**Nguyên tắc CSS (Q3).** `assets/ui/app.css` bám vào `elem_id`/`elem_classes` do ta đặt; thành phần gốc của Gradio đổi màu/bo góc/phông qua
`ui_theme.THEME` (`gr.themes.Base(...).set(...)`, có biến `*_dark`) và lớp `dark` trên `<body>` (JS đồng bộ với nút sáng/tối).
Các thẻ là `gr.Column(elem_classes=["mid-card", …])` — **không** dùng `gr.Group` vì Gradio gắn lớp lên cả hai phần tử lồng nhau
(viền kép, K5).

**Bẫy lớn nhất:** Gradio nhân mỗi quy tắc `css=` thành **một bản có tiền tố** `.gradio-container.gradio-container-X .contain …`.
Quy tắc bắt đầu bằng `body…` (ví dụ `body.x #id`) có bản có tiền tố **không bao giờ khớp** (`body` nằm ngoài `.contain`), còn bản có
tiền tố của quy tắc gốc lại có độ ưu tiên cao hơn → không thắng được. Vì vậy: màu theme tối đi qua **biến CSS** (`--c-link`,
`--c-link-strong`…), còn bật/tắt trang Cài đặt dùng lớp đặt **trên chính phần tử** (`#mid-settings.mid-open`, `#mid-workspace.mid-hide`).
Test `test_css_never_uses_body_prefixed_selectors_for_layout` chặn tái phạm.

**Phông tự lưu trữ (G1.2).** `assets/fonts/*.woff2` (Roboto 300/400/500/700/900, Roboto Condensed 400/600/700, Roboto Mono 400/500;
latin, latin-ext, vietnamese, cyrillic — cyrillic chỉ cho Roboto và Roboto Mono). `ui_theme.font_face_css()` sinh `@font-face` từ thư mục,
URL qua `/gradio_api/file=<đường dẫn thật>` (thư mục `assets` nằm trong `allowed_paths`). Không còn yêu cầu nào tới `fonts.googleapis.com`.
Phải dùng `gr.themes.Font("Roboto")` (không dùng chuỗi trơn trong danh sách phông: Gradio lỗi khi so sánh theme lúc `launch`).

**Vùng thả tiếng Việt (G1.3).** Gói ngôn ngữ của Gradio không có tiếng Việt; chữ tiếng Anh của `gr.File` bị ẩn bằng CSS
(`font-size:0` trên nút) và thay bằng `::before/::after`. Hộp thoại/danh sách tệp gốc bị ẩn (`#mid-file:has(.file-preview-holder)`);
hàng đợi `#mid-queue` (HTML từ `job_view.queue_html`) có nút ×, "Xóa hết", "+ Thêm tệp" — JS bấm hộ các nút gốc
(`button.label-clear-button`, nút có `aria-label` "Clear", `button.upload-container`). **Phụ thuộc vào các tên lớp/aria nội bộ đó** của Gradio 6.32.

**Trạng thái (G1.4).** `job_view.render_status_html(job)` → `gr.HTML#mid-status`; `idle_html()` là trạng thái rỗng; `message_html(text)` cho
thông báo ngắn. Phần trăm tiến độ: OCR chiếm 70% nếu có dịch riêng, ngược lại 100%.

**Kết quả theo tệp (G1.5).** `gr.Radio#mid-file-pick` (chip) chỉ hiện khi ≥2 tệp xong; chữ ký làm mới (`sig`) gồm cả tệp đang chọn.
"Chạy lại" (`on_rerun_job`): còn việc dở/trang lỗi thì chạy tiếp, không thì `JobManager.clone` tạo công việc mới.

**Trang Cài đặt (G1.6).** `gr.Column#mid-settings` nằm cạnh `#mid-workspace`; JS `midToggleSettings`; huy hiệu AI đọc
`data-mid-ai-ready` trong bảng hạ tầng (`infrastructure.render_infrastructure_html`).

**Di động (G1.7).** `@media (max-width:780px)`: `#mid-actionbar` `position:fixed`; thẻ chế độ chỉ hiện thẻ đang chọn (`.mid-modes.open`
mở danh sách), đầu thẻ chất lượng thành dòng tóm tắt (`.mid-quality-card.open`); bấm Chuyển đổi cuộn tới `.mid-col-right`; vùng bấm ≥ 44 px.
Kiểm bằng `iframe` rộng 375 px cùng nguồn (cửa sổ Chrome tự động không thu nhỏ được xuống 375 px): 0 vùng bấm < 40 px, không tràn ngang.

## 1. Cấu trúc tệp `markitdown_gui.py` (lịch sử — trước 2026-11-21)

| Khối | Dòng | Nội dung |
|---|---:|---|
| Import, thư mục xuất | 12–47 | `_OUTPUT_DIR = <tmp>/markitdown_gui_output` |
| Hàm tệp/ghi | 50–216 | `_safe_filename`, `_write_md`, `_write_fen_file`, `_zip_all`, `_download_panel`, `_autosave`, `_resolve_save_dir` |
| Lõi chuyển đổi | 219–475 | `_convert`, `_ocr_to_outputs`, `convert_file`, `convert_url`, chuyển nhãn → giá trị |
| Giao diện tĩnh | 484–981 | tài nguyên SVG, `_SCRIPT` (JavaScript), `CSS`, `TOPBAR_HTML`, `MODE_CARDS_HTML` |
| Điều phối | 986–1345 | `_translate_to_vn`, `_stream_job`, `on_pick_files`, `on_convert_files`, `on_convert_url`, `on_clear` |
| Preset và lưu tùy chọn | 1347–1452 | `_apply_preset`, `_load_prefs`, `_save_prefs` |
| `build_ui` | 1454–1968 | bố cục và nối sự kiện |
| Khởi chạy | 1971–1983 | `launch(...)` |

## 2. Luồng `on_convert_files` (dòng 1101)

Đây là generator trả bốn đầu ra `(preview, raw, downloads, status)` mỗi lần `yield`.

```mermaid
flowchart TD
    A["on_convert_files"] --> B["chuẩn hóa danh sách nguồn<br/>ưu tiên đường dẫn từ hộp thoại"]
    B --> C{"có tệp?"}
    C -- "không" --> C1["yield cảnh báo, kết thúc"]
    C -- "có" --> D["yield Đang khởi động"]
    D --> E["với mỗi tệp"]
    E --> F["_stream_job chạy convert_file trong thread nền<br/>yield tiến độ mỗi tối đa 5 giây"]
    F --> G["tính save_dir một lần"]
    G --> H["lưu VPS, đẩy Dropbox, đánh dấu tải về"]
    H --> I{"dịch riêng cần thiết?"}
    I -- "có" --> I1["_stream_job _translate_to_vn<br/>lưu, Dropbox, tải về cho _vn.md"]
    I -- "không" --> J
    I1 --> J{"chế độ cờ vua?"}
    J -- "có" --> J1["_write_fen_file: lưu, Dropbox, tải về _fen.txt"]
    J -- "không" --> K
    J1 --> K["thêm dòng vào tổng hợp, yield kết quả"]
    K --> E
```

> **Cập nhật 2026-11-21 (G2.4):** `_stream_job` và `on_convert_files` đã bị **thay bằng công việc nền** (`jobs.py`, `job_handlers.py`);
> mục này là lịch sử. Xem [13](13-cong-viec-nen.md). Luồng "Từ URL" vẫn chạy ngay trong sự kiện.

### 2.1 `_stream_job` — giữ kết nối sống (cũ)

Vì OCR một sách có thể chạy hàng chục phút, `_stream_job` (dòng 1026) chạy hàm nặng trong **thread nền
daemon** và cho generator chính `yield` một dòng tiến độ **ít nhất mỗi 5 giây** (`q.get(timeout=5)`), để
kết nối SSE của Gradio không rớt. Callback tiến độ đẩy `(i, n)` vào hàng đợi; các tin dồn lại được gộp,
chỉ giữ tin mới nhất. Kết thúc, hàm trả kết quả qua `StopIteration.value` (`return out.get("result")`),
còn lỗi trong thread được ném lại ở luồng chính.

Các `yield` tiến độ dùng `gr.skip()` cho ba ô đầu để **không gửi lại** toàn bộ xem trước — giảm tải trên
mạng.

### 2.2 Xác định thư mục lưu bản sao (`_resolve_save_dir`, dòng 205)

| Mục "Nơi lưu" | Tệp chọn bằng hộp thoại (đường dẫn thật) | Tệp kéo thả |
|---|---|---|
| Cùng thư mục với file gốc | thư mục của tệp gốc | **lùi về thư mục tùy chọn**, kèm ghi chú |
| Thư mục tùy chọn | thư mục tùy chọn | thư mục tùy chọn |

Lý do: trình duyệt chỉ đưa cho máy chủ bản sao đã tải lên ở đường dẫn tạm của Gradio, không có đường dẫn gốc.
`_autosave` (dòng 182) không ghi đè tệp có sẵn (thêm hậu tố `_2`, `_3`…).

### 2.3 Đặt tên tệp và tránh đè

`_write_md` và `_write_fen_file` thêm hậu tố `_2`, `_3`… khi tên đã nằm trong `used_paths` — chỉ là
`done_paths` của **lô hiện tại**. Với tệp `.md` ở chế độ thường, tên lấy từ `result.title` nếu tài liệu có tiêu đề
(dòng 237–239), nên hai tệp khác nhau có thể trùng tiêu đề.

## 3. Nút chọn tệp từ máy

`on_pick_files` (dòng 1079) chạy `pick_files.py` như **tiến trình con** (tkinter `askopenfilenames`, cửa sổ
luôn ở trên cùng, timeout 300 s). Lý do trong docstring của `pick_files.py`: tránh xung đột tkinter với luồng
nền mà Gradio dùng chạy event handler, và khởi động nhanh (không kéo `gradio`/`markitdown`). Chỉ hoạt động khi
`sys.platform == "win32"` và không có biến `DOCKER`; ngược lại trả thông báo hướng dẫn kéo thả.
Đường dẫn trả về được lưu vào `gr.State` (`picked_state`) và **ưu tiên hơn** tệp kéo thả (`raw_sources = picked_paths if picked_paths else file_paths`).
Kéo thả tệp mới (`file_in.change`) sẽ **xóa** lựa chọn từ hộp thoại.

## 4. Nhớ tùy chọn — `gr.BrowserState`

`prefs = gr.BrowserState({...})` (dòng 1812) lưu 13 khóa vào `localStorage` trình duyệt:
`preset, mode, dir, engine, api_key, claude_token, agy_token, auto_download, dropbox_token,
dropbox_app_key, dropbox_app_secret, dropbox_folder, dropbox_sync`.

Chuỗi khởi động khi tải trang (`demo.load`): `_load_prefs` → `_apply_preset` → JS `midSyncModeCards()`.
Mỗi thay đổi ở 13 thành phần kích hoạt `_save_prefs`. `_apply_preset` chạy lại mỗi khi đổi preset/chế độ/engine và
**đặt lại** `force_ocr = (là chế độ cờ vua)`, `translate_vn = True`, `autosave_on = True`,
`auto_download_on = True`, `dropbox_sync_on = True` cùng model/effort/DPI/trang mỗi lần — ghi đè lựa chọn tay.

## 5. Lớp JavaScript (`_SCRIPT`, dòng 516)

Nhúng vào `<head>`, dùng `MutationObserver` chạy lại mỗi lần DOM đổi:

| Hàm | Việc |
|---|---|
| `midToggleTheme` | đặt `data-mid-theme` trên `<body>`, lưu `localStorage["mid-theme"]` |
| `midSelectMode(idx)` | bấm thẻ chế độ (HTML) → `.click()` vào radio ẩn `#mid-mode-radio` để backend nhận |
| `midSyncModeCards` | đồng bộ class `active` của thẻ theo radio ẩn (cần khi giá trị đặt từ backend) |
| `midRenderBoards` | tìm `pre code` có class `chessboard` hoặc bắt đầu bằng `fen:` trong `#mid-preview`, thay bằng bàn cờ 256 px; quân là SVG nhúng dạng data URI (`window.MID_PIECES`) |
| `midTriggerAutoDownloads` | với `.dl-list[data-auto-download="1"]`, mỗi liên kết mới được bấm tự động, cách nhau 350 ms; nhớ URL đã tải trong `midDownloadedUrls` để không tải lặp |

Hai thứ này là **cầu nối HTML ↔ Gradio**: giao diện thiết kế dùng thẻ HTML tùy biến, còn logic nằm ở các
thành phần Gradio ẩn (`.mid-hidden`, `.mid-plumbing`).

## 6. Sự kiện trong `build_ui`

| Sự kiện | Kết quả |
|---|---|
| `preset/mode/engine_select .change` | `_apply_preset` → 13 đầu ra (`preset_outputs`) |
| `btn_file.click` | `_set_running(True)` → `on_convert_files` (`show_progress="full"`) → `_set_running(False)` |
| `btn_url.click`, `url_in.submit` | tương tự, gọi `on_convert_url` |
| `btn_stop.click` | `_set_running(False)`, `cancels=[proc, ev_url, ev_urls]` |
| `btn_clear.click` | `on_clear` (xóa kết quả và tệp đã chọn) |
| Các nút kiểm tra kết nối | xem [05](05-ha-tang-va-ket-noi.md), [07](07-dong-bo-dropbox.md) |

`enable_plugins` và `use_ocr` là hai `gr.Checkbox(visible=False)` cố định: `enable_plugins=False`,
`use_ocr=True`.

## 7. Khởi chạy (dòng 1971)

```
server_name = GRADIO_SERVER_NAME hoặc ("127.0.0.1" nếu Windows và không phải Docker, ngược lại "0.0.0.0")
server_port = PORT hoặc GRADIO_SERVER_PORT hoặc 7860
inbrowser   = GRADIO_INBROWSER (mặc định true nếu Windows và không Docker)
launch(theme=THEME, css=CSS, head=HEAD, allowed_paths=[_OUTPUT_DIR, _ASSETS_DIR])
```

`allowed_paths` cho phép Gradio phục vụ tệp kết quả qua `/gradio_api/file=<đường dẫn>`. Giao diện
không truyền `share=True`, không đặt xác thực.

## 8. Điểm cần lưu ý và hạn chế

**Thiết kế**
- Tệp 1.985 dòng gộp mọi thứ: hàm nghiệp vụ, hàng trăm dòng CSS/JS trong chuỗi Python, và bố cục. Muốn
  nhân bản giao diện với bộ nhận diện khác thì chủ yếu sửa các khối `CSS`, `TOPBAR_HTML`, `MODE_CARDS_HTML`, `assets/`.
- Khối `on_convert_files` lặp lại thủ công ba lần logic "lưu VPS + Dropbox + tải về" cho `.md`, `_vn.md`, `_fen.txt`.
- `_PRESET_HINTS` (dòng 977) còn **nội dung của thời chỉ có Claude** (`haiku · effort thấp…`, `sonnet · auto · dịch riêng`).
  Nó chỉ dùng làm giá trị khởi tạo của ô gợi ý; ngay khi `_apply_preset` chạy thì ô này bị ghi đè bằng giá trị đúng.
  `sonnet · auto · dịch riêng` cho preset Cân bằng cũng **lệch với thực tế** (`merge=True`, tức gộp OCR+dịch).
- Nhãn hiển thị Effort OCR có `Auto`, trong khi bước dịch không có `Auto`.

**Vận hành**
- **Nút Dừng không dừng thật:** `cancels=[…]` hủy sự kiện Gradio, nhưng công việc chạy trong **thread daemon
  riêng** (`_stream_job`) và các tiến trình `agy`/`claude` con vẫn tiếp tục cho tới khi xong hoặc hết
  timeout 600 s. (Suy ra từ mã, chưa chạy thử: thread không có cơ chế nhận tín hiệu hủy.)
- **Thư mục xuất dùng chung mọi người dùng:** `_OUTPUT_DIR` cố định trong thư mục tạm, tên tệp lấy từ tên
  sách; `markitdown_ketqua.zip` là **một tên cố định** ("mỗi lần gọi ghi đè"). Hai người dùng cùng lúc → tệp và
  zip đè lẫn nhau, và tệp của người này có thể tải được bằng đường dẫn `/gradio_api/file=…` của người kia.
- Thư mục `markitdown_gui_output` không bao giờ được dọn.
- Đầu ra "tải về" là liên kết `<a download>` tự bấm; trình duyệt có thể chặn tải nhiều tệp tự động.

**Bảo mật**
- **Không có xác thực.** Ai vào được URL đều dùng được phiên AI đã cấu hình trên máy chủ, và có thể ghi tệp
  `.md` vào thư mục bất kỳ mà tiến trình có quyền ghi thông qua ô "Thư mục tùy chọn trên VPS" (`_autosave`
  không giới hạn thư mục đích).
- **Khoá và token lưu thô trong `localStorage`** và truyền qua websocket của Gradio: API key Gemini, token
  Claude/Antigravity, Dropbox token, **App Secret**. XSS hoặc máy dùng chung sẽ lộ chúng.
- ~~`CSS`/`HEAD` nạp Google Fonts từ CDN~~ — **đã xử lý (G1.2)**: phông tự lưu trữ.

**Điều đáng ngờ**
- `_convert_btn_label(n)` đổi nhãn nút thành `Chuyển đổi N tệp`, nhưng `_on_files_change` và nút chọn tệp cùng
  ghi vào `btn_file`; chưa kiểm chứng nhãn có bị kẹt sau khi bấm Dừng/Xóa.

## 9. Đường dẫn tham chiếu nhanh

> Từ 2026-11-21 (G0.3) tệp đã tách; tìm theo tên hàm trong các tệp dưới đây.

| Muốn xem… | Mở |
|---|---|
| Luồng bấm nút | `markitdown_gui.py` `on_convert_files` |
| Quyết định OCR hay thường | `pipeline.py` `convert_file` (trả `ConvertResult`, có cờ `translated`) |
| Đưa kết quả ra thư mục tự lưu / Dropbox / tải về | `pipeline.py` `_publish_output` |
| Chạy nền + giữ kết nối | `markitdown_gui.py` `_stream_job` |
| Preset | `presets.py` `_PRESET_OPTS_AGY`, `_PRESET_OPTS_CLAUDE`, `_apply_preset` |
| Nhớ tùy chọn | `presets.py` `_load_prefs`, `_save_prefs`; `prefs` trong `build_ui` |
| JS (bàn cờ, theme, tự tải) | `assets/ui/app.js` (nạp bởi `ui_theme.HEAD`) |
| Đổi màu/thương hiệu | `assets/ui/app.css` (`ui_theme.CSS`), `ui_theme.TOPBAR_HTML` |
| Danh sách tải về (HTML) | `ui_render.py` `_download_panel` |
| Khởi chạy | `markitdown_gui.py` khối `if __name__ == "__main__"` |
| Thiết kế gốc | `design_handoff_markitdown_gui/README.md` |
