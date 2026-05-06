#!/usr/bin/env python3
"""大连理工大学门户系统 API

认证: CAS SSO (sso.dlut.edu.cn) → portal.dlut.edu.cn
使用 config.json 中的 dlut_username / dlut_password
"""

import os
import sys
import re

import _console  # noqa: F401  forces UTF-8 stdout on Windows
import requests

# ─── 复用 dlut_jxgl 的公共辅助函数 ───
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

try:
    from dlut_jxgl import (
        load_config,
        CAS_BASE,
        _UA,
        _CASFormParser,
        _extract_cas_fields,
        _des_encrypt,
    )
except ImportError:
    # 降级：如果导入失败，重新定义基本函数
    import json
    from html.parser import HTMLParser

    CAS_BASE = "https://sso.dlut.edu.cn"
    _UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    _SKILL_DIR = os.path.dirname(_SCRIPT_DIR)
    _CONFIG_PATHS = [
        os.path.join(_SKILL_DIR, "config.json"),
        os.path.join(
            os.path.expanduser("~/.openclaw/workspace/skills/openclaw-dut"),
            "config.json",
        ),
    ]

    def load_config():
        for path in _CONFIG_PATHS:
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
        return {}

    class _CASFormParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.fields = {}

        def handle_starttag(self, tag, attrs):
            if tag != "input":
                return
            attr_dict = dict(attrs)
            name = attr_dict.get("name", "")
            if name in ("lt", "execution", "_eventId"):
                self.fields[name] = attr_dict.get("value", "")

    def _extract_cas_fields(html):
        parser = _CASFormParser()
        parser.feed(html)
        return parser.fields

    def _des_encrypt(data, first_key="1", second_key="2", third_key="3"):
        import execjs

        des_js_path = os.path.join(_SCRIPT_DIR, "..", "vendor", "des.js")
        if not os.path.exists(des_js_path):
            r = requests.get(
                f"{CAS_BASE}/cas/comm/js/des.js?v=20240515", timeout=15
            )
            r.raise_for_status()
            os.makedirs(os.path.dirname(des_js_path), exist_ok=True)
            with open(des_js_path, "w") as f:
                f.write(r.text)
        with open(des_js_path) as f:
            ctx = execjs.compile(f.read())
        return ctx.call("strEnc", data, first_key, second_key, third_key)


# ─── 常量 ───
PORTAL_BASE = "https://portal.dlut.edu.cn"

_portal_session = None


# ═══════════════════════════════════════════
# CAS 认证
# ═══════════════════════════════════════════

def portal_login(username, password):
    """CAS SSO 登录 portal → 返回已认证的 requests.Session"""
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
    )

    # Step 1: 访问门户首页，触发 CAS 重定向
    r = s.get(f"{PORTAL_BASE}/tp/", timeout=15, allow_redirects=False)

    cas_login_url = None
    if r.status_code in (301, 302, 307):
        cas_login_url = r.headers.get("Location", "")
        if cas_login_url and not cas_login_url.startswith("http"):
            cas_login_url = PORTAL_BASE + cas_login_url

    if not cas_login_url or not cas_login_url.startswith(CAS_BASE):
        # 尝试从 HTML 中提取 CAS 登录链接
        if r.status_code == 200:
            m = re.search(
                rf"{re.escape(CAS_BASE)}/cas/login[^\"'\s]*", r.text
            )
            if m:
                cas_login_url = m.group(0)

        if not cas_login_url:
            # 手动构造（service 参数指向 portal）
            service = requests.utils.quote(f"{PORTAL_BASE}/tp/")
            cas_login_url = f"{CAS_BASE}/cas/login?service={service}"

    # Step 2: 获取 CAS 登录页
    r = s.get(cas_login_url, timeout=15)
    r.raise_for_status()

    if "系统提示" in r.text and "请求出错" in r.text:
        raise RuntimeError(
            "CAS 登录页返回异常（HTTP 500），service URL 可能不被允许"
        )

    fields = _extract_cas_fields(r.text)
    if not fields.get("lt"):
        raise RuntimeError("CAS 登录页未找到 lt 字段，页面结构可能已变化")

    # Step 3: DES 加密 + POST
    lt = fields.get("lt", "")
    rsa = _des_encrypt(username + password + lt)
    data = {
        "rsa": rsa,
        "ul": str(len(username)),
        "pl": str(len(password)),
        "sl": "0",
        "lt": lt,
        "execution": fields.get("execution", ""),
        "_eventId": "submit",
    }
    r = s.post(cas_login_url, data=data, allow_redirects=True, timeout=15)

    # Step 4: 检查登录结果
    if "登录成功" in r.text:
        return s
    if r.url.startswith(PORTAL_BASE):
        return s
    if "lt" in r.text and "username" in r.text:
        raise RuntimeError("CAS 登录失败：用户名或密码错误")
    if (
        "errormsg" in r.text.lower()
        or "密码错误" in r.text
        or "用户名或密码" in r.text
    ):
        raise RuntimeError("CAS 登录失败：用户名或密码错误")

    return s


def get_portal_session():
    """获取已认证的 portal session（懒加载，全局缓存）"""
    global _portal_session
    if _portal_session is not None:
        return _portal_session

    config = load_config()
    username = config.get("dlut_username", "")
    password = config.get("dlut_password", "")

    if not username or not password:
        print(
            "ERROR: 未配置 DUT 主账号。请运行 python scripts/setup.py "
            "或在 config.json 中填写 dlut_username / dlut_password"
        )
        sys.exit(1)

    s = portal_login(username, password)
    _portal_session = s
    return s


# ═══════════════════════════════════════════
# OAuth Token 获取
# ═══════════════════════════════════════════

_API_GATEWAY = "https://apim.dlut.edu.cn"


def get_access_token(session):
    """获取 Portal OAuth accessToken (JWT)

    流程:
    1. 访问 CAS OAuth authorize 获取 code
    2. 用 code 换取 accessToken
    返回: access_token 字符串
    """
    import urllib.parse

    oauth_url = (
        f"{CAS_BASE}/cas/oauth2.0/authorize"
        f"?client_id=nup&response_type=code"
        f"&redirect_uri=https://portal.dlut.edu.cn/tp/cas.html&scope=all"
    )
    r = session.get(oauth_url, timeout=15, allow_redirects=True)
    parsed = urllib.parse.urlparse(r.url)
    params = urllib.parse.parse_qs(parsed.query)
    code = params.get("code", [""])[0]
    cas_delegate = params.get("casDelegate", [""])[0]

    if not code:
        raise RuntimeError("无法获取 OAuth authorization code")

    token_url = f"{_API_GATEWAY}/sems-authc/oauth2/casToken/{code}/nup?casDelegate={cas_delegate}"
    r = session.get(
        token_url, timeout=10, headers={"Connection": "close", "Referer": f"{PORTAL_BASE}/tp/cas.html"}
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 200:
        raise RuntimeError(f"获取 token 失败: {data.get('msg', '未知错误')}")
    return data["data"]["accessToken"]


# ═══════════════════════════════════════════
# 数据接口
# ═══════════════════════════════════════════

def get_user_info(access_token):
    """获取当前登录用户信息

    返回: dict 含 user_name, id_number, unit_name, email, mobile 等
    """
    session = get_portal_session()
    url = f"{_API_GATEWAY}/sems-tp-nup/home/pingcurrent"
    r = session.post(
        url,
        timeout=10,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Referer": f"{PORTAL_BASE}/tp/",
            "Connection": "close",
        },
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 200:
        raise RuntimeError(f"获取用户信息失败: {data.get('msg', '未知错误')}")
    return data["data"]


# ═══════════════════════════════════════════
# 请求封装
# ═══════════════════════════════════════════

def portal_request(method, path_or_url, **kwargs):
    """使用已认证的 session 发送请求

    Args:
        method: HTTP 方法 (get/post/put/delete)
        path_or_url: 相对路径（以 / 开头）或完整 URL
    """
    s = get_portal_session()
    if path_or_url.startswith("http"):
        url = path_or_url
    else:
        url = f"{PORTAL_BASE}{path_or_url}"
    headers = kwargs.pop("headers", {})
    headers["Connection"] = "close"
    return getattr(s, method.lower())(url, headers=headers, **kwargs)


# ═══════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description="大连理工大学门户系统")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("login", help="测试 Portal CAS 登录")
    sub.add_parser("me", help="查询当前用户信息")

    p_get = sub.add_parser("get", help="获取 portal 页面/API 内容")
    p_get.add_argument("path", help="路径或完整 URL")
    p_get.add_argument("--output", "-o", help="保存到文件")

    p_open = sub.add_parser("open", help="在浏览器中打开 portal 应用")
    p_open.add_argument(
        "app_id", nargs="?", help="应用 ID，如 sems-tp-nup_29827717"
    )

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    if args.cmd == "login":
        config = load_config()
        username = config.get("dlut_username", "")
        password = config.get("dlut_password", "")
        if not username or not password:
            print("ERROR: 未配置 DUT 主账号")
            sys.exit(1)
        try:
            s = portal_login(username, password)
            print("Portal CAS 登录成功")
            r = s.get(f"{PORTAL_BASE}/tp/", timeout=10, allow_redirects=True)
            print(f"   首页响应: HTTP {r.status_code}")
            print(f"   最终 URL: {r.url[:100]}")
        except Exception as e:
            print(f"登录失败: {e}")
            sys.exit(1)
        return

    if args.cmd == "me":
        try:
            s = get_portal_session()
            token = get_access_token(s)
            info = get_user_info(token)
            print(f"姓名: {info.get('user_name', '')}")
            print(f"学号/工号: {info.get('id_number', '')}")
            print(f"学院: {info.get('unit_name', '')}")
            print(f"邮箱: {info.get('email', '')}")
            print(f"手机: {info.get('mobile', '')}")
        except Exception as e:
            print(f"获取失败: {e}")
            sys.exit(1)
        return

    if args.cmd == "get":
        r = portal_request("get", args.path)
        print(f"HTTP {r.status_code}")
        print(f"URL: {r.url}")
        print("---")
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(r.text)
            print(f"已保存到: {args.output} ({len(r.text)} 字符)")
        else:
            text = r.text[:3000]
            print(text)
            if len(r.text) > 3000:
                print(f"... (共 {len(r.text)} 字符，使用 -o 保存完整内容)")
        return

    if args.cmd == "open":
        import webbrowser

        if args.app_id:
            url = f"{PORTAL_BASE}/tp/#act={args.app_id}"
        else:
            url = f"{PORTAL_BASE}/tp/"
        webbrowser.open(url)
        print(f"已在浏览器中打开: {url}")


if __name__ == "__main__":
    main()
