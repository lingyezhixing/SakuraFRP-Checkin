FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install-deps && \
    playwright install chromium && \
    rm -rf /var/lib/apt/lists/*

CMD ["python", "main.py", "--log-only"]
