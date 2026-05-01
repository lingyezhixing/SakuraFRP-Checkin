import sys
import os
import time
import random
import traceback
from pathlib import Path
from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright

from ai_service import AIService
from logger import CheckinLogger, clean_old_logs
from captcha import detect_captcha_type, solve_grid_captcha, solve_slider_captcha, _is_visible

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# ── 路径与常量 ──────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent
DOMAIN = "www.natfrp.com"
TARGET_URL = f"https://{DOMAIN}/user/"
ACCOUNT_FILE = BASE_DIR / "account.txt"
STATE_FILE = BASE_DIR / "state.json"
ALREADY_SIGNED_TEXT = "今天已经签到过啦"


# ── 工具函数 ────────────────────────────────────────────────

def load_account(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(lines) < 2:
        raise ValueError("account.txt 格式错误：需两行分别存放用户名和密码")
    return lines[0], lines[1]


def find_signed_text(page, timeout=3000):
    try:
        loc = page.get_by_text(ALREADY_SIGNED_TEXT).first
        if loc.is_visible(timeout=timeout):
            return loc
    except Exception:
        pass
    return None


# ── 登录 ────────────────────────────────────────────────────

def login(page, username: str, password: str, logger: CheckinLogger):
    if "login" not in page.url and not _is_visible(page.locator("#username"), timeout=2000):
        logger.info("已登录状态")
        return True

    logger.info("需要登录")
    try:
        page.fill("#username", username)
        page.fill("#password", password)
        page.click("#login")
        page.wait_for_selector("text=账号信息", timeout=10000)

        # 保存登录状态
        page.context.storage_state(path=STATE_FILE)
        logger.success("登录成功")
        return True
    except Exception as exc:
        logger.error(f"登录失败: {exc}")
        return False


# ── 18岁弹窗 ────────────────────────────────────────────────

def dismiss_age_popup(page, logger: CheckinLogger):
    try:
        btn = page.get_by_text("是，我已满18岁")
        if btn.is_visible(timeout=3000):
            logger.debug("检测到18岁确认弹窗，点击确认")
            btn.click()
            time.sleep(1)
    except Exception:
        pass


# ── 签到主流程 ──────────────────────────────────────────────

def run_checkin(debug=False):
    clean_old_logs(BASE_DIR, days=30)
    logger = CheckinLogger(BASE_DIR)
    logger.info("脚本启动")

    # debug 目录
    debug_dir = None
    if debug:
        debug_dir = BASE_DIR / "debug" / datetime.now().strftime("%Y-%m-%d_%H%M%S")
        debug_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"调试目录: {debug_dir}")

    # 初始化
    try:
        ai = AIService()
    except Exception as exc:
        logger.error(f"AI 服务初始化失败: {exc}")
        return

    try:
        username, password = load_account(ACCOUNT_FILE)
    except Exception as exc:
        logger.error(f"加载账号失败: {exc}")
        return

    with sync_playwright() as p:
        browser = _launch_browser(p)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 900})

        # 访问签到页
        try:
            page.goto(TARGET_URL, timeout=30000)
            logger.debug(f"页面加载完成: {page.url}")
            if debug_dir:
                page.screenshot(path=str(debug_dir / "01_page_loaded.png"))
        except Exception as exc:
            logger.error(f"页面访问失败: {exc}")
            browser.close()
            return

        # 登录
        if not login(page, username, password, logger):
            browser.close()
            return
        if debug_dir:
            page.screenshot(path=str(debug_dir / "02_after_login.png"))

        # 18岁弹窗
        dismiss_age_popup(page, logger)

        # 签到
        _do_checkin(page, ai, logger, debug_dir)

        if debug_dir:
            page.screenshot(path=str(debug_dir / "05_final_state.png"))
        logger.info("脚本运行结束")
        browser.close()


def _launch_browser(p):
    proxy_url = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    kwargs = {"headless": True, "slow_mo": 100}
    if proxy_url:
        kwargs["proxy"] = {"server": proxy_url}
    return p.chromium.launch(**kwargs)


def _do_checkin(page, ai, logger, debug_dir):
    # 已签到？
    if find_signed_text(page):
        logger.success("今日已签到")
        return

    # 找签到按钮
    sign_btn = page.get_by_text("点击这里签到")
    if not _is_visible(sign_btn, timeout=3000):
        logger.error("未找到签到按钮")
        return

    logger.info("点击签到按钮...")
    sign_btn.click()
    if debug_dir:
        page.screenshot(path=str(debug_dir / "03_after_click_sign.png"))

    # 等待签到完成或验证码出现
    sign_success = _wait_and_handle_captcha(page, ai, logger, debug_dir)

    if sign_success:
        logger.success("签到完成")
    else:
        logger.error("签到失败：验证码处理失败或超时")


def _wait_and_handle_captcha(page, ai, logger, debug_dir):
    # 第一阶段：轮询等待签到完成或验证码出现（最多30秒）
    captcha_appeared = False
    sign_success = False

    # 前15秒：每0.5秒检查一次
    for i in range(30):
        time.sleep(0.5)
        if find_signed_text(page, timeout=500):
            logger.success("签到完成（无需验证码）")
            return True

    # 验证码检测
    captcha_type = detect_captcha_type(page, logger)
    if captcha_type != "unknown":
        captcha_appeared = True
        logger.info(f"验证码已出现: {captcha_type}")
    else:
        # 继续等15秒，每5秒检查一次
        for rnd in range(3):
            time.sleep(5)
            if find_signed_text(page, timeout=500):
                logger.success("签到完成（无需验证码）")
                return True
            captcha_type = detect_captcha_type(page, logger)
            if captcha_type != "unknown":
                captcha_appeared = True
                logger.info(f"验证码已出现: {captcha_type}")
                break

    if debug_dir:
        page.screenshot(path=str(debug_dir / "04_captcha_state.png"))

    if not captcha_appeared:
        logger.error("30秒内未检测到验证码")
        # 最后给2次机会
        return _try_solve_captcha_loop(page, ai, logger, attempts=2)

    return _try_solve_captcha_loop(page, ai, logger, attempts=3)


def _try_solve_captcha_loop(page, ai, logger, attempts):
    for attempt in range(1, attempts + 1):
        logger.debug(f"第 {attempt}/{attempts} 次检查")

        if find_signed_text(page, timeout=1000):
            return True

        captcha_type = detect_captcha_type(page, logger)
        if captcha_type == "unknown":
            if attempt < attempts:
                time.sleep(2)
            continue

        try:
            if captcha_type == "grid":
                ok = solve_grid_captcha(page, ai, logger)
            else:
                ok = solve_slider_captcha(page, ai, BASE_DIR, logger)

            logger.info(f"验证码处理: {'成功' if ok else '失败'}")
            if ok:
                time.sleep(3)
        except Exception as exc:
            logger.exception(exc, traceback.format_exc())

    return False


# ── 入口 ────────────────────────────────────────────────────

def main():
    args = set(sys.argv[1:])
    debug = "--debug" in args
    run_now = "--now" in args

    if run_now or debug:
        run_checkin(debug=debug)
    else:
        schedule_time = os.getenv("SCHEDULE_TIME")
        if schedule_time:
            while True:
                hour, minute = map(int, schedule_time.split(":"))
                offset = random.randint(-30, 30)
                second = random.randint(0, 59)
                target = datetime.now().replace(
                    hour=hour, minute=minute, second=second, microsecond=0
                ) + timedelta(minutes=offset)
                if target <= datetime.now():
                    target += timedelta(days=1)

                wait = (target - datetime.now()).total_seconds()
                print(f"[INF] 下次签到: {target:%Y-%m-%d %H:%M:%S}，等待 {wait / 3600:.1f} 小时")
                time.sleep(wait)

                print(f"[INF] 开始签到 ({datetime.now():%Y-%m-%d %H:%M:%S})")
                try:
                    run_checkin()
                except Exception as exc:
                    print(f"[ERR] 签到异常: {exc}")
                print("[INF] 签到完成，等待下次执行...\n")
        else:
            run_checkin()


if __name__ == "__main__":
    main()
