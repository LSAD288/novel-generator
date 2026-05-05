# 烽火南境小说生成器 - Android APK 构建说明

## 重要说明

由于原项目使用了 tkinter（桌面GUI库），而 Android 不支持 tkinter，因此我创建了一个基于 Kivy/KivyMD 的移动端适配版本。

## 构建方法

### 方法一：使用 Buildozer（推荐，但需要 Linux 环境）

Buildozer 是 Kivy 官方推荐的 Android 打包工具，但需要在 Linux 环境下运行。

#### 在 Windows 上使用 WSL2 构建：

1. **安装 WSL2 和 Ubuntu**
   ```powershell
   wsl --install -d Ubuntu
   ```

2. **在 Ubuntu 中安装依赖**
   ```bash
   sudo apt update
   sudo apt install -y python3-pip python3-venv git unzip openjdk-17-jdk
   ```

3. **安装 Buildozer**
   ```bash
   pip3 install buildozer cython
   ```

4. **克隆/复制项目到 WSL**
   ```bash
   cd ~
   mkdir -p novel-generator
   # 将项目文件复制到 WSL 中
   ```

5. **运行构建**
   ```bash
   cd novel-generator
   buildozer android debug
   ```

6. **获取 APK**
   构建完成后，APK 文件将在 `bin/` 目录中生成。

#### 在 Linux/Mac 上构建：

1. **安装依赖**
   ```bash
   sudo apt update
   sudo apt install -y python3-pip python3-venv git unzip openjdk-17-jdk
   ```

2. **安装 Buildozer**
   ```bash
   pip3 install buildozer cython
   ```

3. **运行构建**
   ```bash
   buildozer android debug
   ```

### 方法二：使用 Docker（无需安装 Linux）

1. **安装 Docker**

2. **使用 Buildozer Docker 镜像**
   ```bash
   docker run -it --rm \
     -v $(pwd):/home/user/hostcwd \
     kivy/buildozer android debug
   ```

### 方法三：使用 Google Colab（云端构建，无需本地环境）

创建一个 Colab notebook，运行以下代码：

```python
# 挂载 Google Drive
from google.colab import drive
drive.mount('/content/drive')

# 安装依赖
!apt update
!apt install -y python3-pip git unzip openjdk-17-jdk
!pip3 install buildozer cython

# 上传项目文件到 /content/novel-generator
# 然后运行构建
%cd /content/novel-generator
!buildozer android debug

# 下载生成的 APK
from google.colab import files
files.download('bin/fenghuonanjing-1.0.0-arm64-v8a_armeabi-v7a-debug.apk')
```

## 项目文件说明

### 主要文件：

1. **main.py** - KivyMD 移动端入口文件
   - 基于 KivyMD 框架重新设计的移动端界面
   - 包含章节生成、改写、续写三大功能模块
   - 适配 Android 触摸操作

2. **buildozer.spec** - Buildozer 配置文件
   - 定义了应用名称、包名、版本等信息
   - 配置了 Android 权限和依赖库
   - 设置了构建参数

3. **烽火南境 .py** - 原桌面版主程序
   - 包含完整的业务逻辑和核心功能
   - 保留作为参考和备用

### 依赖模块：

- 动态AI痕迹消除系统.py
- 终极AI痕迹消除系统.py
- 章节生成提示词辅助模块.py
- 顶流作者人格建模辅助模块.py
- 工具人角色检测系统.py

## 功能说明

### 移动端版本功能：

1. **章节生成**
   - 选择写作风格（出版小说、网文、玄幻等）
   - 选择题材类型（古代言情、玄幻、都市等）
   - 输入章节大纲
   - 输入详细细纲（可选）
   - 输入特殊要求（可选）
   - 生成章节内容

2. **改写**
   - 选择改写风格
   - 选择改写方向（文学润色、风格转换、细节增强等）
   - 输入原文
   - 输入自定义要求
   - 生成改写后的内容

3. **续写**
   - 选择续写风格
   - 输入已有章节内容
   - 输入大纲（可选）
   - 输入特殊要求
   - 生成续写内容

4. **设置**
   - 配置 DeepSeek API 密钥
   - 查看模块加载状态
   - 应用信息

## 注意事项

1. **API 密钥**：首次使用需要在设置中配置 DeepSeek API 密钥

2. **网络权限**：应用需要网络权限来调用 AI 接口

3. **存储权限**：应用需要存储权限来保存生成的内容

4. **原项目依赖**：由于原项目使用 tkinter，在 Android 上无法直接运行，因此创建了 KivyMD 版本的替代界面

## 构建常见问题

### 1. Buildozer 构建失败

- 确保安装了所有系统依赖
- 检查 Java JDK 版本（推荐 OpenJDK 17）
- 清理构建缓存：`buildozer android clean`

### 2. APK 安装失败

- 确保启用了"允许安装未知来源应用"
- 检查 APK 架构是否与设备匹配

### 3. 应用闪退

- 检查是否正确配置了 API 密钥
- 查看 logcat 日志获取详细错误信息

## 技术栈

- **UI 框架**: Kivy + KivyMD
- **构建工具**: Buildozer
- **Python 版本**: 3.8+
- **目标平台**: Android 5.0+ (API 21+)

## 许可证

与原项目保持一致
