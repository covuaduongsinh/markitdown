@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Dang khoi dong MarkItDown GUI...
echo Mo trinh duyet tai: http://127.0.0.1:7860
".venv\Scripts\python.exe" "markitdown_gui.py"
pause
