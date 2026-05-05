@echo off
chcp 65001 >nul
title 烽火南境小说生成器
cd /d "%~dp0"
echo ==========================================
echo    烽火南境小说生成器
echo ==========================================
echo.
echo 正在启动程序...
echo.
python "烽火南境 .py"
echo.
echo 程序已退出。
pause
