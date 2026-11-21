# Kế hoạch đồng bộ upstream microsoft/markitdown (2026-11-05)

> Mục tiêu: gộp các cập nhật của repo gốc `microsoft/markitdown` vào nhánh `main` của fork, kiểm thử, rồi đẩy lên GitHub (`origin main`).

## Mục tiêu

- Nhánh `main` ở local chứa toàn bộ commit mới của `upstream/main` (tính đến lần fetch mới nhất lúc thực thi).
- Không mất, không đổi hành vi mã riêng của fork (8 tệp Python ở thư mục gốc + tài liệu).
- Đẩy kết quả lên `origin main` trên GitHub theo yêu cầu của chủ dự án.

## Bối cảnh đã kiểm chứng (không cần đoán)

| Sự thật | Bằng chứng đã đọc trong phiên này |
|---|---|
| Remote `origin` là fork, remote `upstream` là repo gốc | `.git/config`: `covuaduongsinh/markitdown` và `microsoft/markitdown` |
| `main` local đang ở `74ebe22` (fix claude-login-bridge) | `.git/refs/heads/main`, `.git/logs/HEAD` |
| `origin/main` cũng ở `74ebe22` → local và GitHub đang khớp nhau | `.git/refs/remotes/origin/main` |
| `upstream/main` đã fetch tới `21d9c1d`, kèm tag `v0.1.9` (`5205b330`) | `.git/refs/remotes/upstream/main`, `.git/FETCH_HEAD` |
| Lần merge upstream gần nhất (`ba0a8ad`) chỉ gộp tới `945314a` → còn một đoạn commit upstream chưa gộp (`945314a..21d9c1d`) | `.git/logs/HEAD`, `.git/logs/refs/remotes/upstream/main` |
| Tiền lệ của fork là **merge** (2 lần: `46d5350`, `ba0a8ad`), không rebase | `.git/logs/HEAD`, `MEMORY.md` mục 4 |
| Fork cam kết không sửa lõi `packages/markitdown` | `AGENTS.md` mục 5, `MEMORY.md` mục 4 |
| Push lên `origin main` kích hoạt Dokploy deploy production | `MEMORY.md` mục 2 |

## Quyết định chính

1. **Merge `upstream/main` vào `main`, không rebase.** Lý do: giữ đúng tiền lệ 2 lần trước; lịch sử `main` đã push lên GitHub nên rebase sẽ viết lại lịch sử công khai.
2. **Giải quyết xung đột theo nguyên tắc: trong `packages/` giữ phía upstream, ở thư mục gốc giữ phía fork.** Lý do: fork không sửa lõi nên xung đột (nếu có) trong `packages/` hầu hết là do hai bên cùng tiến — phía upstream là đúng; mã fork ở gốc là tài sản riêng, không để upstream ghi đè.
3. **Không sửa hành vi trong cùng lượt.** Nếu merge làm lộ khác biệt hành vi upstream (API đổi, converter mới), chỉ ghi nhận vào tài liệu, không "tiện tay" sửa mã fork.
4. **Đẩy lên GitHub sau khi kiểm thử đạt.** Đã được chủ dự án yêu cầu rõ trong tin nhắn ("đồng bộ vào repo ở local và github"); chấp nhận hệ quả Dokploy tự deploy.

## Các bước thực hiện

1. **Kiểm tra cây làm việc.** Chạy `git status --short --branch`. Nếu có thay đổi chưa commit của chủ dự án → dừng lại và báo, không merge đè.
2. **Fetch mới nhất từ upstream.** Chạy `git fetch upstream --tags --prune`, ghi nhận vị trí mới của `upstream/main` (hiện đã biết là `21d9c1d`, có thể đã có commit mới hơn).
3. **Liệt kê và đánh giá cập nhật.** Chạy `git log --oneline <merge-base>..upstream/main` và `git diff --stat <merge-base>..upstream/main` (merge-base kỳ vọng là `945314a`). Mục đích: biết upstream đổi những gì và chạm vào thư mục nào, trước khi merge.
4. **Merge.** Chạy `git merge upstream/main --no-ff` với thông điệp theo mẫu cũ (`merge upstream/main: ...`). Giải quyết xung đột theo quyết định 2; sau khi xong, đọc lại từng hunk xung đột để chắc không mất mã fork.
5. **Kiểm thử.**
   - Test fork (không gọi AI): `.venv\Scripts\python.exe _test_translate_roundtrip.py` từ thư mục gốc.
   - Smoke import: nạp thử `markitdown_gui`, `claude_ocr`, `claude_translate`, `chessboard_fen`, `ai_engine`, `infrastructure` để bắt lỗi import do upstream đổi API.
   - Test upstream (`cd packages\markitdown && hatch test`) nếu merge chạm vào `packages/` — chạy khi khả thi, nếu quá nặng thì ghi rõ đã bỏ qua và vì sao.
   - Không chạy test Dropbox mạng và không gọi `agy`/`claude`/Gemini thật.
6. **Cập nhật tài liệu theo `AGENTS.md` mục 6.4** nếu merge làm đổi hành vi/diagram phiên bản: tài liệu `08-loi-markitdown` / `09-plugin-ocr-mcp-mau`, `TECH.md` (nếu phiên bản upstream đổi), `docs/LICH-SU-PHAT-TRIEN.md`, `MEMORY.md` (trạng thái + điều học được).
7. **Đẩy lên GitHub.** Chạy `git push origin main`, sau đó kiểm tra Dokploy deploy thành công (theo `docs/tinh-nang/10-trien-khai-docker-vps.md`).

## Kế hoạch kiểm chứng

| Bước | Lệnh / kiểm tra | Bằng chứng đạt |
|---|---|---|
| Cây sạch trước merge | `git status --short --branch` | Không có dòng thay đổi nào ngoài nhánh `main` |
| Merge đúng phạm vi | `git log --oneline --graph -5` sau merge | Thấy merge commit nối `main` cũ với `upstream/main` mới |
| Không mất mã fork | `git diff HEAD~1 --stat` + đọc hunk ở tệp gốc | Tệp gốc không bị xóa/sửa ngoài ý muốn |
| Fork vẫn chạy | Test roundtrip + smoke import | Exit 0, không `ImportError` |
| GitHub đồng bộ | `git status -sb` sau push | `main...origin/main` không lệch |

## Rủi ro và việc chưa kiểm chứng

- **R1 — Shell thực thi đang hỏng trong phiên này.** Công cụ `muse.powershell` liên tục lỗi `Access is denied (os error 5)` khi chạy lệnh git. Nếu lúc thực thi vẫn hỏng, tôi không thể chạy `fetch`/`merge`/`push` và sẽ dừng lại, đưa bộ lệnh thủ công để chủ dự án chạy. Đây là rủi ro cao nhất.
- **R2 — Xung đột merge trong `packages/`.** Kỳ vọng thấp vì fork không sửa lõi, nhưng nếu upstream refactor đúng chỗ fork từng merge thì vẫn có thể xung đột. Đã có nguyên tắc xử lý ở quyết định 2.
- **R3 — Push kích hoạt deploy production.** Đã biết trước và đã được yêu cầu; sau push cần xác minh web `https://markitdown.dsc.edu.vn` vẫn chạy.
- **Chưa kiểm chứng:** nội dung `git status` hiện tại; danh sách commit cụ thể trong đoạn `945314a..21d9c1d`; có commit upstream mới hơn `21d9c1d` hay không — cả ba sẽ được xác định ở bước 1–3 lúc thực thi.

## Ngoài phạm vi

- Không thêm tính năng, không sửa mã fork ngoài việc giải quyết xung đột merge.
- Không sửa trực tiếp mã trong `packages/` ngoài phạm vi merge.
- Không gọi AI (`agy`/`claude`/Gemini) hay Dropbox thật để thử.
- Không đổi remote, không xóa nhánh, không viết lại lịch sử.
