# -- coding: utf-8 --
"""
Copyright (c) 2024 [Hosea]
Licensed under the MIT License.
See LICENSE file in the project root for full license information.
"""
import os
import random
import time
import traceback

import undetected_chromedriver as uc
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BASE_URL = "https://www.nodeseek.com"
TRADE_URL = f"{BASE_URL}/categories/trade"
COMMENT_TARGET_COUNT = int(os.environ.get("NS_COMMENT_COUNT", "20"))
COMMENT_MIN_INTERVAL = float(os.environ.get("NS_COMMENT_MIN_INTERVAL", "3.2"))
COMMENT_PAGE_LIMIT = int(os.environ.get("NS_COMMENT_PAGE_LIMIT", "3"))
COMMENT_TEXTS = ["bd", "帮顶"]
ENABLE_CHICKEN_LEG = False


def env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


ns_random = env_flag("NS_RANDOM", True)
headless = env_flag("HEADLESS", True)


def wait_for_page_ready(driver, timeout=20):
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def scroll_to_center(driver, element):
    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center', inline: 'center'});",
        element,
    )
    time.sleep(0.4)


def safe_click(driver, element, description="元素", timeout=8):
    last_error = None
    for attempt in range(1, 4):
        try:
            scroll_to_center(driver, element)
            WebDriverWait(driver, timeout).until(lambda _: element.is_displayed())
            element.click()
            return True
        except Exception as error:
            last_error = error
            print(f"{description} 第 {attempt} 次点击失败: {type(error).__name__}: {error}")
            time.sleep(0.8)

    try:
        driver.execute_script("arguments[0].click();", element)
        return True
    except Exception as error:
        print(f"{description} JavaScript 点击失败: {type(error).__name__}: {error}")
        if last_error:
            print(f"{description} 上一次 Selenium 点击错误: {last_error}")
        return False


def throttle_comment(last_submit_at):
    if last_submit_at <= 0:
        return
    elapsed = time.monotonic() - last_submit_at
    wait_seconds = COMMENT_MIN_INTERVAL - elapsed
    if wait_seconds > 0:
        print(f"等待 {wait_seconds:.1f} 秒，避开评论频率限制")
        time.sleep(wait_seconds)


def setup_driver_and_cookies():
    try:
        cookie = os.environ.get("NS_COOKIE") or os.environ.get("COOKIE")

        if not cookie:
            print("未找到 cookie 配置")
            return None

        print("开始初始化浏览器...")
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        if headless:
            print("启用无头模式...")
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")

        print("正在启动 Chrome...")
        driver = uc.Chrome(options=options)
        driver.set_window_size(1920, 1080)

        if headless:
            driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

        print("正在设置 cookie...")
        driver.get(BASE_URL)
        wait_for_page_ready(driver)
        time.sleep(3)

        cookie_count = 0
        for cookie_item in cookie.split(";"):
            cookie_item = cookie_item.strip()
            if not cookie_item or "=" not in cookie_item:
                continue
            name, value = cookie_item.split("=", 1)
            driver.add_cookie(
                {
                    "name": name.strip(),
                    "value": value.strip(),
                    "domain": ".nodeseek.com",
                    "path": "/",
                }
            )
            cookie_count += 1

        print(f"已设置 {cookie_count} 个 cookie，刷新页面...")
        driver.refresh()
        wait_for_page_ready(driver)
        time.sleep(5)

        return driver

    except Exception as error:
        print(f"设置浏览器和 Cookie 时出错: {error}")
        print(traceback.format_exc())
        return None


def click_sign_icon(driver):
    try:
        print("开始执行签到...")
        driver.get(BASE_URL)
        wait_for_page_ready(driver)
        time.sleep(3)

        sign_icon = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//span[@title='签到']"))
        )
        print(f"签到图标元素: {sign_icon.get_attribute('outerHTML')}")

        if not safe_click(driver, sign_icon, "签到图标"):
            return False

        time.sleep(4)
        print(f"签到点击后页面 URL: {driver.current_url}")

        button_text = "试试手气" if ns_random else "鸡腿 x 5"
        try:
            reward_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH, f"//button[contains(normalize-space(), '{button_text}')]")
                )
            )
            if safe_click(driver, reward_button, f"{button_text} 按钮"):
                print(f"完成签到奖励选择: {button_text}")
                time.sleep(2)
                return True
        except TimeoutException:
            print(f"没有找到 {button_text} 按钮，可能已经签到过或页面未打开签到弹窗")

        return False

    except Exception as error:
        print("签到过程中出错:")
        print(f"错误类型: {type(error).__name__}")
        print(f"错误信息: {error}")
        print(f"当前页面 URL: {driver.current_url}")
        print(traceback.format_exc())
        return False


def collect_post_urls(driver):
    urls = []
    seen = set()

    for page in range(1, COMMENT_PAGE_LIMIT + 1):
        page_url = TRADE_URL if page == 1 else f"{TRADE_URL}?page={page}"
        print(f"正在收集交易区第 {page} 页帖子...")
        driver.get(page_url)
        wait_for_page_ready(driver)

        posts = WebDriverWait(driver, 30).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".post-list-item"))
        )
        valid_posts = [post for post in posts if not post.find_elements(By.CSS_SELECTOR, ".pined")]
        random.shuffle(valid_posts)

        for post in valid_posts:
            try:
                post_link = post.find_element(By.CSS_SELECTOR, ".post-title a")
                post_url = post_link.get_attribute("href")
                if post_url and post_url not in seen:
                    seen.add(post_url)
                    urls.append(post_url)
            except Exception:
                continue

        if len(urls) >= COMMENT_TARGET_COUNT * 2:
            break

    print(f"已收集 {len(urls)} 个可尝试评论的帖子")
    random.shuffle(urls)
    return urls


def submit_comment(driver, post_url, last_submit_at):
    driver.get(post_url)
    wait_for_page_ready(driver)

    editor = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".CodeMirror"))
    )
    safe_click(driver, editor, "评论编辑器")

    input_text = random.choice(COMMENT_TEXTS)
    actions = ActionChains(driver)
    for char in input_text:
        actions.send_keys(char)
        actions.pause(random.uniform(0.1, 0.3))
    actions.perform()

    throttle_comment(last_submit_at)

    submit_button = WebDriverWait(driver, 30).until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                "//button[contains(@class, 'submit') and contains(@class, 'btn') "
                "and contains(normalize-space(), '发布评论')]",
            )
        )
    )

    if not safe_click(driver, submit_button, "发布评论按钮"):
        return False, last_submit_at

    submitted_at = time.monotonic()
    time.sleep(random.uniform(3.0, 5.0))
    return True, submitted_at


def nodeseek_comment(driver):
    success_count = 0
    last_submit_at = 0.0

    try:
        post_urls = collect_post_urls(driver)

        for post_url in post_urls:
            if success_count >= COMMENT_TARGET_COUNT:
                break

            try:
                print(f"正在处理第 {success_count + 1}/{COMMENT_TARGET_COUNT} 条评论: {post_url}")
                ok, last_submit_at = submit_comment(driver, post_url, last_submit_at)
                if ok:
                    success_count += 1
                    print(f"已在帖子 {post_url} 中提交评论，当前成功 {success_count}/{COMMENT_TARGET_COUNT}")
            except Exception as error:
                print(f"处理帖子失败 {post_url}: {type(error).__name__}: {error}")
                continue

        print(f"NodeSeek 评论任务完成，成功 {success_count}/{COMMENT_TARGET_COUNT}")
        return success_count

    except Exception as error:
        print(f"NodeSeek 评论出错: {error}")
        print(traceback.format_exc())
        return success_count


def click_chicken_leg(driver):
    if not ENABLE_CHICKEN_LEG:
        print("加鸡腿功能已禁用，跳过")
        return False

    try:
        print("尝试点击加鸡腿按钮...")
        chicken_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, '//div[@class="nsk-post"]//div[@title="加鸡腿"][1]'))
        )
        if not safe_click(driver, chicken_btn, "加鸡腿按钮"):
            return False

        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".msc-confirm"))
        )

        try:
            error_title = driver.find_element(By.XPATH, "//h3[contains(text(), '该评论创建于7天前')]")
            if error_title:
                print("该帖子超过 7 天，无法加鸡腿")
                ok_btn = driver.find_element(By.CSS_SELECTOR, ".msc-confirm .msc-ok")
                safe_click(driver, ok_btn, "确认按钮")
                return False
        except Exception:
            ok_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".msc-confirm .msc-ok"))
            )
            safe_click(driver, ok_btn, "确认按钮")
            print("确认加鸡腿成功")

        WebDriverWait(driver, 5).until_not(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".msc-overlay"))
        )
        time.sleep(1)
        return True

    except Exception as error:
        print(f"加鸡腿操作失败: {error}")
        return False


if __name__ == "__main__":
    print("开始执行 NodeSeek 自动任务...")
    driver = setup_driver_and_cookies()
    if not driver:
        print("浏览器初始化失败")
        exit(1)

    try:
        sign_ok = click_sign_icon(driver)
        comment_count = nodeseek_comment(driver)
        # 低等级账号暂时没有免费加鸡腿额度，默认禁用。
        # 后续需要开启时，把 ENABLE_CHICKEN_LEG 改为 True，并在评论后调用 click_chicken_leg(driver)。
        print(f"脚本执行完成，签到: {'成功或已签到' if sign_ok else '未确认成功'}，评论: {comment_count}/{COMMENT_TARGET_COUNT}")
    finally:
        driver.quit()
