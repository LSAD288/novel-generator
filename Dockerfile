FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FJ_HOST=0.0.0.0 \
    FJ_CLOUD=1 \
    NOVEL_NO_BROWSER=1 \
    FJ_DATA_DIR=/data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data

EXPOSE 8765

CMD ["sh", "-c", "FJ_PORT=${PORT:-8765} python server.py"]
