FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN apt-get update && \
    pip install --no-cache-dir -r requirements.txt && \
    playwright install-deps && \
    playwright install chromium && \
    rm -rf /var/lib/apt/lists/*

CMD ["python", "main.py", "--both"]
