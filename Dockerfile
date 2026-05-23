FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 替换 APT 源为阿里云
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ && \
    playwright install-deps chromium && \
    playwright install chromium && \
    rm -rf /var/lib/apt/lists/*

CMD ["python", "main.py"]
