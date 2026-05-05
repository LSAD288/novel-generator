#!/bin/bash
# 烽火南境小说生成器 - Docker 构建脚本 (Linux/Mac)

set -e

echo "=========================================="
echo "烽火南境小说生成器 - Docker 构建脚本"
echo "=========================================="
echo ""

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "错误: Docker 未安装"
    echo "请先安装 Docker: https://www.docker.com/products/docker-desktop"
    exit 1
fi

echo "Docker 已安装"
echo ""

# 构建 Docker 镜像
echo "正在构建 Docker 镜像..."
docker build -t novel-generator-builder .

if [ $? -ne 0 ]; then
    echo "错误: Docker 镜像构建失败"
    exit 1
fi

echo "Docker 镜像构建完成"
echo ""

# 运行容器进行构建
echo "开始构建 APK..."
echo "注意: 首次构建需要下载 SDK/NDK，可能需要 15-30 分钟"
echo ""

docker run --rm -v "$(pwd):/app" novel-generator-builder

if [ $? -ne 0 ]; then
    echo "错误: APK 构建失败"
    exit 1
fi

echo ""
echo "=========================================="
echo "构建完成!"
echo "APK 文件位于: bin/ 目录"
echo "=========================================="
