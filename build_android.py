#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
烽火南境小说生成器 - Android APK 构建脚本
支持 WSL / Linux / Docker / Google Colab 多种构建方式
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


PROJECT_DIR = Path(__file__).parent.resolve()

REQUIRED_PY_FILES = [
    "main.py",
    "novel_core.py",
    "动态AI痕迹消除系统.py",
    "ultimate_ai_humanizer.py",
    "章节生成提示词辅助模块.py",
    "顶流作者人格建模辅助模块.py",
    "工具人角色检测系统.py",
]

REQUIRED_DIRS = [
    "books",
    "chapters",
    "database",
    "extracted_content",
]


def check_environment():
    if sys.platform.startswith('linux'):
        try:
            with open('/proc/version', 'r') as f:
                content = f.read().lower()
                if 'microsoft' in content or 'wsl' in content:
                    return 'wsl'
        except:
            pass
        return 'linux'
    elif sys.platform == 'darwin':
        return 'macos'
    elif sys.platform.startswith('win'):
        return 'windows'
    return 'unknown'


def check_required_files():
    missing = []
    for f in REQUIRED_PY_FILES:
        if not (PROJECT_DIR / f).exists():
            missing.append(f)
    return missing


def install_buildozer():
    print("正在安装 Buildozer...")
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "buildozer", "cython"], check=True)
    print("Buildozer 安装完成！")


def install_system_deps():
    print("正在安装系统依赖...")
    deps = [
        "python3-pip", "python3-venv", "git", "unzip",
        "openjdk-17-jdk", "autoconf", "automake", "libtool",
        "pkg-config", "zlib1g-dev", "libncurses5-dev",
        "libncursesw5-dev", "libtinfo5", "cmake",
        "libffi-dev", "libssl-dev", "libsqlite3-dev",
        "libjpeg-dev", "libpng-dev",
    ]
    subprocess.run(["sudo", "apt", "update"], check=True)
    subprocess.run(["sudo", "apt", "install", "-y"] + deps, check=True)
    print("系统依赖安装完成！")


def build_apk(release=False):
    print("开始构建 APK...")
    os.chdir(PROJECT_DIR)

    cmd = ["buildozer", "android", "release" if release else "debug"]
    try:
        result = subprocess.run(cmd, check=True)
        print("构建完成！")
        return True
    except subprocess.CalledProcessError as e:
        print(f"构建失败: {e}")
        return False


def copy_apk():
    bin_dir = PROJECT_DIR / "bin"
    if bin_dir.exists():
        apks = list(bin_dir.glob("*.apk"))
        if apks:
            output_dir = PROJECT_DIR / "output"
            output_dir.mkdir(exist_ok=True)
            for apk in apks:
                dest = output_dir / apk.name
                shutil.copy2(apk, dest)
                print(f"APK 已复制到: {dest}")
            return True
    print("未找到 APK 文件")
    return False


def generate_colab_notebook():
    notebook_path = PROJECT_DIR / "colab_build.ipynb"
    print(f"Colab 构建笔记本已存在: {notebook_path}")
    return notebook_path


def generate_docker_build():
    dockerfile_path = PROJECT_DIR / "Dockerfile"
    print(f"Dockerfile 已存在: {dockerfile_path}")
    return dockerfile_path


def main():
    print("=" * 60)
    print("烽火南境小说生成器 - Android APK 构建脚本 v2.0")
    print("=" * 60)

    env = check_environment()
    print(f"当前环境: {env}")

    missing = check_required_files()
    if missing:
        print(f"\n警告: 缺少以下必要文件:")
        for f in missing:
            print(f"  - {f}")
        print("\n部分功能可能不可用，但构建仍可继续。")

    if env == 'windows':
        print("\n当前在 Windows 环境下，Buildozer 需要 Linux 环境。")
        print("请选择构建方式:")
        print("  1. 使用 WSL (推荐)")
        print("  2. 使用 Docker")
        print("  3. 使用 Google Colab")
        print("  4. 仅检查配置")
        choice = input("\n请选择 (1-4): ").strip()

        if choice == '1':
            print("\n请在 WSL 终端中运行:")
            print(f"  cd {PROJECT_DIR}")
            print(f"  python3 build_android.py --wsl")
        elif choice == '2':
            generate_docker_build()
            print("\n请运行:")
            print(f"  docker build -t novel-genator .")
            print(f"  docker run -v {PROJECT_DIR}/bin:/app/bin novel-generator")
        elif choice == '3':
            generate_colab_notebook()
            print("\n请将 colab_build.ipynb 上传到 Google Colab 运行")
        elif choice == '4':
            print("\n配置检查:")
            print(f"  buildozer.spec: {'存在' if (PROJECT_DIR / 'buildozer.spec').exists() else '缺失'}")
            print(f"  main.py: {'存在' if (PROJECT_DIR / 'main.py').exists() else '缺失'}")
            print(f"  novel_core.py: {'存在' if (PROJECT_DIR / 'novel_core.py').exists() else '缺失'}")
            for f in REQUIRED_PY_FILES:
                exists = (PROJECT_DIR / f).exists()
                print(f"  {f}: {'存在' if exists else '缺失'}")
        return 0

    if env in ('wsl', 'linux'):
        try:
            install_system_deps()
            install_buildozer()
            if build_apk():
                copy_apk()
                print("\n构建成功！APK 文件位于: output/ 目录")
            else:
                print("\n构建失败！")
                return 1
        except Exception as e:
            print(f"错误: {e}")
            return 1

    return 0


if __name__ == "__main__":
    if '--wsl' in sys.argv:
        os.chdir(PROJECT_DIR)
        install_system_deps()
        install_buildozer()
        if build_apk():
            copy_apk()
    else:
        sys.exit(main())
