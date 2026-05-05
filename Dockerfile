# 烽火南境小说生成器 - Docker 构建镜像
FROM kivy/buildozer:latest

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY . /app/

# 安装额外依赖
RUN sudo apt update && sudo apt install -y \
    python3-pip \
    python3-venv \
    git \
    unzip \
    openjdk-17-jdk \
    autoconf \
    automake \
    libtool \
    pkg-config \
    zlib1g-dev \
    libncurses5-dev \
    libncursesw5-dev \
    cmake \
    libffi-dev \
    libssl-dev

# 安装 Python 依赖
RUN pip3 install --upgrade pip
RUN pip3 install buildozer cython

# 设置权限
RUN sudo chown -R user:user /app

# 默认命令
CMD ["buildozer", "android", "debug"]
