@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
if errorlevel 1 goto fail
python run_all.py --check-reference
if errorlevel 1 goto fail
echo 完成。结果位于 submission 和 docs。
pause
exit /b 0
:fail
echo 执行失败，请查看日志。不得使用旧结果文件。
pause
exit /b 1
