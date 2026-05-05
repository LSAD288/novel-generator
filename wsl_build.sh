#!/bin/bash
# 烽火南境小说生成器 - WSL 一键构建脚本
# 重启电脑后，在 WSL 终端中运行: bash wsl_build.sh

set -e

echo "============================================================"
echo "  烽火南境小说生成器 - WSL 一键构建 APK"
echo "============================================================"

PROJECT_DIR="/mnt/d/小说/烽火南境/小说生成器"
BUILD_DIR="$HOME/novel-generator-build"

echo ""
echo "[1/6] 更新系统并安装依赖..."
sudo apt update
sudo apt install -y \
    python3-pip python3-venv git unzip \
    openjdk-17-jdk autoconf automake libtool \
    pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev \
    libtinfo5 cmake libffi-dev libssl-dev \
    libsqlite3-dev libjpeg-dev libpng-dev

echo ""
echo "[2/6] 安装 Python 构建工具..."
pip3 install --upgrade pip
pip3 install buildozer cython

echo ""
echo "[3/6] 复制项目文件到构建目录..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

cp "$PROJECT_DIR/main.py" "$BUILD_DIR/"
cp "$PROJECT_DIR/novel_core.py" "$BUILD_DIR/"
cp "$PROJECT_DIR/buildozer.spec" "$BUILD_DIR/"
cp "$PROJECT_DIR/动态AI痕迹消除系统.py" "$BUILD_DIR/"
cp "$PROJECT_DIR/ultimate_ai_humanizer.py" "$BUILD_DIR/"
cp "$PROJECT_DIR/章节生成提示词辅助模块.py" "$BUILD_DIR/"
cp "$PROJECT_DIR/顶流作者人格建模辅助模块.py" "$BUILD_DIR/"
cp "$PROJECT_DIR/工具人角色检测系统.py" "$BUILD_DIR/"
cp "$PROJECT_DIR/新建章节模块完整提取.py" "$BUILD_DIR/" 2>/dev/null || true

cp -r "$PROJECT_DIR/books" "$BUILD_DIR/" 2>/dev/null || mkdir -p "$BUILD_DIR/books"
cp -r "$PROJECT_DIR/chapters" "$BUILD_DIR/" 2>/dev/null || mkdir -p "$BUILD_DIR/chapters"
cp -r "$PROJECT_DIR/database" "$BUILD_DIR/" 2>/dev/null || mkdir -p "$BUILD_DIR/database"
cp -r "$PROJECT_DIR/extracted_content" "$BUILD_DIR/" 2>/dev/null || mkdir -p "$BUILD_DIR/extracted_content"

echo ""
echo "[4/6] 验证文件完整性..."
cd "$BUILD_DIR"
echo "  构建目录文件列表:"
ls -la *.py 2>/dev/null || echo "  警告: 未找到 Python 文件"

echo ""
echo "[5/6] 开始构建 APK (首次构建需下载SDK，约15-30分钟)..."
buildozer android debug

echo ""
echo "[6/6] 复制 APK 到项目目录..."
mkdir -p "$PROJECT_DIR/output"
if [ -d "bin" ]; then
    cp bin/*.apk "$PROJECT_DIR/output/" 2>/dev/null || true
    echo "  APK 文件:"
    ls -la "$PROJECT_DIR/output/"*.apk 2>/dev/null || echo "  未找到 APK"
else
    echo "  构建目录中未找到 bin/ 目录"
fi

echo ""
echo "============================================================"
echo "  构建完成！"
echo "  APK 位置: $PROJECT_DIR/output/"
echo "============================================================"
