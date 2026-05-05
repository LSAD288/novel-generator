@echo off
chcp 65001
cls

echo ==========================================
echo 烽火南境小说生成器 - Docker 构建脚本
echo ==========================================
echo.

REM 检查 Docker 是否安装
docker --version >nul 2>&1
if errorlevel 1 (
    echo 错误: Docker 未安装或未启动
    echo 请先安装 Docker Desktop: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

echo Docker 已安装
echo.

REM 构建 Docker 镜像
echo 正在构建 Docker 镜像...
docker build -t novel-generator-builder .

if errorlevel 1 (
    echo 错误: Docker 镜像构建失败
    pause
    exit /b 1
)

echo Docker 镜像构建完成
echo.

REM 运行容器进行构建
echo 开始构建 APK...
echo 注意: 首次构建需要下载 SDK/NDK，可能需要 15-30 分钟
echo.

docker run --rm -v "%cd%:/app" novel-generator-builder

if errorlevel 1 (
    echo 错误: APK 构建失败
    pause
    exit /b 1
)

echo.
echo ==========================================
echo 构建完成!
echo APK 文件位于: bin\ 目录
echo ==========================================

pause
