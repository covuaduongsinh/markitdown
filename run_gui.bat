@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   MarkItDown GUI - Co vua Duong Sinh
echo ============================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [LOI] Khong tim thay .venv\Scripts\python.exe
    echo.
    echo Hay tao virtual environment truoc, vi du:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip.exe install -e "packages/markitdown[all]"
    echo.
    pause
    exit /b 1
)

set "FOUND_AGY="
set "FOUND_CLAUDE="

where agy >nul 2>nul && set "FOUND_AGY=1"
if not defined FOUND_AGY (
    if exist "%LOCALAPPDATA%\agy\bin\agy.EXE" set "FOUND_AGY=1"
)

where claude >nul 2>nul && set "FOUND_CLAUDE=1"
if not defined FOUND_CLAUDE (
    if exist "%USERPROFILE%\.local\bin\claude.exe" set "FOUND_CLAUDE=1"
)

if not defined FOUND_AGY if not defined FOUND_CLAUDE (
    echo [CANH BAO] Khong tim thay CLI "agy" ^(Google Antigravity^) hoac "claude" ^(Claude Code^) trong PATH.
    echo App van chay duoc va convert file thuong binh thuong, nhung se KHONG OCR/dich
    echo duoc sach co vua ^(can it nhat 1 trong 2 CLI da dang nhap^).
    echo Xem GUI_README.md, muc "Yeu cau: 1 trong 2 AI Engine" de biet cach cai dat.
    echo.
)

echo Dang khoi dong MarkItDown GUI...
echo Mo trinh duyet tai: http://127.0.0.1:7860
".venv\Scripts\python.exe" "markitdown_gui.py"
pause
