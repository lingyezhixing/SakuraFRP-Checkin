#!/bin/bash
set -e

# 加载 .env
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# 设置时区（默认上海）
export TZ=${TZ:-Asia/Shanghai}

# 确保日志目录存在
mkdir -p /app/logs

# 初始化随机时间（立即生成今天的）
if [ -n "$SCHEDULE_TIME" ]; then
    bash /app/generate_random_time.sh
fi

# 写入 cron 任务：每分钟执行 run_scheduled.sh
echo "* * * * * cd /app && bash /app/run_scheduled.sh >> /proc/1/fd/1 2>&1" > /etc/cron.d/checkin
chmod 0644 /etc/cron.d/checkin

# 前台运行 cron
exec cron -f
