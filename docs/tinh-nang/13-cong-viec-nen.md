# Tính năng 13 — Công việc nền: điểm lưu, Dừng thật, chạy tiếp, lịch sử

> Tài liệu này mô tả mã nguồn trên nhánh `feat/nang-cap-giao-dien` (Giai đoạn 2 của kế hoạch `docs/plans/2026-11-21-nang-cap-giao-dien-va-tinh-nang.md`).
> Tệp chính: `jobs.py`, `proc_control.py`, `job_view.py`, `job_handlers.py`; phần sửa ở `claude_ocr.ocr_pdf`, `claude_translate.translate_markdown_vn`, `pipeline.py`.
> Số dòng không ghi — hãy tìm theo tên hàm/lớp.

---

# Phần A — Chức năng

## Bài toán

Một cuốn sách scan dài hàng trăm trang chạy hàng chục phút. Trước đây kết quả chỉ nằm trong bộ nhớ cho tới khi cả tệp xong, nên rớt mạng, khóa màn hình điện thoại hay đóng tab ở phút 35 là **mất hết và tốn lại hạn mức AI**. Nút Dừng chỉ hủy sự kiện của giao diện, còn tiến trình `agy`/`claude` vẫn chạy ngầm.

## Người dùng thấy gì

- Bấm **Chuyển đổi** là tạo một **công việc nền**. Đóng trình duyệt, khóa điện thoại, hay thậm chí khởi động lại ứng dụng đều không làm mất việc: mở lại trang sẽ tự gắn vào công việc gần nhất.
- Mỗi trang OCR xong được **lưu ngay lên đĩa**. Trang lỗi được đánh dấu riêng.
- **⏹ Dừng** diệt thật các tiến trình AI (trong vài giây) và giữ lại mọi trang đã xong.
- **▶ Chạy tiếp** (sau khi dừng / lỗi / ứng dụng khởi động lại) và **🔁 OCR lại N trang lỗi** chỉ gọi AI cho các trang còn thiếu.
- Ô **Trang cần làm** (Tùy chọn nâng cao): `1-5, 20, 31-40` để chỉ OCR các trang đó; bên dưới hiện ước lượng "97 trang → **97 lượt gọi OCR**".
- Tab **🕘 Lịch sử**: danh sách công việc đã chạy, mở lại kết quả, tải `.zip`, xóa; hiển thị dung lượng đang dùng. Công việc cũ hơn **60 ngày** tự bị xóa.
- Tiêu đề tab trình duyệt đổi theo trạng thái (`⏳ Đang chạy`, `✅ Xong`, `⚠️ Xong, có trang lỗi`…); nút **🔔 Thông báo** trên thanh tiêu đề bật thông báo trình duyệt khi xong.

## Điều cần biết khi dùng

- Khóa/token (Gemini, Claude, Antigravity, Dropbox) **không bao giờ ghi vào đĩa**; chúng chỉ nằm trong RAM lúc công việc chạy. Vì vậy **Chạy tiếp** lấy lại từ các ô trên giao diện ở thời điểm bấm.
- Dịch riêng (không gộp OCR+dịch) cũng có điểm lưu theo từng đoạn: chạy tiếp không dịch lại đoạn đã dịch xong.
- Khi chạy tiếp, trang đã có điểm lưu được dùng nguyên (kể cả khi bạn đã đổi model giữa chừng).
- Chuyển **từ URL** vẫn chạy ngay trong sự kiện (không qua công việc nền, chưa có dịch/lưu VPS).

---

# Phần B — Kỹ thuật

## 1. Bố cục dữ liệu

`MID_DATA_DIR` (mặc định `<tmp>/markitdown_gui_data`; Docker: `/data`):

```
jobs/<job_id>/
  job.json              trạng thái, tùy chọn, tiến độ từng tệp — ghi nguyên tử (tệp tạm + os.replace)
  src/f01/<tên gốc>     bản sao tệp nguồn (để chạy tiếp được dù tệp tạm của Gradio đã bị dọn)
  f01/pages/0007.md     kết quả OCR một trang  (0007.err nếu lỗi; chỉ một trong hai tồn tại)
  f01/tr/<sha1>.md      kết quả dịch một đoạn
  f01/out/              <tên>.md · <tên>_vn.md · <tên>_fen.txt
  f01/raw.md            văn bản kết quả (xem trước / mở lại từ Lịch sử)
  ketqua.zip            gộp mọi tệp kết quả (≥2 tệp)
```

`job_id = secrets.token_urlsafe(9)`; tên thư mục **không** lấy từ tên tệp người dùng. `JobManager.abs_path` dùng `os.path.realpath` + `commonpath` để chặn `..`.

## 2. Vòng đời

Công việc: `queued → running → done | error | cancelled`. Tệp: `pending → running → done | error | cancelled`.

- `JobManager.submit(files, options, creds)` sao nguồn, ghi `job.json`, đưa vào hàng đợi. `MID_MAX_JOBS` (mặc định 1) luồng nền chạy lần lượt; luồng nghỉ sau 30 s rảnh và tự mở lại khi có việc.
- `_process_file` gọi lại **đúng `pipeline.convert_file`** (OCR → tùy chọn dịch riêng → `_fen.txt` → `_publish_output`), chỉ khác: thư mục xuất đặt riêng qua `pipeline._OUT_DIR_OVERRIDE` (ContextVar), và truyền `ocr_pdf_kwargs` (`pages`, `done_pages`, `on_page`, `cancel`).
- `on_page(page_no, text, error)` do `ocr_pdf` gọi ở luồng của công việc → ghi `NNNN.md`/`NNNN.err`. `ocr_pdf` bỏ qua các trang có trong `done_pages` (không render, không gọi AI) và chỉ ghép các trang thuộc tập `pages`.
- Trang OCR trả rỗng được tính là lỗi (`.err`), nên chạy tiếp sẽ thử lại.
- Khi khởi động, công việc `queued/running` còn sót trong `job.json` được đánh dấu `error` ("Ứng dụng khởi động lại giữa chừng…") và coi là chạy tiếp được.
- `resume()` đưa mọi tệp chưa `done` **hoặc** còn `pages_failed` về `pending` rồi xếp hàng lại; "Chạy tiếp" và "OCR lại trang lỗi" là cùng một thao tác, chỉ khác nhãn (`job_view.resume_label`).
- Dọn dẹp: `cleanup_old()` xóa công việc không chạy cũ hơn `MID_KEEP_DAYS` (khi khởi động và mỗi 24 giờ, luồng daemon `mid-cleanup`); `disk_usage()` cho tab Lịch sử.

## 3. Dừng thật (`proc_control.py`)

- `CancelToken` giữ cờ hủy + tập tiến trình con đang chạy. Token đi qua `contextvars`; `submit_in_context` nộp việc vào `ThreadPoolExecutor` kèm bản sao ngữ cảnh để luồng con thấy token.
- Ba nơi gọi CLI (`ai_engine.run_agy_prompt`, `claude_ocr._run_claude_ocr`, `claude_translate._call_claude`) dùng `run_cli(...)` thay `subprocess.run`: tiến trình được đăng ký, `cancel()` diệt **cả cây** (Windows `taskkill /F /T`, POSIX `killpg` TERM rồi KILL), `run_cli` ném `OperationCancelled`.
- `OperationCancelled` kế thừa **`BaseException`** để các khối `except Exception` sẵn có (ví dụ trong `convert_file`, `_translate_to_vn`) không nuốt nó.
- `_run_engine_ocr` và `_call_engine_translate` gọi `check_cancelled()` đầu hàm; engine giả ngủ bằng `proc_control.sleep` nên thức dậy ngay.
- `ocr_pdf` khi bị hủy: ngừng nộp trang mới, `pool.shutdown(wait=False, cancel_futures=True)`, rồi ném `OperationCancelled` (các trang đã xong đã ghi qua `on_page`).

## 4. Giao diện (`job_handlers.py`, `job_view.py`, `build_ui`)

- `on_start_job` nhận **đúng danh sách đầu vào cũ của `on_convert_files`** + `page_spec`; trả `[job_id] + JOB_OUTPUTS`.
- `JOB_OUTPUTS` = `status, preview, raw, downloads, sig_state, timer, btn_file, btn_stop, btn_resume, job_flag`.
- `gr.Timer(2 s)` chỉ bật khi có việc đang chạy (`render_job` trả `gr.Timer(active=…)`); `sig_state` giữ **chữ ký** (`job_view.signature`) — chữ ký không đổi thì `preview/raw/downloads` trả `gr.skip()` để khỏi gửi lại phần nặng.
- `job_state` là `gr.BrowserState` với `secret` **cố định**: mặc định Gradio mã hóa bằng khóa ngẫu nhiên mỗi lần khởi động nên sau redeploy trình duyệt sẽ không đọc lại được mã công việc.
- Mở lại trang/Lịch sử gọi `render_job(..., reattach=True)` → **không** bật tự tải về máy (tránh tải lại hàng loạt tệp cũ).
- `job_flag` là thẻ HTML ẩn (`#mid-job-flag`, `data-state/data-id/data-failed`); `assets/ui/app.js` (`midWatchJob`) đọc nó để đổi tiêu đề tab và bắn `Notification`.
- `allowed_paths` của `launch` gồm `jobs.data_dir()` — thiếu dòng này thì mọi liên kết tải về công việc nền trả **403**.

## 5. Điểm lưu khi dịch

`translate_markdown_vn(chunk_cache=…)`: khóa = `sha1(chess|chess_lang|nội dung đoạn)` (`chunk_cache_key`); chỉ lưu bản dịch **sạch** (qua kiểm placeholder và kiểm "chưa dịch"), không lưu bản dự phòng kèm cảnh báo. `DiskChunkCache` ghi `<sha1>.md`.

## 5b. Mở rộng ở Giai đoạn 3

Công việc đã xong còn có: **hiệu đính** (`review.py`: sửa FEN ghi lại cả điểm lưu trang để "Chạy tiếp" không mất sửa đổi; ảnh trang `pages/NNNN.jpg` tạo khi xem), **xuất Obsidian** (`JobManager.apply_obsidian`, tùy chọn `obsidian_frontmatter`, `obsidian_split`) và `JobManager.clone` cho nút "Chạy lại". `_atomic_write` ghi với `newline="\n"` để tệp giống nhau trên mọi hệ điều hành. Xem [14](14-hieu-dinh-ket-qua.md).

## 6. Điểm cần lưu ý và hạn chế

- **Đường Gemini REST không hủy được giữa lượt gọi** (`urllib`): Dừng không chờ nó (`shutdown(wait=False)`), nhưng yêu cầu HTTP đang bay vẫn chạy nốt tới khi xong/hết giờ và kết quả bị bỏ.
- **Chạy tiếp dùng lại trang cũ** kể cả khi đã đổi model/DPI/chế độ giữa chừng. Muốn làm lại từ đầu: tạo công việc mới.
- **Chạy lại một công việc đã tự lưu/Dropbox** sẽ lưu thêm bản `_2` ở đích (`_autosave` không ghi đè); Dropbox thì ghi theo logic của `upload_to_dropbox`.
- **Chưa có ảnh trang thu nhỏ** (`pages/NNNN.jpg`) — thuộc G3.2 (đối chiếu trang gốc), kế hoạch dự kiến nhưng chưa làm.
- Xóa công việc đang chạy bị từ chối; công việc `running` sau khi tiến trình chết được sửa trạng thái ở lần khởi động kế.
- `allowed_paths` trỏ cả `MID_DATA_DIR`: ai biết đường dẫn đầy đủ (gồm `job_id` ngẫu nhiên) tải được tệp. Chưa tách theo người dùng (S2).
- Công việc nền **một tài khoản dùng chung**: mọi người dùng cùng thấy Lịch sử (chưa có phân quyền).
- `BrowserState` của **prefs** (khóa, token…) vẫn dùng khóa ngẫu nhiên mỗi lần khởi động → sau redeploy các ô này có thể bị trống (chưa kiểm chứng; ghi ở "Phát hiện thêm" P6 của kế hoạch).
- Thông báo trình duyệt (`Notification`) **chưa kiểm chứng** (cần cử chỉ người dùng để xin quyền); phần đổi tiêu đề tab đã kiểm trong Chrome.

## 7. Đường dẫn tham chiếu nhanh

| Muốn xem… | Mở |
|---|---|
| Quản lý công việc, vòng đời, dọn dẹp | `jobs.py` `JobManager` |
| Xử lý một tệp (OCR → dịch → FEN → xuất) | `jobs.py` `JobManager._process_file` |
| Hủy tiến trình, token, `run_cli` | `proc_control.py` |
| Điểm lưu theo trang | `claude_ocr.py` `ocr_pdf` (`pages`, `done_pages`, `on_page`, `cancel`) |
| Điểm lưu theo đoạn dịch | `claude_translate.py` `chunk_cache_key`, `_translate_chunk`; `jobs.py` `DiskChunkCache` |
| Khoảng trang | `pipeline.py` `parse_page_ranges`, `estimate_ocr_calls` |
| Vẽ trạng thái/lịch sử | `job_view.py` |
| Handler giao diện | `job_handlers.py` |
| Nối sự kiện, Timer, BrowserState | `markitdown_gui.py` `build_ui` (khối "công việc nền") |
| JS đổi tiêu đề/thông báo | `assets/ui/app.js` `midWatchJob`, `midEnableNotify` |
| Test | `tests_gui/test_jobs.py`, `test_job_ui.py`, `test_fake_engine_flow.py` |
