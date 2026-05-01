# SakuraFRP 自动签到脚本

自动完成 [natfrp.com](https://www.natfrp.com/user/) 每日签到，支持九宫格点选和滑块拖动两种验证码。

- **九宫格验证码**：下载原图一次裁出题目和格子 → AI 逐格视觉相似度比较 → 点击匹配格子
- **滑块验证码**：captcha-recognizer 深度学习库识别缺口（96%+ 准确率）→ pytweening 缓动函数模拟人类拖动轨迹
- **定时调度**：内置 sleep 循环，每天在目标时间 ±30 分钟随机执行

## 目录结构

```
.
├── main.py             # 入口：调度 + 浏览器自动化 + 签到流程
├── captcha.py          # 验证码：检测、九宫格求解、滑块求解
├── ai_service.py       # AI 服务：OpenAI 兼容 API 封装
├── logger.py           # 日志：按日期分割文件，同时输出控制台
├── account.txt         # 账号（第1行用户名，第2行密码）
├── .env                # 环境变量配置
├── state.json          # 登录状态缓存（自动生成）
├── env.example         # 环境变量示例
├── requirements.txt    # Python 依赖
├── Dockerfile          # Docker 构建
├── docker-compose.yml  # Docker Compose 配置
└── logs/               # 日志目录（自动生成）
```

## 准备工作

### 1. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 创建 `account.txt`

```
你的用户名
你的密码
```

### 3. 配置环境变量

复制 `env.example` 为 `.env` 并填写：

```env
# LLM API（OpenAI 兼容接口）
LLM_BASE_URL=http://127.0.0.1:8080/v1
LLM_API_KEY=your_api_key_here
LLM_MODEL_VISION=Qwen3.5-2B

# 定时执行（格式 HH:MM，设置后每天在 ±30 分钟随机执行）
SCHEDULE_TIME=08:00

# 可选代理
HTTP_PROXY=
```

## 运行方式

```bash
# 立即执行一次
python main.py --now

# 立即执行 + 调试截图
python main.py --debug --now

# 使用 SCHEDULE_TIME 环境变量定时执行
python main.py
```

### Docker

```bash
docker compose up -d
```

容器以 `restart: always` 运行，配合 `SCHEDULE_TIME` 环境变量实现每日自动签到。

## 验证码技术

### 九宫格点选

1. 从九宫格 `<img>` 的 `src` 下载原图（一张包含题目+格子的完整图）
2. 裁出底部条带（左侧 1/3）作为题目图，顶部正方形切分为 9 张格子图
3. AI 逐格视觉相似度比较（题目图 vs 格子图，无需文字标签）
4. 点击匹配格子 → 提交

### 滑块拖动

1. captcha-recognizer (YOLOv5) 识别缺口位置
2. 计算页面坐标偏移
3. pytweening 缓动函数模拟人类拖动：
   - 随机缓动函数（easeInOutQuad / easeOutQuad / easeInOutCubic）
   - ±5px 随机误差
   - 水平 ±1.5px / 垂直 ±2px 轨迹抖动
   - 50% 概率超调回调
   - 变速拖动（前快后慢）

## 日志

- 按日期分割：`logs/checkin_YYYY-MM-DD.log`
- 格式：`[时间戳] [级别] 消息`
- 自动清理 30 天前的旧日志

## 环境要求

- Python 3.8+
- Playwright Chromium
- 见 `requirements.txt`
