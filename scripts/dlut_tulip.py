#!/usr/bin/env python3
"""大连理工大学校园网自助服务系统 (tulip.dlut.edu.cn)

基于 Selenium 的自动化方案：
- 使用无头浏览器登录并操作
- 通过执行页面内 JavaScript 调用 JSON-RPC API
- 获取用户信息、余额、流量等数据

依赖: pip install selenium
"""

import os
import sys
import json
import time
import argparse

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

from dlut_portal import load_config

TULIP_BASE = "http://tulip.dlut.edu.cn"


def _get_driver(headless=True):
    """创建 Chrome WebDriver"""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    try:
        driver = webdriver.Chrome(options=chrome_options)
    except Exception:
        raise RuntimeError(
            "无法启动 Chrome。请确保已安装 Chrome 浏览器和 chromedriver。\n"
            "下载地址: https://chromedriver.chromium.org/downloads"
        )
    return driver


def _is_logged_in(driver):
    """检查是否已登录"""
    try:
        return driver.execute_script(
            """
            if (typeof Frame !== 'undefined' && Frame.isLogin) {
                return Frame.isLogin();
            }
            return document.querySelector('[data-frame-id="userName"]') === null;
            """
        )
    except Exception:
        return False


def _do_login(driver, username, password):
    """在页面中执行登录"""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-frame-id='userName']"))
    )

    driver.find_element(By.CSS_SELECTOR, "[data-frame-id='userName']").send_keys(username)
    driver.find_element(By.CSS_SELECTOR, "[data-frame-id='password']").send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "[data-frame-id='btn-login']").click()
    time.sleep(2)


def _call_rpc(driver, method, params=None):
    """通过页面 JavaScript 调用 JSON-RPC 接口"""
    if params is None:
        params = []

    script = f"""
    return new Promise((resolve, reject) => {{
        require(['request'], function(Request) {{
            Request.request({json.dumps(method)}, {json.dumps(params)}, function(result) {{
                resolve({{success: true, result: result}});
            }}, function(error) {{
                var errMsg = '未知错误';
                if (error) {{
                    if (typeof error === 'string') {{
                        errMsg = error;
                    }} else if (error.message) {{
                        errMsg = error.message;
                    }} else if (error.error) {{
                        errMsg = JSON.stringify(error.error);
                    }} else {{
                        errMsg = JSON.stringify(error);
                    }}
                }}
                resolve({{success: false, error: errMsg}});
            }});
        }}, function(err) {{
            reject('RequireJS 加载失败: ' + err);
        }});
    }});
    """

    result = driver.execute_script(script)
    if result is None:
        raise RuntimeError("RPC 调用返回空结果")
    if not result.get("success"):
        raise RuntimeError(f"RPC 调用失败: {result.get('error')}")
    rpc_response = result.get("result") or {}
    if isinstance(rpc_response, dict) and "result" in rpc_response:
        return rpc_response["result"]
    return rpc_response


def get_tulip_session(username, password, headless=True):
    """获取已登录的 Selenium WebDriver 会话"""
    driver = _get_driver(headless=headless)
    try:
        driver.get(f"{TULIP_BASE}/index.html;#/login.login")
        time.sleep(2)

        if _is_logged_in(driver):
            return driver

        _do_login(driver, username, password)
        time.sleep(2)

        if not _is_logged_in(driver):
            raise RuntimeError("登录失败，请检查用户名密码")

        return driver
    except Exception:
        driver.quit()
        raise


def get_user_info(driver):
    """获取用户信息"""
    return _call_rpc(driver, "/login/isAuthenticated")


def get_charge_info(driver, account):
    """获取余额和流量信息"""
    return _call_rpc(driver, "/user/charge/getChargeInfoByAccount", [account])


def get_security_user(driver, user_id):
    """获取安全中心用户信息"""
    return _call_rpc(driver, "/security/user/getById", [user_id])


# ═══════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="大连理工大学校园网自助服务系统")
    parser.add_argument("--no-headless", action="store_true", help="显示浏览器窗口")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("login", help="测试登录")
    sub.add_parser("me", help="查询用户信息")
    sub.add_parser("balance", help="查询余额和流量")
    sub.add_parser("security", help="查询安全中心信息")
    sub.add_parser("summary", help="汇总信息")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    config = load_config()
    username = config.get("dlut_username", "")
    password = config.get("dlut_password", "")

    if not username or not password:
        print("ERROR: 未配置 DUT 主账号。请运行 python scripts/setup.py")
        sys.exit(1)

    headless = not args.no_headless
    driver = None

    try:
        driver = get_tulip_session(username, password, headless=headless)

        if args.cmd == "login":
            print("校园网自助服务系统登录成功")
            info = get_user_info(driver)
            print(f"姓名: {info.get('Name', '')}")
            print(f"账号: {info.get('Account', '')}")
            return

        if args.cmd == "me":
            info = get_user_info(driver)
            print(json.dumps(info, ensure_ascii=False, indent=2))
            return

        if args.cmd == "balance":
            info = get_user_info(driver)
            account = info.get("Account", "")
            if not account:
                raise RuntimeError("无法获取账号信息")
            charge = get_charge_info(driver, account)
            print(json.dumps(charge, ensure_ascii=False, indent=2))
            return

        if args.cmd == "security":
            info = get_user_info(driver)
            user_id = info.get("ID", "")
            if not user_id:
                raise RuntimeError("无法获取用户ID")
            security = get_security_user(driver, user_id)
            print(json.dumps(security, ensure_ascii=False, indent=2))
            return

        if args.cmd == "summary":
            info = get_user_info(driver)
            account = info.get("Account", "")
            user_id = info.get("ID", "")

            print(f"姓名: {info.get('Name', '')}")
            print(f"账号: {account}")
            print(f"学院: {info.get('Department', {}).get('DisplayName', '')}")
            print(f"邮箱: {info.get('Email', '')}")
            print(f"手机: {info.get('Mobile', '')}")

            if account:
                try:
                    charge = get_charge_info(driver, account)
                    print(f"余额: {charge.get('balance', 'N/A')} 元")
                    print(f"已用流量: {charge.get('userdTotalFlow', 'N/A')} MB")
                    print(f"总支出: {charge.get('expenditure', 'N/A')} 元")
                except Exception as e:
                    print(f"余额查询失败: {e}")
            return

    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()
