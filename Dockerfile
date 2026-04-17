FROM python:3.11-full

# 必要パッケージ
RUN apt-get update && apt-get install -y ffmpeg libportaudio2 && rm -rf /var/lib/apt/lists/*

# Ollama のインストール（公式スクリプトを使う）
RUN curl -fsSL https://ollama.com/install.sh | sh

# プロジェクトコピー & インストール
COPY . /app
WORKDIR /app
RUN pip install -e .

ENTRYPOINT ["flatercula"]

