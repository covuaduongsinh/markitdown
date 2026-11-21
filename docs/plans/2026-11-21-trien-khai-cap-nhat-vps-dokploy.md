# Kế hoạch Triển khai Cập nhật MarkItDown lên VPS qua Dokploy (2026-11-21)

> **Mục tiêu:** Cập nhật phiên bản mới nhất (đã đồng bộ upstream v0.1.9 và toàn bộ mã nguồn/tài liệu của fork) lên máy chủ VPS `217.15.160.118` đang chạy Dokploy (`markitdown.dsc.edu.vn`).

## 1. Thông tin Máy chủ & Dịch vụ

| Tham số | Giá trị |
|---|---|
| Địa chỉ VPS | `217.15.160.118` (Port: 22, User: `root`, SSH key: `C:\Users\duongsinh\.ssh\id_ed25519`) |
| Dokploy Panel | `https://dokploy.dsc.edu.vn` |
| Tên miền ứng dụng | `https://markitdown.dsc.edu.vn` |
| Tên dịch vụ Docker Swarm/Compose | `app-copy-primary-feed-r4ikwl` (hoặc tra cứu từ Docker trên VPS) |
| Commit triển khai | `269b3c4` (đã push lên `origin/main` trên GitHub `covuaduongsinh/markitdown`) |

## 2. Các bước thực hiện

- [x] **Bước 1: Kết nối SSH và kiểm tra hiện trạng trên VPS**
  - Đã kết nối tới `root@217.15.160.118` qua SSH key `id_ed25519`.
  - Xác định dịch vụ Swarm `app-copy-primary-feed-r4ikwl` (Dokploy app ID `Z3lolNBxq03oG1ilzCpyH`).
  - Container cũ chạy commit `74ebe22`.

- [x] **Bước 2: Kích hoạt cập nhật / Build lại ứng dụng**
  - Kích hoạt redeploy qua webhook API của Dokploy (`/api/deploy/Thw5XWNsnOMm-pPhM8nJ7`) với GitHub push event header.
  - Dokploy clone mã nguồn commit mới nhất `269b3c4` từ GitHub và build lại Docker image hoàn tất.

- [x] **Bước 3: Xác minh ứng dụng sau khi deploy**
  - Docker Swarm đã rolling-update sang container mới `2051a3a3b5bc` (`Running` ổn định).
  - Log container: `Running on local URL: http://0.0.0.0:7860`.
  - Kiểm tra `https://markitdown.dsc.edu.vn` phản hồi `HTTP/2 200 OK` (Uvicorn server).

- [x] **Bước 4: Cập nhật tài liệu & Trạng thái**
  - Cập nhật `MEMORY.md` và `docs/LICH-SU-PHAT-TRIEN.md`.
  - Commit và đồng bộ nhánh `main`.
