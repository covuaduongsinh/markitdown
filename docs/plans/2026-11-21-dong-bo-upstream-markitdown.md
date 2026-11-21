# Kế hoạch đồng bộ upstream microsoft/markitdown (2026-11-21)

> Mục tiêu: Gộp các cập nhật từ repo gốc `microsoft/markitdown` (`upstream/main` commit `ed17895`) vào nhánh `main` của fork Cờ vua Dương Sinh, kiểm thử và đồng bộ lên GitHub (`origin main`).

## 1. Bối cảnh & Hiện trạng

| Thành phần | Trạng thái hiện tại |
|---|---|
| Remote `origin` | `https://github.com/covuaduongsinh/markitdown.git` (nhánh `main` ở `74ebe22`) |
| Remote `upstream` | `https://github.com/microsoft/markitdown.git` (nhánh `main` ở `ed17895`) |
| Merge-base | `945314a45ddbe02935f2fd287b797dc0ba4a01e4` |
| Đoạn commit cần gộp | `945314a..ed17895` (23 commit từ upstream) |
| Phạm vi thay đổi của upstream | Chỉ nằm trong `.github/`, `.pre-commit-config.yaml`, `README.md` và `packages/*`. Không chạm vào 8 file mã nguồn của fork ở thư mục gốc. |
| Tài liệu fork | Đang có bộ tài liệu mới (`docs/*`, `AGENTS.md`, `CLAUDE.md`, `MEMORY.md`, `SKILLS.md`, `TECH.md`) và sửa đổi banner ở `README.md` cần commit. |

## 2. Danh sách commit upstream cần gộp (`945314a..ed17895`)

1. `d51937d` fix: bump youtube-transcript-api to >=1.2.3 for Python 3.14 support (#2407)
2. `b8f79c5` Bump versions or markitdown and markitdown-ocr (#2545)
3. `199fe8b` increase chunk size from 512 bytes to 64 KB for HTTP response reading (#1511)
4. `533ea57` fix(wikipedia): accept mobile (m.wikipedia.org) URLs in WikipediaConverter (#1850)
5. `53f38ea` fix: handle None sys.stdout.encoding in CLI output (#1656)
6. `5610ced` Add language parameter for the audio transcription (#1295)
7. `f70e637` optimize non-seekable stream buffering using shutil.copyfileobj (#1510)
8. `44f3a0e` Use frozenset for OMML direct tag lookup (#1919)
9. `1f9530a` fix(wikipedia): drop the site suffix from italicised titles (#2458)
10. `2b61a33` Consolidate tests by format and strengthen regression coverage (#2579)
11. `d9cae89` Replace local parser mocks with real conversion fixtures (#2586)
12. `64e3d67` Exercise real installed OCR plugin discovery in registration tests (#2588)
13. `18d48cb` Exercise real CLI file-type parsing and CU result formatting (#2592)
14. `331519d` Test PowerPoint missing text with real fixtures and shared vectors (#2594)
15. `7ccc027` Test MCP input errors with real conversions (#2597)
16. `4cc9fa1` Restore JSON regression coverage for late non-ASCII text (#2601)
17. `69e2087` Bump the magika dependency (#2722)
18. `c907c4c` Bump Mammoth dependency to >=1.12.2,<2 (#2729)
19. `f9affc8` Require certifi>=2026.10.19 for updated CA trust (#2730)
20. `3cf4750` Update Black, Pillow, and Windows ARM Cryptography baselines (#2731)
21. `21d9c1d` Bump versions, prior to point-release. (#2733)
22. `7482c09` feat(doc-intel): expose models, features, query fields, and structured output (#1913)
23. `1dccd83` Clarify hosted service requirements in README (#2845)
24. `3ae4f03` Override default SpeechRecognition endpoint (#2846)
25. `ed17895` fix: match ExifTool directories case-insensitively on Windows (#2837)

## 3. Nguyên tắc & Quy tắc merge

1. **Merge `--no-ff`, không rebase**: Giữ nguyên lịch sử các commit nhánh chính của fork.
2. **Quy tắc giải quyết xung đột**:
   - Trong `packages/`: Giữ nguyên mã của upstream (fork không sửa upstream).
   - Ở thư mục gốc (`README.md`): Giữ banner giới thiệu bản fork Cờ vua Dương Sinh ở đầu tệp, tích hợp các cập nhật mới của upstream ở thân tệp.
   - Các tệp mã nguồn riêng của fork: Giữ nguyên 100%.
3. **Kiểm thử sau merge**:
   - Chạy test roundtrip tiếng Việt/FEN: `.venv\Scripts\python.exe _test_translate_roundtrip.py`.
   - Smoke test import toàn bộ các module riêng của fork (`markitdown_gui`, `claude_ocr`, `claude_translate`, `chessboard_fen`, `ai_engine`, `infrastructure`, `claude_login_bridge`).
4. **Cập nhật tài liệu**: Cập nhật `MEMORY.md`, `TECH.md`, `docs/LICH-SU-PHAT-TRIEN.md` với commit và trạng thái mới.
5. **Đồng bộ GitHub**: Push lên `origin main`.

## 4. Các bước triển khai

- [x] Bước 1: Commit các tệp tài liệu và kế hoạch hiện tại để working tree sạch trước merge (`8d77815`).
- [x] Bước 2: Chạy `git merge upstream/main --no-ff -m "merge upstream/main: ed17895 fix ExifTool, DocIntel, dependencies, tests refactor"` (`a722ceb`).
- [x] Bước 3: Xử lý xung đột (tự động giải quyết sạch ở `README.md`, giữ banner fork ở đầu).
- [x] Bước 4: Chạy kiểm thử tự động (roundtrip test + smoke import test toàn bộ module: PASS 100%).
- [x] Bước 5: Cập nhật tài liệu `MEMORY.md`, `TECH.md`, `docs/LICH-SU-PHAT-TRIEN.md`.
- [x] Bước 6: Commit bổ sung tài liệu và push lên `origin main`.
