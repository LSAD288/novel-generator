# 烽火南境小说生成器 - GitHub Actions 自动构建指南

## 快速开始（3步）

### 第1步：创建 GitHub 仓库

1. 访问 https://github.com/new
2. 输入仓库名称：`novel-generator`
3. 选择 **Public**（公开）或 **Private**（私有）
4. 点击 **Create repository**

### 第2步：推送代码到 GitHub

在本地项目目录执行以下命令：

```bash
cd "d:\小说\烽火南境\小说生成器"

# 初始化 git 仓库
git init

# 添加所有文件
git add .

# 提交
git commit -m "Initial commit"

# 添加远程仓库（将 YOUR_USERNAME 替换为你的 GitHub 用户名）
git remote add origin https://github.com/YOUR_USERNAME/novel-generator.git

# 推送代码
git push -u origin main
```

如果默认分支是 master：
```bash
git push -u origin master
```

### 第3步：查看构建结果

1. 打开你的 GitHub 仓库页面
2. 点击 **Actions** 标签
3. 等待构建完成（约15-30分钟）
4. 构建完成后，点击最新的 workflow run
5. 在 **Artifacts** 部分下载 APK 文件

或者等待自动发布的 Release，在 **Releases** 页面下载。

---

## 手动触发构建

如果推送后没有自动构建，可以手动触发：

1. 进入 GitHub 仓库
2. 点击 **Actions** 标签
3. 点击左侧的 **Build Android APK**
4. 点击右侧的 **Run workflow** → **Run workflow**

---

## 常见问题

### Q: 构建失败怎么办？

A: 点击失败的 workflow，查看日志。常见问题：
- 依赖下载超时：重新运行 workflow
- 内存不足：GitHub Actions 免费版有 7GB 内存限制，通常够用

### Q: 如何更新代码后重新构建？

A: 修改代码后再次执行：
```bash
git add .
git commit -m "Update code"
git push
```
GitHub Actions 会自动触发新的构建。

### Q: 构建好的 APK 在哪里下载？

A: 有两个地方可以下载：
1. **Actions** 页面 → 点击 workflow run → Artifacts
2. **Releases** 页面（自动发布）

---

## 文件说明

推送时需要包含的文件：

```
novel-generator/
├── .github/workflows/build-apk.yml  # GitHub Actions 配置
├── main.py                          # 主程序
├── novel_core.py                    # 核心逻辑
├── 动态AI痕迹消除系统.py            # AI痕迹消除
├── ultimate_ai_humanizer.py         # 终极AI痕迹消除
├── 章节生成提示词辅助模块.py         # 章节提示词
├── 顶流作者人格建模辅助模块.py       # 作者建模
├── 工具人角色检测系统.py            # 角色检测
├── buildozer.spec                   # Buildozer 配置
├── books/                           # 书籍数据
├── chapters/                        # 章节数据
├── database/                        # 数据库
└── extracted_content/               # 提取内容
```

---

## 构建时间

- 首次构建：约 15-30 分钟（需要下载 Android SDK/NDK）
- 后续构建：约 5-10 分钟（使用缓存）

---

## 需要帮助？

如果构建过程中遇到问题，可以：
1. 查看 GitHub Actions 日志
2. 检查 buildozer.spec 配置
3. 确保所有 Python 文件编码为 UTF-8
