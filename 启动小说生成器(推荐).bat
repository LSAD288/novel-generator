@echo off
chcp 65001 >nul
title 烽火南境小说生成器
cd /d "%~dp0"
echo ==========================================
echo    烽火南境小说生成器
echo ==========================================
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python安装！
    echo 请先安装Python 3.8或更高版本。
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] Python已安装
echo.

:: 检查必要的依赖包
echo [2/3] 检查依赖包...
python -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo [警告] 未检测到tkinter模块
    echo 某些功能可能无法正常使用
    echo.
)

python -c "import PIL" >nul 2>&1
if errorlevel 1 (
    echo [警告] 未检测到PIL模块，正在尝试安装...
    pip install Pillow -i https://pypi.tuna.tsinghua.edu.cn/simple
    echo.
)

python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo [警告] 未检测到requests模块，正在尝试安装...
    pip install requests -i https://pypi.tuna.tsinghua.edu.cn/simple
    echo.
)

echo [3/3] 依赖检查完成
echo.
echo ==========================================
echo    正在启动小说生成器...
echo ==========================================
echo.

:: 启动程序
python "烽火南境 .py"

:: 程序退出后的处理
echo.
echo ==========================================
echo    程序已退出
echo ==========================================
echo.
pause
