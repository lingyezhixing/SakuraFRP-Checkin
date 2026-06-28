# SakuraFRP 自动签到脚本

自动完成 [natfrp.com](https://www.natfrp.com/user/) 每日签到，支持九宫格点选和滑块拖动两种验证码。

- **九宫格验证码**：下载原图一次裁出题目和格子 → AI 识别题目物体 → 逐格二分类匹配 → 点击提交
- **滑块验证码**：captcha-recognizer (YOLOv5) 识别缺口 → pytweening 缓动函数模拟人类拖动轨迹
- **定时调度**：内置 sleep 循环，每天在目标时间 ±30 分钟随机执行

## 目录结构

```
.
├── main.py             # 入口：调度 + 浏览器自动化 + 签到流程
├── captcha.py          # 验证码：检测、九宫格求解、滑块求解
├── ai_service.py       # AI 服务：OpenAI 兼容 API 封装（视觉识别 + 逐格分类）
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
# 本地模型可填任意非空值，如 skip
LLM_API_KEY=your_api_key_here
LLM_MODEL=MiniCPM-V-4.6

# 定时执行（格式 HH:MM，设置后每天在 ±30 分钟随机执行）
SCHEDULE_TIME=08:00

# 时区
TZ=Asia/Shanghai

# 可选代理
HTTP_PROXY=
```

## VLM 模型选择

推荐使用本地部署的小参数模型，服务更稳定。本项目已针对小模型深度优化，**MiniCPM-V-4.6** 等 1B 规模的小模型也具有相当高的识别成功率，对硬件要求不高。配合内置重试机制，可实现稳定解析，每次签到的平均验证码轮次消耗小于 2。

### 推荐模型

| 模型 | 参数量 | 说明 |
|------|--------|------|
| MiniCPM-V-4.6 | ~1B | 首选推荐，经过充分测试 |
| 其他 OpenAI 兼容的视觉模型 | 任意 | 只要兼容 `/v1/chat/completions` 接口均可使用（包括闭源模型如 GPT-4o 等） |

## 运行方式

```bash
# 立即执行一次
python main.py --now

# 调试模式（立即执行 + 截图保存到 debug/ 目录）
python main.py --debug

# 使用 SCHEDULE_TIME 环境变量定时循环执行
python main.py
```

### Docker

```bash
docker compose up -d
```

容器以 `restart: always` 运行，配合 `SCHEDULE_TIME` 环境变量实现每日自动签到。

## 工作流程

### 签到主流程

1. 启动 Chromium 浏览器（headless，支持代理）
2. 访问签到页面，使用账号密码登录（自动保存 `state.json` 缓存状态）
3. 关闭"已满18岁"弹窗（如有）
4. 检测是否已签到 → 点击签到按钮 → 如出现验证码则进入验证码处理
5. 验证码最多重试 5 轮，每轮检测类型后分别处理

### 九宫格点选

1. 从九宫格 `<img>` 的 `src` 下载原图（一张包含题目 + 格子的完整图）
2. 裁出底部条带左侧 ~1/3 作为题目图，顶部正方形切分为 9 张格子图
3. AI 视觉识别题目图中的目标物体名称
4. AI 对每个格子进行二分类（"图片中是否有【目标】？只回答：是或否"）
5. 点击所有匹配格子 → 点击提交

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
- 格式：`[时间戳] [级别] 消息`（级别：DEBUG / INFO / SUCCESS / ERROR）
- 控制台简写前缀：`[DBG]` / `[INF]` / `[OK]` / `[ERR]`
- 自动清理 30 天前的旧日志

## 环境要求

- Python 3.8+
- Playwright Chromium
- 见 `requirements.txt`
