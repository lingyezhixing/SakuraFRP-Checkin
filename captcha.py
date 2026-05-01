import io
import random
import time
import urllib.request

from PIL import Image
import pytweening

from logger import CheckinLogger
from ai_service import AIService

# ── 选择器常量 ──────────────────────────────────────────────

_GRID_SELECTORS = [".geetest_table_box", ".geetest_grid", "[class*='table'][class*='box']"]

_SLIDER_SELECTORS = [
    ".geetest_slider", ".geetest_slider_button", ".geetest_slider_track",
    ".geetest_canvas_bg", ".geetest_canvas_slice",
    "[class*='slider']", "[class*='canvas'][class*='bg']",
]

_SLIDER_BUTTON_SELECTORS = [
    ".geetest_slider_button", ".geetest_slider_knob",
    ".geetest_btn", "[class*='slider'][class*='button']",
]

_CANVAS_SELECTORS = [".geetest_canvas_bg", "canvas.geetest_canvas_bg"]

_BG_IMG_SELECTORS = [".geetest_bg img", ".geetest_slice_bg img", "[class*='bg'] img"]

_SUBMIT_SELECTORS = [".geetest_commit", "text=确认", ".geetest_submit"]

_EASING_FUNCTIONS = [
    pytweening.easeInOutQuad,
    pytweening.easeOutQuad,
    pytweening.easeInOutCubic,
]

# ── 工具函数 ────────────────────────────────────────────────

def _is_visible(locator, timeout=2000):
    try:
        return locator.is_visible(timeout=timeout)
    except Exception:
        return False


def _first_visible(page, selectors, timeout=2000):
    for sel in selectors:
        loc = page.locator(sel).first
        if _is_visible(loc, timeout):
            return loc
    return None


# ── 缺口识别（captcha-recognizer）──────────────────────────

def _identify_gap(bg_img_bytes, logger: CheckinLogger):
    try:
        from captcha_recognizer.slider import Slider
        import numpy as np

        bg_arr = np.array(Image.open(io.BytesIO(bg_img_bytes)))
        box, confidence = Slider().identify(source=bg_arr, show=False)

        if box and len(box) >= 4:
            gap = int(box[0])
            logger.debug(f"captcha-recognizer: 缺口={gap}px, 置信度={confidence:.2f}")
            return gap

        logger.debug("captcha-recognizer 未识别到缺口")
        return 0
    except ImportError:
        logger.error("captcha-recognizer 库未安装，请运行: pip install captcha-recognizer")
        return 0
    except Exception as exc:
        logger.error(f"captcha-recognizer 识别异常: {exc}")
        return 0


# ── 验证码类型检测 ──────────────────────────────────────────

def detect_captcha_type(page, logger: CheckinLogger):
    if _first_visible(page, _GRID_SELECTORS, timeout=2000):
        logger.debug("检测到九宫格验证码")
        return "grid"

    for sel in _SLIDER_SELECTORS:
        if _is_visible(page.locator(sel).first, timeout=2000):
            logger.debug("检测到滑块验证码")
            return "slider"

    logger.debug("未检测到已知的验证码类型")
    return "unknown"


# ── 九宫格验证码 ────────────────────────────────────────────

def solve_grid_captcha(page, ai: AIService, logger: CheckinLogger):
    logger.info("开始处理九宫格验证码...")

    container = page.locator(".geetest_table_box").first
    if not _is_visible(container, 3000):
        logger.debug("验证码容器不可见")
        return False

    # 一次下载，裁出题目图和九宫格
    tip_bytes, cell_images = _download_and_slice(container, logger)
    if not tip_bytes or not cell_images:
        return False

    # 逐格比较（题目图 vs 格子图）
    click_indices = _classify_cells(tip_bytes, cell_images, ai, logger)
    logger.info(f"匹配格子: {click_indices or '无'}")

    if not click_indices:
        _refresh_captcha(page, logger)
        return False

    # 点击匹配格子
    _click_cells(page, container, click_indices, logger)

    # 提交
    btn = _first_visible(page, _SUBMIT_SELECTORS, timeout=2000)
    if btn:
        btn.click()
        logger.debug("已点击提交按钮")
        return True

    logger.error("未找到提交按钮")
    return False


def _download_and_slice(container, logger):
    try:
        src = container.locator("img.geetest_item_img").first.get_attribute("src")
        if not src:
            raise ValueError("未找到图片URL")
        logger.debug(f"下载原图: {src[:80]}...")
        data = urllib.request.urlopen(src, timeout=10).read()
        full_img = Image.open(io.BytesIO(data))
        w, h = full_img.size

        # 题目图：底部条带左侧 ~1/3（右侧纯黑）
        tip_w = round(w / 3)
        tip_buf = io.BytesIO()
        full_img.crop((0, w, tip_w, h)).save(tip_buf, format="PNG")
        tip_bytes = tip_buf.getvalue()

        # 九宫格：顶部正方形 (0, 0) → (w, w)
        cw = w / 3
        cells = []
        for r in range(3):
            for c in range(3):
                buf = io.BytesIO()
                full_img.crop((c * cw, r * cw, (c + 1) * cw, (r + 1) * cw)).save(buf, format="PNG")
                cells.append(buf.getvalue())

        logger.debug(f"图片切分完成: {w}x{h}, 题目 {tip_w}x{h-w}")
        return tip_bytes, cells
    except Exception as exc:
        logger.error(f"图片下载切分失败: {exc}")
        return None, []



def _classify_cells(tip_bytes, cell_images, ai, logger):
    indices = []
    for i, cell_bytes in enumerate(cell_images):
        matched = ai.compare_images(tip_bytes, cell_bytes)
        label = "匹配" if matched else "不匹配"
        logger.debug(f"格子 {i + 1} (行{(i // 3) + 1}, 列{(i % 3) + 1}): {label}")
        if matched:
            indices.append(i + 1)
    return indices


def _click_cells(page, container, indices, logger):
    box = container.bounding_box()
    if not box:
        logger.error("无法获取验证码容器位置")
        return
    cw, ch = box["width"] / 3, box["height"] / 3
    for idx in indices:
        r, c = (idx - 1) // 3, (idx - 1) % 3
        x = box["x"] + c * cw + cw / 2
        y = box["y"] + r * ch + ch / 2
        logger.debug(f"点击格子 {idx} (行{r + 1}, 列{c + 1})")
        page.mouse.click(x, y)
        time.sleep(random.uniform(0.3, 0.5))


def _refresh_captcha(page, logger):
    logger.info("未找到匹配项，刷新验证码")
    try:
        btn = page.locator(".geetest_refresh").first
        if _is_visible(btn):
            btn.click()
            time.sleep(2)
    except Exception:
        pass


# ── 滑块验证码 ──────────────────────────────────────────────

def solve_slider_captcha(page, ai, base_dir, logger: CheckinLogger):
    import time

    logger.info("开始处理滑块验证码...")

    # 找到滑块按钮
    slider_btn = _first_visible(page, _SLIDER_BUTTON_SELECTORS, timeout=1000)
    if not slider_btn:
        logger.error("未找到滑块按钮")
        return False

    btn_box = slider_btn.bounding_box()
    if not btn_box:
        logger.error("无法获取滑块按钮位置")
        return False

    btn_x = btn_box["x"] + btn_box["width"] / 2
    btn_y = btn_box["y"] + btn_box["height"] / 2
    btn_initial_x = btn_box["x"]

    # 获取背景图
    bg_bytes = _get_bg_image(page, base_dir, logger)
    if not bg_bytes:
        logger.error("无法获取验证码背景图")
        return False

    # 识别缺口
    gap = _identify_gap(bg_bytes, logger)
    if gap <= 0:
        logger.error("缺口识别失败")
        return False
    logger.info(f"缺口位置: {gap}px")

    # 计算拖动距离
    drag_distance = _calc_drag_distance(page, gap, btn_initial_x, logger)
    target_x = btn_x + drag_distance
    logger.info(f"滑动距离: {drag_distance:.1f}px, 目标: {target_x:.1f}px")

    # 拖动前截图
    try:
        page.screenshot(path=str(base_dir / "slider_before_drag.png"))
    except Exception:
        pass

    # 执行拖动
    _drag_slider(page, btn_x, btn_y, drag_distance, target_x, logger)

    # 拖动后截图
    try:
        page.screenshot(path=str(base_dir / "slider_after_drag.png"))
    except Exception:
        pass

    time.sleep(2)

    # 检查结果
    captcha_gone = not _is_visible(page.locator(".geetest_slider").first, timeout=1000)
    if captcha_gone:
        logger.debug("验证码已消失，可能验证成功")
    else:
        logger.debug("验证码仍存在，可能验证失败")
    return captcha_gone


def _get_bg_image(page, base_dir, logger):
    # 方法1: canvas
    bg_canvas = _first_visible(page, _CANVAS_SELECTORS, timeout=1000)
    if bg_canvas:
        try:
            data = bg_canvas.screenshot()
            (base_dir / "captcha_bg.png").write_bytes(data)
            return data
        except Exception:
            pass

    # 方法2: img 标签
    for sel in _BG_IMG_SELECTORS:
        img = page.locator(sel).first
        if _is_visible(img, timeout=1000):
            try:
                data = img.screenshot()
                (base_dir / "captcha_bg.png").write_bytes(data)
                return data
            except Exception:
                continue

    # 方法3: 截图整个验证码区域
    logger.debug("尝试截图整个验证码区域")
    for sel in [".geetest_popup", ".geetest_wrap"]:
        container = page.locator(sel).first
        if _is_visible(container, timeout=2000):
            try:
                data = container.screenshot()
                (base_dir / "captcha_container.png").write_bytes(data)
                return data
            except Exception:
                continue

    return None


def _calc_drag_distance(page, gap, btn_initial_x, logger):
    bg_canvas = _first_visible(page, _CANVAS_SELECTORS, timeout=1000)
    if bg_canvas:
        canvas_box = bg_canvas.bounding_box()
        if canvas_box:
            offset = btn_initial_x - canvas_box["x"]
            logger.debug(f"偏移量: {offset:.1f}px")
            return gap + offset + random.uniform(-5.0, 5.0)

    logger.debug("无背景canvas信息，直接使用缺口位置")
    return gap + random.uniform(-5.0, 5.0)


def _drag_slider(page, start_x, start_y, distance, target_x, logger):
    page.mouse.move(start_x, start_y)
    time.sleep(random.uniform(0.1, 0.2))
    page.mouse.down()
    time.sleep(random.uniform(0.1, 0.2))

    steps = random.randint(20, 30)
    easing = random.choice(_EASING_FUNCTIONS)
    logger.debug(f"缓动: {easing.__name__}, 步数: {steps}")

    for i in range(steps):
        progress = easing(i / steps)
        jx = random.uniform(-1.5, 1.5)
        jy = random.uniform(-2, 2)
        page.mouse.move(start_x + distance * progress + jx, start_y + jy)

        if i < steps * 0.3:
            time.sleep(random.uniform(0.005, 0.015))
        elif i > steps * 0.7:
            time.sleep(random.uniform(0.02, 0.04))
        else:
            time.sleep(random.uniform(0.01, 0.025))

    # 超调回调
    if random.random() > 0.5:
        overshoot = random.uniform(2, 5)
        page.mouse.move(target_x + overshoot, start_y + random.uniform(-1, 1))
        time.sleep(random.uniform(0.05, 0.1))

    page.mouse.move(target_x, start_y)
    time.sleep(random.uniform(0.15, 0.25))
    page.mouse.up()
    time.sleep(random.uniform(0.5, 1.0))
    logger.debug("滑块拖动完成")
