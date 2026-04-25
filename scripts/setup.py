#!/usr/bin/env python3
"""openclaw-dlut 交互式配置向导

运行方式：python3 scripts/setup.py
功能：引导用户配置所有服务凭证，生成 config.json
"""

import os
import sys

# Windows stdout 默认 gbk，subprocess 捕获时 emoji 会 UnicodeEncodeError
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure") and (_s.encoding or "").lower() != "utf-8":
        _s.reconfigure(encoding="utf-8", errors="replace")
import json
import getpass
import platform

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.json")
EXAMPLE_PATH = os.path.join(PROJECT_DIR, "config.example.json")

# Windows ANSI 转义序列支持
if platform.system() == "Windows":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

# ANSI 颜色
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def banner():
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════╗
║       🎓 openclaw-dlut 配置向导                  ║
║       大连理工大学全能 AI 校园助手                ║
╚══════════════════════════════════════════════════╝{RESET}
""")


def load_existing():
    """加载已有配置"""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    if os.path.exists(EXAMPLE_PATH):
        with open(EXAMPLE_PATH) as f:
            return json.load(f)
    return {}


def prompt(label, default="", secret=False, required=False):
    """交互式输入，支持默认值和密码模式"""
    if default and not secret:
        hint = f"{DIM}(当前: {default[:20]}{'...' if len(str(default)) > 20 else ''}){RESET}"
    elif default and secret:
        hint = f"{DIM}(已配置，回车保留){RESET}"
    else:
        hint = f"{DIM}(可选，回车跳过){RESET}" if not required else f"{RED}(必填){RESET}"

    while True:
        if secret:
            val = getpass.getpass(f"  {label} {hint}: ")
        else:
            val = input(f"  {label} {hint}: ").strip()

        if not val:
            if default:
                return default
            if required:
                print(f"  {RED}⚠ 此项为必填，请输入{RESET}")
                continue
            return ""
        return val


def test_chaoxing(phone, password):
    """测试超星学习通登录"""
    try:
        import requests
        import base64
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import pad
        except ImportError:
            print(f"  {YELLOW}⚠ 需要 pycryptodome: pip install pycryptodome{RESET}")
            return None

        key = b"u2oh6Vu^HWe4_AES"
        cipher_u = AES.new(key, AES.MODE_CBC, key)
        cipher_p = AES.new(key, AES.MODE_CBC, key)
        uname = base64.b64encode(cipher_u.encrypt(pad(phone.encode(), 16))).decode()
        pwd = base64.b64encode(cipher_p.encrypt(pad(password.encode(), 16))).decode()

        r = requests.post("https://passport2.chaoxing.com/fanyalogin", data={
            "fid": "-1", "uname": uname, "password": pwd,
            "refer": "https%3A%2F%2Fi.chaoxing.com",
            "t": "true", "forbidotherlogin": "0", "validate": "",
            "doubleFactorLogin": "0", "independentId": "0",
        }, timeout=15)
        data = r.json()
        if data.get("status"):
            print(f"  {GREEN}✅ 超星登录成功！用户: {data.get('name', phone)}{RESET}")
            return True
        else:
            print(f"  {RED}❌ 超星登录失败: {data.get('msg2', '未知错误')}{RESET}")
            return False
    except ImportError:
        print(f"  {YELLOW}⚠ 需要 requests 库来测试连接: pip install requests{RESET}")
        return None
    except Exception as e:
        print(f"  {RED}❌ 连接失败: {e}{RESET}")
        return False


def test_mail(username, password, mail_domain="mail.dlut.edu.cn"):
    """测试邮箱连接"""
    try:
        import imaplib
        conn = imaplib.IMAP4_SSL("mail.dlut.edu.cn", 993, timeout=10)
        login_user = f"{username}@{mail_domain}" if "@" not in username else username
        conn.login(login_user, password)
        conn.logout()
        print(f"  {GREEN}✅ 邮箱连接成功！{RESET}")
        return True
    except Exception as e:
        print(f"  {RED}❌ 邮箱连接失败: {e}{RESET}")
        return False


def _test_jxgl_login(username, password):
    """测试教务系统 CAS 登录"""
    try:
        sys.path.insert(0, SCRIPT_DIR)
        from dlut_jxgl import test_cas_login
        return test_cas_login(username, password)
    except Exception as e:
        return False, f"连接失败: {e}"


def section(title, desc=""):
    """打印配置区块标题"""
    print(f"\n{BOLD}{CYAN}━━━ {title} ━━━{RESET}")
    if desc:
        print(f"  {DIM}{desc}{RESET}")
    print()


def main():
    banner()
    config = load_existing()
    is_update = os.path.exists(CONFIG_PATH)

    if is_update:
        print(f"{YELLOW}📝 检测到已有配置文件，将在此基础上更新{RESET}")
        print(f"{DIM}   回车保留当前值，输入 n 跳过某项配置{RESET}\n")
    else:
        print(f"  首次配置，将引导你逐步设置各项服务")
        print(f"  {DIM}回车保留当前值，输入 n 跳过某项配置{RESET}\n")

    # ━━━ 1. 超星学习通 ━━━
    section(
        "📋 超星学习通",
        "DDL 追踪、成绩查询、课件下载等功能"
    )
    print(f"  {DIM}使用超星学习通手机号+密码登录（dut.fanya.chaoxing.com）{RESET}\n")

    yn = input(f"  是否配置超星学习通？{DIM}(Y/n){RESET}: ").strip().lower()
    if yn != "n":
        phone = prompt("超星手机号", config.get("chaoxing_phone", ""))
        if phone:
            config["chaoxing_phone"] = phone
            password = prompt("超星密码", config.get("chaoxing_password", ""), secret=True)
            if password:
                config["chaoxing_password"] = password
                config["save_dir"] = prompt("课件下载目录", config.get("save_dir", "~/Downloads/Chaoxing课件"))
                config["calendar_name"] = prompt("日历名称", config.get("calendar_name", "超星作业"))

                print()
                test_chaoxing(phone, password)
            else:
                config["chaoxing_password"] = ""
        else:
            config["chaoxing_phone"] = ""
            config["chaoxing_password"] = ""
    else:
        print(f"  {DIM}已跳过超星学习通配置{RESET}")

    # ━━━ 2. 邮箱 ━━━
    section(
        "📧 大工邮箱",
        "用于查看未读邮件、搜索、发送邮件"
    )
    print(f"  {DIM}使用 DUT 统一身份认证账号登录 IMAP/SMTP{RESET}\n")

    yn = input(f"  是否配置大工邮箱？{DIM}(Y/n){RESET}: ").strip().lower()
    if yn != "n":
        username = prompt("DUT 用户名", config.get("dlut_username", ""))
        config["dlut_username"] = username

        if username:
            # 邮箱域名选择
            default_domain = config.get("dlut_mail_domain", "")
            if default_domain:
                print(f"  {DIM}当前邮箱域名: @{default_domain}{RESET}")
            print(f"  {DIM}大工邮箱有两种域名，请选择你的邮箱后缀:{RESET}")
            print(f"    1. mail.dlut.edu.cn")
            print(f"    2. dlut.edu.cn")
            domain_choice = input(f"  请选择 (1/2){DIM} [{'1' if default_domain == 'mail.dlut.edu.cn' else '2' if default_domain == 'dlut.edu.cn' else ''}]{RESET}: ").strip()
            if domain_choice == "2":
                config["dlut_mail_domain"] = "dlut.edu.cn"
            else:
                config["dlut_mail_domain"] = "mail.dlut.edu.cn"
            mail_domain = config["dlut_mail_domain"]
            print(f"  {GREEN}已选择 @{mail_domain}{RESET}\n")

            password = prompt("DUT 密码", config.get("dlut_password", ""), secret=True)
            config["dlut_password"] = password

            if password:
                print()
                for attempt in range(1, 6):
                    if test_mail(username, password, mail_domain):
                        break
                    if attempt < 5:
                        print(f"  {YELLOW}第 {attempt} 次失败，还剩 {5 - attempt} 次机会{RESET}")
                        password = prompt("DUT 密码", "", secret=True, required=True)
                        config["dlut_password"] = password
                    else:
                        print(f"  {RED}已连续 5 次登录失败，跳过邮箱配置{RESET}")
        else:
            config["dlut_password"] = ""
    else:
        print(f"  {DIM}已跳过大工邮箱配置{RESET}")

    # ━━━ 3. 教务系统 ━━━
    section(
        "🎓 教务系统",
        "用于查询课表、考试安排、期末成绩"
    )
    print(f"  {DIM}通过 CAS 统一认证登录 jxgl.dlut.edu.cn{RESET}\n")

    yn = input(f"  是否配置教务系统？{DIM}(Y/n){RESET}: ").strip().lower()
    if yn != "n":
        # 用户名：默认复用 dlut_username
        default_user = config.get("jxgl_username", "") or config.get("dlut_username", "")
        username = prompt("教务系统用户名", default_user)
        if username:
            config["jxgl_username"] = username

            # 密码：默认复用 dlut_password
            default_pwd = config.get("jxgl_password", "") or config.get("dlut_password", "")
            password = prompt("教务系统密码", default_pwd, secret=True)
            config["jxgl_password"] = password

            if password:
                print()
                for attempt in range(1, 6):
                    ok, msg = _test_jxgl_login(username, password)
                    if ok:
                        print(f"  {GREEN}✅ 教务系统{msg}{RESET}")
                        break
                    print(f"  {RED}❌ 教务系统{msg}{RESET}")
                    if attempt < 5:
                        print(f"  {YELLOW}第 {attempt} 次失败，还剩 {5 - attempt} 次机会{RESET}")
                        password = prompt("教务系统密码", "", secret=True, required=True)
                        config["jxgl_password"] = password
                    else:
                        print(f"  {RED}已连续 5 次登录失败，跳过教务系统配置{RESET}")
        else:
            config["jxgl_password"] = ""
    else:
        print(f"  {DIM}已跳过教务系统配置{RESET}")

    # ━━━ 保存 ━━━
    print(f"\n{BOLD}{CYAN}━━━ 保存配置 ━━━{RESET}\n")

    # 统计配置了多少项
    configured = []
    if config.get("chaoxing_phone") and config["chaoxing_phone"] != "YOUR_PHONE_NUMBER":
        configured.append("超星学习通")
    if config.get("dlut_username"):
        configured.append("邮箱")
        if config.get("jxgl_username"):
            configured.append("教务系统")
    print(f"  已配置服务: {GREEN}{', '.join(configured) if configured else '无'}{RESET}")
    print(f"  配置文件路径: {CONFIG_PATH}")
    print()

    yn = input(f"  确认保存？{DIM}(Y/n){RESET}: ").strip().lower()
    if yn == "n":
        print(f"\n  {YELLOW}已取消，配置未保存{RESET}")
        return

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"\n  {GREEN}{BOLD}✅ 配置完成！{RESET}")
    print(f"  {DIM}配置已保存到 {CONFIG_PATH}{RESET}")
    print(f"""
{CYAN}现在你可以：{RESET}
  • 直接和 AI 对话：{BOLD}"我有什么作业没交？"{RESET}
  • 或手动运行脚本：{BOLD}python3 scripts/chaoxing_api.py ddls{RESET}

{DIM}如需修改配置，重新运行 python3 scripts/setup.py 即可{RESET}
""")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n  {YELLOW}已取消{RESET}")
        sys.exit(0)
