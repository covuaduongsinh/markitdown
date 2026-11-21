# Prompt triển khai — Nâng cấp giao diện và tính năng MarkItDown GUI

> Dùng cho một **phiên mới** của Claude Code mở tại `D:\code\markitdown`. Mỗi phiên làm **một giai đoạn**.
> Cách dùng: dán khối dưới đây, đổi số ở dòng `GIAI_DOAN`. Kế hoạch gốc:
> [`2026-11-21-nang-cap-giao-dien-va-tinh-nang.md`](2026-11-21-nang-cap-giao-dien-va-tinh-nang.md).

```text
GIAI_DOAN = 0

Nhiệm vụ: triển khai Giai đoạn {GIAI_DOAN} của kế hoạch
docs/plans/2026-11-21-nang-cap-giao-dien-va-tinh-nang.md trong repo này (fork markitdown của Cờ vua Dương Sinh:
ứng dụng web Gradio chuyển sách cờ vua scan sang Markdown).

Bối cảnh cần biết trước khi đọc mã:
- Giao diện trên production đang lệch thiết kế vì CSS bám vào DOM nội bộ của Gradio và Gradio không được ghim
  phiên bản (production 6.32.0, .venv 6.17.3). Kế hoạch mục 1 có bảng bằng chứng; mục 2 có các quyết định đã chốt
  (giữ Gradio, ghim phiên bản, CSS chỉ bám id/lớp do ta đặt, phông tự lưu trữ, công việc nền lưu đĩa, engine giả).
- Người dùng chính chạy những cuốn sách dài hàng trăm trang và thường theo dõi từ điện thoại, nên độ tin cậy
  (không mất kết quả khi rớt kết nối, dừng được thật) và bố cục di động quan trọng ngang với vẻ ngoài.

Đọc theo thứ tự trước khi sửa gì: AGENTS.md → MEMORY.md → kế hoạch (toàn bộ) → tài liệu tính năng liên quan trong
docs/tinh-nang/ (bảng ở AGENTS.md mục 2) → với Giai đoạn 1 đọc thêm design_handoff_markitdown_gui/README.md.

Phạm vi:
- Chỉ làm các mục G{GIAI_DOAN}.x. Thấy việc đáng làm ngoài phạm vi thì ghi vào cuối kế hoạch, mục "Phát hiện thêm",
  không tự làm.
- Nếu các giai đoạn trước chưa xong (bảng "Tiến độ" cuối kế hoạch), dừng lại và báo, đừng làm nhảy cóc: G1 cần G0,
  G2 cần G0, G3 cần G2.
- Các câu hỏi C1–C4 trong kế hoạch: C1 (gắn volume /data trên Dokploy) và C3 (giữ lịch sử 60 ngày) đã được chủ dự án
  chốt; C2, C4 dùng mặc định ghi trong kế hoạch nếu chưa có trả lời.
- Mục G2.9 (gắn volume trên Dokploy) là thay đổi hạ tầng production: chỉ làm khi chủ dự án đã duyệt nhánh và nói rõ
  cho phép lên production trong phiên đó; nếu chưa, chuẩn bị sẵn lệnh/các bước và để lại trong báo cáo.

Ràng buộc (lý do đi kèm để bạn xử lý đúng các trường hợp kế hoạch không lường trước):
- Làm trên nhánh feat/nang-cap-giao-dien (tạo từ main nếu chưa có). Không push, không merge vào main: push main làm
  Dokploy tự deploy lên production.
- Cây làm việc có thể đang có thay đổi chưa commit của chủ dự án (thường là MEMORY.md, docs/LICH-SU-PHAT-TRIEN.md,
  tệp trong docs/plans). Kiểm `git status --short --branch` trước; không revert, không gộp chúng vào commit của bạn
  ngoài phần bạn tự thêm. Hai tệp kế hoạch/prompt này nếu còn untracked thì commit chúng ở commit đầu tiên của nhánh.
- Không gọi agy, claude -p, Gemini hay Dropbox thật: chúng tiêu hạn mức thuê bao và ghi lên tài khoản của chủ dự án.
  Mọi kiểm thử luồng dùng engine giả MID_FAKE_ENGINE=1 (mục G0.2). Nếu đang làm G0 thì engine giả là thứ phải có
  trước khi kiểm bất kỳ luồng nào.
- Không sửa packages/ (mã upstream), không phá các hằng/định dạng ở AGENTS.md mục 4b. Ngoại lệ duy nhất đã được
  duyệt: thay việc dò chuỗi "gộp 1 bước" bằng cờ có cấu trúc (G0.3) — khi làm thì cập nhật luôn bảng 4b.
- Dùng .venv\Scripts\python.exe; đặt PYTHONUTF8=1 khi in tiếng Việt ra console.
- Kiến thức về API Gradio dễ lệch theo phiên bản. Trước khi dùng auth, gr.Timer, gr.BrowserState, theme .set(),
  cách phục vụ tệp tĩnh/phông: xem tài liệu hoặc mã nguồn của đúng bản gradio đã ghim trong .venv, đừng viết theo
  trí nhớ. Điều gì không chạy thử được thì ghi rõ "chưa kiểm chứng" trong báo cáo và tài liệu.
- Tham số mới thêm vào hàm có sẵn (ocr_pdf, run_agy_prompt…) phải tùy chọn và mặc định giữ hành vi cũ.
- Chuỗi giao diện và chú thích bằng tiếng Việt, tên hàm/biến tiếng Anh; chuỗi đưa vào HTML phải html.escape.

Cách làm:
- Mỗi mục G{GIAI_DOAN}.x một commit kiểu feat(ui): … / fix(ui): … / refactor(gui): … ; đánh dấu [x] mục đó trong
  kế hoạch ở cùng commit.
- Sau mỗi mục, chạy lại bộ kiểm ở kế hoạch mục 5 tương ứng. Với thay đổi giao diện: khởi động app bằng engine giả,
  mở http://127.0.0.1:7860 bằng công cụ trình duyệt bạn có, kiểm ở bề rộng 1366 / 768 / 375 px và cả hai theme,
  so với handoff. Nếu phiên không có công cụ trình duyệt, nói rõ điều đó và liệt kê chính xác những gì chủ dự án
  cần tự xem — đừng báo "đã kiểm giao diện" khi chưa nhìn thấy nó.
- Cập nhật tài liệu theo bảng ở AGENTS.md mục 6 (tài liệu tính năng, TECH.md khi thêm biến MID_*, RA-SOAT-RUI-RO.md
  đánh dấu mục đã xử lý kèm commit). Tài liệu tính năng mới theo mẫu hai tầng Phần A / Phần B.

Dừng lại và hỏi chủ dự án khi: phải xóa tệp/thư mục có sẵn; phải đổi prompt gửi AI ngoài mục G3.3; nâng phiên bản
gói làm test đang đạt bị hỏng mà không sửa được trong phạm vi; hoặc một mục trong kế hoạch mâu thuẫn với mã thực tế.

Kết thúc phiên:
- Cập nhật bảng "Tiến độ" trong kế hoạch (trạng thái, commit), MEMORY.md mục 2/3/5 và thêm một mục vào
  docs/LICH-SU-PHAT-TRIEN.md mục 4 (yêu cầu, đã làm, cách kiểm chứng, chưa làm).
- Báo cáo ngắn bằng tiếng Việt: đã xong mục nào (kèm commit), kết quả từng bước kiểm (đạt/không, kèm đầu ra khi
  không đạt), điều gì chưa kiểm chứng, việc chủ dự án cần tự làm (duyệt nhánh, đặt biến trên Dokploy, thử với AI thật).
```

## Thứ tự chạy gợi ý

| Phiên | `GIAI_DOAN` | Kết quả nhìn thấy được |
|---|---|---|
| 1 | `0` | Phiên bản ghim, engine giả, tệp đã tách, đăng nhập web bật được bằng biến môi trường |
| 2 | `1` | Giao diện đúng thiết kế, tiếng Việt hoàn toàn, dùng tốt trên điện thoại, trang Cài đặt riêng |
| 3 | `2` | Công việc nền: không mất kết quả khi rớt mạng, Dừng thật, khoảng trang, lịch sử 60 ngày trên volume bền |
| 4 | `3` | Bảng hiệu đính FEN, đối chiếu trang gốc, thuật ngữ, xuất Obsidian |
| 5 | `4` | Bảo mật, Docker, bảng trạng thái trung thực |

Giai đoạn 2 và 3 lớn: nếu một phiên không kịp, phiên sau dán lại đúng prompt — bảng "Tiến độ" và các ô `[x]` trong
kế hoạch cho biết làm tiếp từ đâu.
