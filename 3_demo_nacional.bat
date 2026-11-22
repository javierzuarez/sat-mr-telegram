@echo off
chcp 65001 > nul
cd /d "%~dp0"
python demo_nacional.py
echo.
pause
