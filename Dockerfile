FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN apt-get update && \
    apt-get install -y --no-install-recommends cron && \
    pip install --no-cache-dir -r requirements.txt && \
    playwright install-deps && \
    playwright install chromium && \
    rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh run_scheduled.sh generate_random_time.sh run_checkin.sh ./
RUN chmod +x entrypoint.sh run_scheduled.sh generate_random_time.sh run_checkin.sh

ENTRYPOINT ["./entrypoint.sh"]
