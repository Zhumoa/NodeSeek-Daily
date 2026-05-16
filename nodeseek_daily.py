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
from bs4 import BeautifulSoup
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "y", "on")


ns_random = env_flag("NS_RANDOM", True)
cookie = os.environ.get("NS_COOKIE") or os.environ.get("COOKIE")
headless = env_flag("HEADLESS", True)

randomInputStr = ["bd", "帮顶"]
COMMENT_TARGET_COUNT = int(os.environ.get("NS_COMMENT_COUNT", "20"))
COMMENT_MIN_INTERVAL = float(os.environ.get("NS_COMMENT_MIN_INTERVAL", "3.2"))


def scroll_center(driver, element):
    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center', inline: 'center'});",
        element,
    )
    time.sleep(0.5)


def click_element(driver, element, name="元素"):
    try:
        scroll_center(driver, element)
        element.click()
        return True
    except Exception as click_error:
        print(f"{name} 点击失败，尝试使用 JavaScript 点击: {str(click_error)}")
        try:
            driver.execute_script("arguments[0].click();", element)
            return True
        except Exception as js_error:
            print(f"{name} JavaScript 点击也失败: {str(js_error)}")
            return False


def click_sign_icon(driver):
    """
    尽量沿用原脚本：查找签到图标，然后点击签到弹窗里的奖励按钮。
    只额外加了回首页、居中滚动和拼手气默认值。
    """
    try:
        print("开始查找签到图标...")
        driver.get("https://www.nodeseek.com")
        time.sleep(5)

        sign_icon = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//span[@title='签到']"))
        )
        print("找到签到图标，准备点击...")
        print(f"签到图标元素: {sign_icon.get_attribute('outerHTML')}")

        if not click_element(driver, sign_icon, "签到图标"):
            return False

        print("等待页面跳转...")
        time.sleep(5)
        print(f"当前页面URL: {driver.current_url}")

        try:
            if ns_random:
                button_text = "试试手气"
            else:
                button_text = "鸡腿 x 5"

            click_button = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable(
                    (By.XPATH, f"//button[contains(text(), '{button_text}')]")
                )
            )

            if click_element(driver, click_button, button_text):
                print(f"完成 {button_text} 点击")
                time.sleep(2)
                return True
        except Exception as lucky_error:
            print(f"签到奖励按钮点击失败或者已经签到过了: {str(lucky_error)}")

        return False

    except Exception as e:
        print("签到过程中出错:")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {str(e)}")
        print(f"当前页面URL: {driver.current_url}")
        print(f"当前页面标题: {driver.title}")
        print(f"当前页面源码片段: {driver.page_source[:500]}...")
        print("详细错误信息:")
        traceback.print_exc()
        return False


def setup_driver_and_cookies():
    """
    基本恢复原脚本的浏览器初始化方式。
    关键点：继续使用 version_main=147 和普通 --headless，避免上次重构版引入的不稳定行为。
    """
    try:
        cookie_value = os.environ.get("NS_COOKIE") or os.environ.get("COOKIE")
        headless_value = env_flag("HEADLESS", True)

        if not cookie_value:
            print("未找到cookie配置")
            return None

        print("开始初始化浏览器...")
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        if headless_value:
            print("启用无头模式...")
            options.add_argument("--headless")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument(
                "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

        print("正在启动Chrome...")
        driver = uc.Chrome(options=options, version_main=147)

        if headless_value:
            driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            driver.set_window_size(1920, 1080)

        print("Chrome启动成功")

        print("正在设置cookie...")
        driver.get("https://www.nodeseek.com")
        time.sleep(5)

        cookie_count = 0
        for cookie_item in cookie_value.split(";"):
            try:
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
            except Exception as e:
                print(f"设置cookie出错: {str(e)}")
                continue

        print(f"已设置 {cookie_count} 个 cookie，刷新页面...")
        driver.refresh()
        time.sleep(5)

        return driver

    except Exception as e:
        print(f"设置浏览器和Cookie时出错: {str(e)}")
        print("详细错误信息:")
        print(traceback.format_exc())
        return None


def wait_comment_interval(last_submit_time):
    if not last_submit_time:
        return

    elapsed = time.monotonic() - last_submit_time
    wait_time = COMMENT_MIN_INTERVAL - elapsed
    if wait_time > 0:
        print(f"等待 {wait_time:.1f} 秒，避开评论频率限制")
        time.sleep(wait_time)


def nodeseek_comment(driver):
    try:
        print("正在访问交易区...")
        target_url = "https://www.nodeseek.com/categories/trade"
        driver.get(target_url)
        print("等待页面加载...")

        posts = WebDriverWait(driver, 30).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".post-list-item"))
        )
        print(f"成功获取到 {len(posts)} 个帖子")

        valid_posts = [post for post in posts if not post.find_elements(By.CSS_SELECTOR, ".pined")]
        random.shuffle(valid_posts)

        selected_urls = []
        for post in valid_posts:
            try:
                post_link = post.find_element(By.CSS_SELECTOR, ".post-title a")
                post_url = post_link.get_attribute("href")
                if post_url and post_url not in selected_urls:
                    selected_urls.append(post_url)
            except Exception:
                continue

        success_count = 0
        last_submit_time = 0

        for post_url in selected_urls:
            if success_count >= COMMENT_TARGET_COUNT:
                break

            try:
                print(f"正在处理第 {success_count + 1} 条评论，帖子: {post_url}")
                driver.get(post_url)

                editor = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".CodeMirror"))
                )

                click_element(driver, editor, "评论编辑器")
                time.sleep(0.5)
                input_text = random.choice(randomInputStr)

                actions = ActionChains(driver)
                for char in input_text:
                    actions.send_keys(char)
                    actions.pause(random.uniform(0.1, 0.3))
                actions.perform()

                time.sleep(1)
                wait_comment_interval(last_submit_time)

                submit_button = WebDriverWait(driver, 30).until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            "//button[contains(@class, 'submit') and contains(@class, 'btn') "
                            "and contains(text(), '发布评论')]",
                        )
                    )
                )

                if not click_element(driver, submit_button, "发布评论按钮"):
                    continue

                last_submit_time = time.monotonic()
                success_count += 1
                print(f"已在帖子 {post_url} 中完成评论，当前成功 {success_count}/{COMMENT_TARGET_COUNT}")
                time.sleep(random.uniform(3, 5))

            except Exception as e:
                print(f"处理帖子时出错: {str(e)}")
                continue

        print(f"NodeSeek评论任务完成，成功 {success_count}/{COMMENT_TARGET_COUNT}")
        return success_count

    except Exception as e:
        print(f"NodeSeek评论出错: {str(e)}")
        print("详细错误信息:")
        print(traceback.format_exc())
        return 0


def click_chicken_leg(driver):
    print("加鸡腿功能已禁用，跳过")
    return False


if __name__ == "__main__":
    print("开始执行NodeSeek评论脚本...")
    driver = setup_driver_and_cookies()
    if not driver:
        print("浏览器初始化失败")
        exit(1)

    try:
        comment_count = nodeseek_comment(driver)
        sign_ok = click_sign_icon(driver)
        print(
            f"脚本执行完成，签到: {'成功或已签到' if sign_ok else '未确认成功'}，"
            f"评论: {comment_count}/{COMMENT_TARGET_COUNT}"
        )
    finally:
        driver.quit()
