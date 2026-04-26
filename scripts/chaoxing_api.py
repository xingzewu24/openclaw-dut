#!/usr/bin/env python3
"""DUT 超星学习通 API — 替代 canvas_api.py

保持函数签名兼容，auto_homework.py / grading_assistant.py / calendar_sync.py 零改动。
认证: 手机号+密码 → AES-CBC 加密 → Cookie 会话
"""

import os
import sys

# Windows stdout 默认 gbk，subprocess 捕获时 emoji 会 UnicodeEncodeError
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure") and (_s.encoding or "").lower() != "utf-8":
        _s.reconfigure(encoding="utf-8", errors="replace")
import json
import re
import time
import base64
import platform
import requests
from datetime import datetime, timezone, timedelta

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad as _aes_pad
except ImportError:
    AES = None

# ─── 常量 ───
TZ_SHANGHAI = timezone(timedelta(hours=8))
BASE_URL = "https://dut.fanya.chaoxing.com"
_MOOC1 = "https://mooc1.chaoxing.com"
_MOOC2 = "https://mooc2-ans.chaoxing.com"
_PASSPORT = "https://passport2.chaoxing.com"
_AES_KEY = b"u2oh6Vu^HWe4_AES"

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATHS = [
    os.path.join(SKILL_DIR, "config.json"),
    os.path.expanduser("~/.openclaw/workspace/skills/openclaw-dlut/config.json"),
]
PROFILE_ENV_VAR = "OPENCLAW_DLUT_CHAOXING_PROFILE"

# Cookie 持久化路径
_COOKIE_PATH = os.path.join(SKILL_DIR, ".chaoxing_cookies.json")

# 内部缓存
_session = None
_course_cache = {}  # courseId(str) -> {courseId, clazzId, cpi, name, teacher}


def _save_cookies(session):
    """保存 cookies 到文件"""
    try:
        cookies = dict(session.cookies)
        with open(_COOKIE_PATH, 'w', encoding='utf-8') as f:
            json.dump(cookies, f)
    except Exception as e:
        print(f"⚠️  保存 Cookie 失败: {e}")


def _load_cookies(session):
    """从文件加载 cookies"""
    try:
        if os.path.exists(_COOKIE_PATH):
            with open(_COOKIE_PATH, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            for k, v in cookies.items():
                session.cookies.set(k, v)
            return True
    except Exception as e:
        print(f"⚠️  加载 Cookie 失败: {e}")
    return False


def _delete_cookies():
    """删除持久化的 cookie 文件"""
    try:
        if os.path.exists(_COOKIE_PATH):
            os.remove(_COOKIE_PATH)
    except Exception:
        pass


# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════

def load_config():
    for path in CONFIG_PATHS:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    return {}


# ═══════════════════════════════════════════
# AES 加密
# ═══════════════════════════════════════════

def _aes_encrypt(text):
    if AES is None:
        raise ImportError("需要 pycryptodome: pip install pycryptodome")
    cipher = AES.new(_AES_KEY, AES.MODE_CBC, _AES_KEY)
    return base64.b64encode(cipher.encrypt(_aes_pad(text.encode(), 16))).decode()


# ═══════════════════════════════════════════
# 会话管理
# ═══════════════════════════════════════════

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    if platform.system() == "Windows"
    else "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _new_session():
    s = requests.Session()
    s.headers.update({"User-Agent": _UA})
    return s


def _login_by_phone(s, phone, password):
    """手机号+密码登录 → /fanyalogin"""
    r = s.post(f"{_PASSPORT}/fanyalogin", data={
        "fid": "-1",
        "uname": _aes_encrypt(phone),
        "password": _aes_encrypt(password),
        "refer": "https%3A%2F%2Fi.chaoxing.com",
        "t": "true",
        "forbidotherlogin": "0",
        "validate": "",
        "doubleFactorLogin": "0",
        "independentId": "0",
    })
    return r.json()


def _print_qr_ascii(qr_bytes):
    """终端 ASCII 渲染二维码，弹窗失败时的降级方案。返回是否成功。"""
    try:
        import io
        from PIL import Image
        from pyzbar.pyzbar import decode as _pz_decode
        import qrcode
        img = Image.open(io.BytesIO(qr_bytes))
        decoded = _pz_decode(img)
        if not decoded:
            return False
        qr = qrcode.QRCode(border=1)
        qr.add_data(decoded[0].data.decode())
        qr.make(fit=True)
        qr.print_ascii(invert=True)
        print()
        return True
    except Exception:
        return False


def _show_qr_popup(qr_bytes):
    """Tkinter 弹窗显示二维码。返回 (root, status_var)，失败返回 (None, None)。"""
    try:
        import io
        import tkinter as tk
        from PIL import Image, ImageTk
        root = tk.Tk()
        root.title("超星学习通扫码登录")
        root.attributes("-topmost", True)
        root.resizable(False, False)

        img = Image.open(io.BytesIO(qr_bytes))
        img = img.resize((280, 280), getattr(Image, "Resampling", Image).LANCZOS)
        photo = ImageTk.PhotoImage(img)

        tk.Label(root, text="请用「超星学习通」App 扫码登录",
                 font=("", 13), pady=12).pack()
        img_label = tk.Label(root, image=photo, padx=20)
        img_label.image = photo  # 防 GC
        img_label.pack()

        status_var = tk.StringVar(value="等待扫码...")
        tk.Label(root, textvariable=status_var,
                 font=("", 10), fg="#666", pady=12).pack()

        root.update_idletasks()
        w, h = root.winfo_width(), root.winfo_height()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 3}")
        root.update()
        return root, status_var
    except Exception:
        return None, None


def _login_by_qrcode(s):
    """扫码登录 → 弹窗显示二维码（GUI 不可用时降级为终端 ASCII / 临时文件），等待手机超星 App 扫码"""
    # 1. 获取 uuid 和 enc
    r = s.get(f"{_PASSPORT}/login", params={"fid": "-1"}, timeout=15)
    uuid = _re_first(r.text, r'uuid"\s*value\s*=\s*"([^"]+)"')
    enc = _re_first(r.text, r'enc"\s*value\s*=\s*"([^"]+)"')
    if not uuid:
        uuid = _re_first(r.text, r'uuid=([^&"\']+)')
    if not enc:
        enc = _re_first(r.text, r'enc=([^&"\']+)')

    if not uuid:
        print("❌ 无法获取扫码 uuid")
        return False

    # 2. 下载服务端生成的二维码图片
    qr_url = f"{_PASSPORT}/createqr?uuid={uuid}&fid=-1"
    qr_resp = s.get(qr_url, timeout=10)
    qr_bytes = qr_resp.content

    # 3. 优先弹窗显示，失败降级 ASCII 终端，再失败兜底保存文件并自动打开
    print("\n请用「超星学习通」App 扫描二维码登录\n")
    popup, status_var = _show_qr_popup(qr_bytes)
    if popup is None:
        if not _print_qr_ascii(qr_bytes):
            import tempfile
            tmp = os.path.join(tempfile.gettempdir(), "chaoxing_qr.jpg")
            with open(tmp, "wb") as f:
                f.write(qr_bytes)
            print(f"  二维码已保存到: {tmp}")
            try:
                if sys.platform == "win32":
                    os.startfile(tmp)
                elif sys.platform == "darwin":
                    import subprocess as _sp
                    _sp.Popen(["open", tmp])
                else:
                    import subprocess as _sp
                    _sp.Popen(["xdg-open", tmp])
            except Exception:
                print("  请用超星 App 扫描该图片，或在浏览器中打开查看\n")

    # 4. 轮询扫码状态（GET 方式，兼容性更好）
    success = False
    debug_once = True
    poll_url = f"{_PASSPORT}/getauthstatus"
    try:
        for i in range(60):
            r = s.get(poll_url, params={
                "uuid": uuid,
                "enc": enc or "",
            }, headers={"Referer": f"{_PASSPORT}/login?fid=-1"}, timeout=10)
            try:
                data = r.json()
            except Exception:
                data = {}

            if debug_once:
                print(f"\n[调试] uuid={uuid[:30] if uuid else '(空)'}...")
                print(f"[调试] enc={enc[:30] if enc else '(空)'}...")
                print(f"[调试] 状态码={r.status_code}, 响应: {r.text[:300]}")
                debug_once = False

            status = data.get("status", -1)
            # status: 1=成功, 2=已扫码待确认, 其他=等待中
            if status == 1:
                print("\n✅ 扫码登录成功！")
                _save_cookies(s)
                success = True
                break
            elif status == 2:
                msg = "已扫码，请在手机上确认..."
            else:
                remaining = 60 - i
                msg = f"等待扫码... ({remaining}s)"

            print(f"\r⏳ {msg}", end="", flush=True)

            if popup is not None:
                try:
                    status_var.set(msg)
                    popup.update()
                except Exception:
                    popup = None  # 窗口被用户关闭

            time.sleep(1.5)
        else:
            print("\n❌ 扫码超时")
    finally:
        if popup is not None:
            try:
                popup.destroy()
            except Exception:
                pass

    return success


def _get_session(profile_name=None):
    global _session
    if _session is not None:
        return _session

    config = load_config()
    phone = config.get("chaoxing_phone", "")
    password = config.get("chaoxing_password", "")
    login_method = config.get("chaoxing_login", "auto")  # auto | phone | qrcode

    s = _new_session()

    # 尝试加载已保存的 Cookie（用 passport2 自身接口验证，避免 SSO 跳转误判）
    if _load_cookies(s):
        try:
            r = s.get(f"{_PASSPORT}/mooc/accountManage", timeout=10, allow_redirects=True)
            # 如果被重定向到 login 页面，说明 cookie 已过期
            if "login" not in r.url.lower() and r.status_code == 200:
                print("✅ 使用已保存的 Cookie 登录成功")
                _session = s
                return s
            print("⏳ 已保存的 Cookie 已过期，重新登录...")
        except Exception:
            pass
        # Cookie 无效，清除文件并创建新会话
        _delete_cookies()
        s = _new_session()

    # 方式 1: 手机号+密码（如果配置了）
    if phone and password and login_method in ("auto", "phone"):
        try:
            data = _login_by_phone(s, phone, password)
            if data.get("status"):
                print(f"✅ 超星登录成功")
                _save_cookies(s)
                _session = s
                return s
            msg = data.get("msg2", "")
            if login_method == "phone":
                print(f"ERROR: 超星登录失败: {msg}")
                sys.exit(1)
            print(f"⚠️  手机号+密码登录失败 ({msg})，尝试扫码登录...")
        except Exception as e:
            if login_method == "phone":
                print(f"ERROR: 登录异常: {e}")
                sys.exit(1)
            print(f"⚠️  密码登录异常 ({e})，尝试扫码登录...")

    # 方式 2: 扫码登录
    if login_method in ("auto", "qrcode"):
        if _login_by_qrcode(s):
            _save_cookies(s)
            _session = s
            return s
        if login_method == "qrcode":
            print("ERROR: 扫码登录失败")
            sys.exit(1)

    print("ERROR: 所有登录方式均失败。请检查 config.json 中的 chaoxing_phone / chaoxing_password")
    print("  或设置 \"chaoxing_login\": \"qrcode\" 使用扫码登录")
    sys.exit(1)


def _invalidate_session():
    global _session
    _session = None


def _get_course_meta(course_id):
    cid = str(course_id)
    if cid not in _course_cache:
        list_courses()
    meta = _course_cache.get(cid)
    if not meta:
        raise ValueError(f"课程 {course_id} 未找到（缓存中无此 ID）")
    return meta


# ═══════════════════════════════════════════
# 兼容层 — canvas_api.py 签名
# ═══════════════════════════════════════════

def get_canvas_profile(profile_name=None):
    config = load_config()
    return {
        "name": profile_name or "default",
        "token": config.get("chaoxing_phone", ""),
        "base_url": BASE_URL,
    }


def get_token(profile_name=None):
    return get_canvas_profile(profile_name).get("token", "")


def get_base_url(profile_name=None):
    return BASE_URL


def headers(profile_name=None):
    s = _get_session(profile_name)
    return {"Cookie": "; ".join(f"{k}={v}" for k, v in s.cookies.items())}


def api_get(path, params=None, profile_name=None):
    s = _get_session(profile_name)
    if path.startswith("/mooc"):
        url = f"{_MOOC1}{path}"
    elif path.startswith("/api") or path.startswith("/mooc2"):
        url = f"{_MOOC1}{path}"
    else:
        url = f"{BASE_URL}{path}"
    r = s.get(url, params=params)
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return r.text


# ═══════════════════════════════════════════
# HTML 解析工具
# ═══════════════════════════════════════════

def _re_first(text, pattern):
    m = re.search(pattern, text)
    return m.group(1) if m else ""


def _input_val(el, name):
    inp = (
        el.select_one(f'input[name="{name}"]')
        or el.select_one(f'input#{name}')
        or el.select_one(f'input.{name}')
    )
    return inp.get("value", "") if inp else ""


def _parse_date(text):
    if not text:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y.%m.%d %H:%M",
        "%Y/%m/%d %H:%M",
        "%Y年%m月%d日 %H:%M",
    ):
        try:
            return datetime.strptime(text.strip(), fmt).replace(tzinfo=TZ_SHANGHAI)
        except ValueError:
            continue
    return None


def _parse_short_date(short, ref=None):
    """超星 view/preview 页时间格式仅 'MM-DD HH:MM'，根据当前时间反推年份。

    短时间格式假定属于本学期（≈ 当前 ±6 个月）。如以当前年份解析后落在
    远未来（>150 天后），则视为去年；落在远过去（>200 天前）视为明年。
    """
    if not short:
        return None
    short = short.strip()
    m = re.match(r'^(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})$', short)
    if not m:
        return None
    month, day, hour, minute = map(int, m.groups())
    ref_dt = ref or datetime.now(TZ_SHANGHAI)
    for year in (ref_dt.year, ref_dt.year - 1, ref_dt.year + 1):
        try:
            dt = datetime(year, month, day, hour, minute, tzinfo=TZ_SHANGHAI)
        except ValueError:
            continue
        delta_days = (dt - ref_dt).total_seconds() / 86400
        if -200 <= delta_days <= 150:
            return dt
    try:
        return datetime(ref_dt.year, month, day, hour, minute, tzinfo=TZ_SHANGHAI)
    except ValueError:
        return None


def _fetch_assignment_dates(session, task_url):
    """访问作业 task URL，从 view/preview/dowork 页面抽取起止时间。

    Returns:
        dict: {
            "start_at": ISO 字符串或 None,
            "end_at":   ISO 字符串或 None,
            "status":   "view" | "preview" | "dowork" | "dowork_not_started" | "dowork_blocked" | "unknown",
        }
    """
    result = {"start_at": None, "end_at": None, "status": "unknown"}
    if not task_url:
        return result
    try:
        r = session.get(task_url, allow_redirects=True, timeout=15)
    except Exception:
        return result

    final_url = r.url or ""
    text = r.text or ""

    # 优先匹配标准的 "作答时间:<em>start</em>至<em>end</em>" 格式
    # view/preview/dowork(进行中) 都可能出现
    m_range = re.search(
        r'作答时间[:：][^<]*<em>([^<]+)</em>[^<]*<em>([^<]+)</em>',
        text,
    )
    if m_range:
        start_dt = _parse_short_date(m_range.group(1))
        end_dt = _parse_short_date(m_range.group(2), ref=start_dt)
        if start_dt:
            result["start_at"] = start_dt.isoformat()
        if end_dt:
            result["end_at"] = end_dt.isoformat()
        if "/work/view" in final_url:
            result["status"] = "view"
        elif "/work/preview" in final_url:
            result["status"] = "preview"
        else:
            result["status"] = "dowork"
        return result

    # 未开始情况：dowork 页面的 "开始时间：YYYY-MM-DD HH:MM:SS"
    if "/work/dowork" in final_url:
        m_start = re.search(
            r'开始时间[:：]\s*(\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?)',
            text,
        )
        m_end = re.search(
            r'结束时间[:：]\s*(\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?)',
            text,
        )
        if m_start:
            dt = _parse_date(m_start.group(1))
            if dt:
                result["start_at"] = dt.isoformat()
        if m_end:
            dt = _parse_date(m_end.group(1))
            if dt:
                result["end_at"] = dt.isoformat()
        if m_start or "未开始" in text:
            result["status"] = "dowork_not_started"
        else:
            result["status"] = "dowork_blocked"

    return result


# ═══════════════════════════════════════════
# 用户
# ═══════════════════════════════════════════

def get_me(profile_name=None):
    s = _get_session(profile_name)
    uid = dict(s.cookies).get("_uid", "unknown")
    name = ""
    try:
        r = s.get(f"{_PASSPORT}/mooc/accountManage", timeout=10)
        m = re.search(r'realname["\s:]+([^"&<\s]+)', r.text)
        if m:
            name = m.group(1)
    except Exception:
        pass
    if not name:
        name = load_config().get("chaoxing_phone", uid)
    return {"id": uid, "name": name}


# ═══════════════════════════════════════════
# 课程
# ═══════════════════════════════════════════

def list_courses(profile_name=None):
    s = _get_session(profile_name)
    global _course_cache

    referer = (
        f"{_MOOC2}/mooc2-ans/visit/interaction"
        f"?moocDomain={_MOOC1}/mooc-ans"
    )
    payload = {
        "courseType": 1,
        "courseFolderId": 0,
        "query": "",
        "superstarClass": 0,
    }

    r = s.post(
        f"{_MOOC2}/mooc2-ans/visit/courselistdata",
        data=payload,
        headers={"Referer": referer},
    )

    # Cookie 过期 → 删除文件并重新登录
    if "passport2.chaoxing.com" in r.text or r.status_code == 302:
        _delete_cookies()
        _invalidate_session()
        s = _get_session(profile_name)
        r = s.post(
            f"{_MOOC2}/mooc2-ans/visit/courselistdata",
            data=payload,
            headers={"Referer": referer},
        )

    courses = []

    if BeautifulSoup:
        soup = BeautifulSoup(r.text, "html.parser")
        for div in soup.select("div.course"):
            html = str(div)

            course_id = (
                _input_val(div, "courseId")
                or _re_first(html, r'courseId["\s:=]+["\']?(\d+)')
                or div.get("data-courseid", "")
            )
            clazz_id = (
                _input_val(div, "clazzId")
                or _re_first(html, r'clazzId["\s:=]+["\']?(\d+)')
                or div.get("data-clazzid", "")
            )
            cpi = (
                _input_val(div, "cpi")
                or _re_first(html, r'cpi["\s:=]+["\']?(\d+)')
                or div.get("data-cpi", "")
            )

            title_el = (
                div.select_one(".course-name")
                or div.select_one("h3")
                or div.select_one("a[title]")
            )
            title = (
                (title_el.get("title") or title_el.get_text(strip=True))
                if title_el
                else "未知课程"
            )

            teacher_el = div.select_one(".color3") or div.select_one(".teacher")
            teacher = teacher_el.get_text(strip=True) if teacher_el else ""

            if course_id:
                courses.append({
                    "id": int(course_id),
                    "name": title,
                    "course_code": "",
                    "teacher": teacher,
                    "enrollments": [{"role": "StudentEnrollment"}],
                })
                _course_cache[str(course_id)] = {
                    "courseId": str(course_id),
                    "clazzId": str(clazz_id),
                    "cpi": str(cpi),
                    "name": title,
                    "teacher": teacher,
                }
    else:
        for m in re.finditer(
            r'class="[^"]*course[^"]*"[^>]*>(.*?)</div>', r.text, re.DOTALL
        ):
            html = m.group(1)
            cid = _re_first(html, r'courseId["\s:=]+["\']?(\d+)')
            if not cid:
                continue
            title_m = re.search(r'class="course-name"[^>]*>([^<]+)', html)
            title = title_m.group(1).strip() if title_m else "未知课程"
            courses.append({
                "id": int(cid),
                "name": title,
                "course_code": "",
                "enrollments": [{"role": "StudentEnrollment"}],
            })
            _course_cache[str(cid)] = {
                "courseId": str(cid),
                "clazzId": _re_first(html, r'clazzId["\s:=]+["\']?(\d+)'),
                "cpi": _re_first(html, r'cpi["\s:=]+["\']?(\d+)'),
                "name": title,
            }

    return courses


# ═══════════════════════════════════════════
# 文件 / 课件
# ═══════════════════════════════════════════

def list_course_files(course_id, search_term=None, profile_name=None):
    s = _get_session(profile_name)
    meta = _get_course_meta(course_id)

    # 获取课程章节
    r = s.get(f"{_MOOC2}/mooc2-ans/mycourse/studentcourse", params={
        "courseid": meta["courseId"],
        "clazzid": meta["clazzId"],
        "cpi": meta["cpi"],
        "ut": "s",
    })

    chapter_ids = list(set(re.findall(r'cur(\d+)', r.text)))
    chapter_ids.extend(re.findall(r'knowledgeid["\s:=]+(\d+)', r.text))
    chapter_ids = list(set(chapter_ids))

    files = []
    for ch_id in chapter_ids:
        try:
            ch_files = _get_knowledge_files(s, meta, ch_id)
        except Exception:
            continue
        if search_term:
            ch_files = [
                f for f in ch_files
                if search_term.lower() in f.get("display_name", "").lower()
            ]
        files.extend(ch_files)
        time.sleep(0.3)

    return files


def _get_knowledge_files(s, meta, knowledge_id):
    r = s.get(f"{_MOOC1}/mooc-ans/knowledge/cards", params={
        "clazzid": meta["clazzId"],
        "courseid": meta["courseId"],
        "knowledgeid": knowledge_id,
        "ut": "s",
        "cpi": meta["cpi"],
        "v": time.strftime("%Y-%04m%j-%H%M"),
        "mooc2": "1",
        "num": "0",
    })

    # 解析 mArg = {...}
    m = re.search(r'mArg\s*=\s*(\{.*?\});', r.text, re.DOTALL)
    if not m:
        return []

    try:
        marg = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []

    files = []
    for att in marg.get("attachments", []):
        att_type = att.get("type", "")
        if att_type not in ("document", "pdf"):
            continue

        prop = att.get("property", {})
        obj_id = att.get("objectId", "")
        name = prop.get("name", "")

        files.append({
            "id": obj_id,
            "display_name": name,
            "filename": name,
            "url": obj_id,  # download_file 会用 objectId 解析
            "size": prop.get("size", 0),
            "object_id": obj_id,
            "type": att_type,
        })

    return files


def list_course_folders(course_id, profile_name=None):
    s = _get_session(profile_name)
    meta = _get_course_meta(course_id)

    r = s.get(f"{_MOOC2}/mooc2-ans/mycourse/studentcourse", params={
        "courseid": meta["courseId"],
        "clazzid": meta["clazzId"],
        "cpi": meta["cpi"],
        "ut": "s",
    })

    folders = []
    if BeautifulSoup:
        soup = BeautifulSoup(r.text, "html.parser")
        for ch in soup.select(".chapter_unit"):
            el = ch.select_one(".chapter_item") or ch.select_one("span")
            folders.append({
                "id": ch.get("id", ""),
                "name": el.get_text(strip=True) if el else "未知章节",
                "full_name": el.get_text(strip=True) if el else "",
            })
    else:
        for m in re.finditer(r'id="(cur\d+)"[^>]*>.*?<span[^>]*>([^<]+)</span>', r.text):
            folders.append({
                "id": m.group(1),
                "name": m.group(2).strip(),
                "full_name": m.group(2).strip(),
            })
    return folders


def download_file(file_url, save_path, profile_name=None):
    s = _get_session(profile_name)
    os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)

    url = file_url
    # objectId → 解析真实下载链接
    if not file_url.startswith("http"):
        fid = dict(s.cookies).get("fid", "")
        r = s.get(
            f"{_MOOC1}/ananas/status/{file_url}",
            params={"k": fid, "flag": "normal"},
            timeout=30,
        )
        try:
            meta = r.json()
        except Exception:
            raise ValueError(f"无法解析文件 {file_url}: {r.status_code}")
        url = meta.get("pdf") or meta.get("http") or meta.get("httphd", "")
        if not url:
            raise ValueError(f"文件 {file_url} 无下载链接")

    r = s.get(url, stream=True, timeout=120)
    r.raise_for_status()
    with open(save_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return save_path


def download_course_files(course_id, course_name, save_dir, extensions=None, profile_name=None):
    files = list_course_files(course_id, profile_name=profile_name)
    downloaded = []
    for f in files:
        name = f.get("display_name", "")
        if extensions:
            ext = os.path.splitext(name)[1].lower()
            if ext not in extensions:
                continue
        save_path = os.path.join(save_dir, course_name, name)
        if os.path.exists(save_path):
            downloaded.append(save_path)
            continue
        try:
            download_file(
                f.get("object_id") or f.get("url", ""),
                save_path,
                profile_name=profile_name,
            )
            downloaded.append(save_path)
            print(f"  ✅ {name}")
        except Exception as e:
            print(f"  ❌ {name}: {e}")
    return downloaded


# ═══════════════════════════════════════════
# 作业
# ═══════════════════════════════════════════

def list_assignments(course_id, profile_name=None, fetch_dates=False):
    s = _get_session(profile_name)
    meta = _get_course_meta(course_id)

    # 1. 通过 stucoursemiddle 获取课程 stu 页面
    r_mid = s.get(f"{_MOOC1}/visit/stucoursemiddle", params={
        "courseid": meta["courseId"],
        "clazzid": meta["clazzId"],
        "cpi": meta["cpi"],
        "ismooc2": 1,
        "v": 2,
    }, allow_redirects=True, timeout=15)

    stu_url = r_mid.url
    r_stu = s.get(stu_url, timeout=15)
    work_enc = _re_first(r_stu.text, r'id="workEnc"[^>]*value="([^"]+)"')

    # 2. 获取作业列表
    r2 = s.get(f"{_MOOC1}/mooc2/work/list", params={
        "courseId": meta["courseId"],
        "classId": meta["clazzId"],
        "cpi": meta["cpi"],
        "ut": "s",
        "enc": work_enc,
    }, headers={"Referer": stu_url}, timeout=15)

    assignments = []
    if BeautifulSoup:
        soup = BeautifulSoup(r2.text, "html.parser")
        # 超星作业列表: li[data] 包含作业URL，p.overHidden2 是名称，p.status 是状态
        for li in soup.select(".bottomList li[data]"):
            html = str(li)

            # 名称: 从 aria-label 或 p.overHidden2
            name = ""
            aria = li.get("aria-label", "")
            if aria:
                name = aria.split(";")[0].strip()
            if not name:
                name_el = li.select_one("p.overHidden2")
                name = name_el.get_text(strip=True) if name_el else ""

            # task_url + workId: 从 data 属性提取
            data_url = li.get("data", "")
            work_id = _re_first(data_url, r"workId=(\d+)")
            if not work_id:
                work_id = _re_first(html, r"workId[=:](\d+)")
            if not work_id:
                continue

            # 状态
            status_el = li.select_one("p.status")
            status_text = status_el.get_text(strip=True) if status_el else ""

            # 列表页 HTML 不含截止时间，留空，由 _scan_all_ddls 进入详情页再补
            due_at = None

            # 分值
            points_possible = None

            # 提交状态映射
            submitted = any(k in status_text for k in ("已完成", "已交"))
            graded = any(k in status_text for k in ("已批", "待批阅"))

            assignments.append({
                "id": int(work_id),
                "name": name,
                "due_at": due_at,
                "task_url": data_url,
                "status_text": status_text,
                "points_possible": points_possible,
                "submission_types": ["online_upload"],
                "description": "",
                "submission": {
                    "workflow_state": (
                        "graded" if graded
                        else "submitted" if submitted
                        else "unsubmitted"
                    ),
                    "score": None,
                    "grade": None,
                },
            })
    else:
        # Regex fallback: 同步抓取 data + aria-label + workId
        for m in re.finditer(
            r'data="([^"]+workId=(\d+)[^"]*)"[^>]*aria-label="([^"]+)"',
            r2.text,
        ):
            data_url = m.group(1)
            work_id = m.group(2)
            aria = m.group(3)
            parts = [p.strip() for p in aria.split(";")]
            name = parts[0] if parts else ""
            status_text = parts[1] if len(parts) > 1 else ""

            submitted = any(k in status_text for k in ("已完成", "已交"))
            graded = "已批" in status_text or "待批阅" in status_text
            assignments.append({
                "id": int(work_id),
                "name": name,
                "due_at": None,
                "task_url": data_url,
                "status_text": status_text,
                "points_possible": None,
                "submission_types": ["online_upload"],
                "description": "",
                "submission": {
                    "workflow_state": "graded" if graded else "submitted" if submitted else "unsubmitted",
                    "score": None,
                    "grade": None,
                },
            })

    # 可选：为未提交项填充 due_at（额外 HTTP 开销，按需开启）
    if fetch_dates:
        for a in assignments:
            if a["due_at"]:
                continue
            if a["submission"]["workflow_state"] in ("submitted", "graded"):
                continue
            if not a.get("task_url"):
                continue
            info = _fetch_assignment_dates(s, a["task_url"])
            a["due_at"] = info.get("end_at")
            a["start_at"] = info.get("start_at")
            time.sleep(0.2)

    return assignments


def get_assignment(course_id, assignment_id, profile_name=None):
    s = _get_session(profile_name)
    meta = _get_course_meta(course_id)

    r = s.get(f"{_MOOC1}/mooc-ans/api/work", params={
        "api": "1",
        "workId": str(assignment_id),
        "needRedirect": "true",
        "skipHeader": "true",
        "cpi": meta["cpi"],
        "ut": "s",
        "clazzId": meta["clazzId"],
        "courseid": meta["courseId"],
    })

    result = {
        "id": int(assignment_id),
        "name": "",
        "description": "",
        "due_at": None,
        "points_possible": None,
        "submission_types": ["online_upload"],
        "allowed_extensions": [],
    }

    if BeautifulSoup:
        soup = BeautifulSoup(r.text, "html.parser")
        title_el = (
            soup.select_one(".jobName")
            or soup.select_one("h2")
            or soup.select_one("h3")
        )
        if title_el:
            result["name"] = title_el.get_text(strip=True)

        desc_parts = []
        for q_div in soup.select(".singleQuesId"):
            q_text = q_div.get_text(separator="\n", strip=True)
            desc_parts.append(q_text)
        result["description"] = "\n\n".join(desc_parts) if desc_parts else ""

        date_el = soup.select_one(".jobTime")
        if date_el:
            dt = _parse_date(date_el.get_text(strip=True))
            result["due_at"] = dt.isoformat() if dt else None

        points_el = soup.select_one(".totalScore")
        if points_el:
            pts = _re_first(points_el.get_text(), r'(\d+(?:\.\d+)?)')
            result["points_possible"] = float(pts) if pts else None

    # api/work 通常 403，回退：从作业列表抓 task_url 再访问 view/preview/dowork
    if not result["due_at"] or not result["name"]:
        try:
            for a in list_assignments(course_id, profile_name=profile_name):
                if a["id"] == int(assignment_id):
                    if not result["name"] and a.get("name"):
                        result["name"] = a["name"]
                    if a.get("task_url"):
                        info = _fetch_assignment_dates(s, a["task_url"])
                        if info.get("end_at"):
                            result["due_at"] = info["end_at"]
                    break
        except Exception:
            pass

    return result


def get_my_submission(course_id, assignment_id, profile_name=None):
    assignments = list_assignments(course_id, profile_name=profile_name)
    for a in assignments:
        if a["id"] == int(assignment_id):
            sub = a.get("submission", {})
            return {
                "assignment_id": int(assignment_id),
                "workflow_state": sub.get("workflow_state", "unsubmitted"),
                "score": sub.get("score"),
                "grade": sub.get("grade"),
                "submitted_at": None,
            }
    return {
        "assignment_id": int(assignment_id),
        "workflow_state": "unsubmitted",
        "score": None,
        "grade": None,
    }


def submit_assignment(course_id, assignment_id, file_paths, profile_name=None):
    print("WARNING: 超星作业提交暂未完整实现，请手动提交")
    return {"status": "not_implemented"}


# ═══════════════════════════════════════════
# 成绩
# ═══════════════════════════════════════════

def get_course_grades(course_id, profile_name=None):
    assignments = list_assignments(course_id, profile_name=profile_name)
    s = _get_session(profile_name)
    meta = _get_course_meta(course_id)
    results = []

    for a in assignments:
        score = None
        grade = None

        try:
            r = s.get(f"{_MOOC1}/mooc-ans/api/work", params={
                "api": "1",
                "workId": str(a["id"]),
                "cpi": meta["cpi"],
                "ut": "s",
                "clazzId": meta["clazzId"],
                "courseid": meta["courseId"],
            }, timeout=15)

            if BeautifulSoup:
                soup = BeautifulSoup(r.text, "html.parser")
                score_el = (
                    soup.select_one(".resultNum")
                    or soup.select_one(".Finalresult span")
                )
                if score_el:
                    s_text = _re_first(score_el.get_text(), r'(\d+(?:\.\d+)?)')
                    if s_text:
                        score = float(s_text)
                        grade = str(score)
        except Exception:
            pass

        sub = a.get("submission", {})
        results.append({
            "name": a["name"],
            "points_possible": a.get("points_possible"),
            "score": score,
            "grade": grade,
            "workflow_state": sub.get("workflow_state", ""),
            "due_at": a.get("due_at"),
        })
        time.sleep(0.3)

    return results


# ═══════════════════════════════════════════
# 讨论区（有限支持）
# ═══════════════════════════════════════════

def list_discussions(course_id, profile_name=None):
    return []


def get_full_discussion(course_id, topic_id, profile_name=None):
    return {}


# ═══════════════════════════════════════════
# DDL 汇总
# ═══════════════════════════════════════════

def get_all_upcoming_ddls(profile_name=None):
    """所有未交作业（含已截止和未截止），按截止时间排序"""
    ddls = _scan_all_ddls(profile_name=profile_name)
    return [d for d in ddls if not d["submitted"]]


def get_categorized_unsubmitted_ddls(profile_name=None):
    """未交作业按截止时间分类返回

    Returns:
        dict: {
            "missing": [...],        # 已截止但未交
            "upcoming": [...],       # 未截止待交（含未开始）
            "no_deadline": [...],    # 既无截止也无开始时间
        }
    """
    ddls = _scan_all_ddls(profile_name=profile_name, include_past=True)
    now = datetime.now(TZ_SHANGHAI)

    missing = []     # 已截止未交
    upcoming = []    # 未截止待交（含未开始）
    no_deadline = [] # 真无时间信息

    for d in ddls:
        if d["submitted"]:
            continue
        # 1. 有截止时间
        if d.get("due_at"):
            if d["due_dt"] < now:
                missing.append(d)
            else:
                upcoming.append(d)
        # 2. 未开始：有 start_at 但无 end_at → 视为待办（upcoming）
        elif d.get("start_at"):
            try:
                start_dt = datetime.fromisoformat(d["start_at"])
            except Exception:
                start_dt = None
            if start_dt and start_dt > now:
                d["due_dt"] = start_dt
            upcoming.append(d)
        # 3. 真无时间
        else:
            no_deadline.append(d)

    # 已截止：最近过期的排前面（按 due_dt 降序，最近过期的优先）
    missing.sort(key=lambda x: x["due_dt"], reverse=True)
    # 未截止：最快到期的排前面（按 due_dt 升序）
    upcoming.sort(key=lambda x: x["due_dt"])

    return {
        "missing": missing,
        "upcoming": upcoming,
        "no_deadline": no_deadline,
    }


def get_all_ddls_via_planner(start_date=None, include_past=False, profile_name=None):
    return _scan_all_ddls(
        start_date=start_date,
        include_past=include_past,
        profile_name=profile_name,
    )


def _scan_all_ddls(start_date=None, include_past=False, profile_name=None):
    now = datetime.now(TZ_SHANGHAI)

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=TZ_SHANGHAI)
        except ValueError:
            start_dt = datetime(now.year, 2, 17, tzinfo=TZ_SHANGHAI)
    else:
        start_dt = datetime(now.year, 2, 17, tzinfo=TZ_SHANGHAI)

    courses = list_courses(profile_name=profile_name)
    ddls = []

    for c in courses:
        try:
            assignments = list_assignments(
                c["id"],
                profile_name=profile_name,
                fetch_dates=True,
            )
        except Exception:
            continue

        for a in assignments:
            due_str = a.get("due_at")
            sub = a.get("submission", {})
            submitted = sub.get("workflow_state") in ("submitted", "graded")
            status_text = a.get("status_text", "")
            start_at = a.get("start_at")

            # 解析为 datetime 对象
            due_dt = None
            if due_str:
                try:
                    due_dt = _parse_date(due_str)
                    if due_dt is None:
                        due_dt = datetime.fromisoformat(
                            due_str.replace("Z", "+00:00")
                        ).astimezone(TZ_SHANGHAI)
                except Exception:
                    due_dt = None

            # 真正无截止时间的作业，用占位符以便排序，但保留 due_at=None 标记
            has_deadline = due_dt is not None
            if due_dt is None:
                due_dt = datetime(now.year, 12, 31, 23, 59, tzinfo=TZ_SHANGHAI)
            elif not due_dt.tzinfo:
                due_dt = due_dt.replace(tzinfo=TZ_SHANGHAI)

            if not include_past and has_deadline and due_dt < start_dt:
                continue

            graded = sub.get("workflow_state") == "graded"

            meta = _course_cache.get(str(c.get("id", "")), {})

            # 显示文案
            if has_deadline:
                due_local = due_dt.strftime("%Y-%m-%d %H:%M")
            elif start_at:
                try:
                    start_dt_obj = datetime.fromisoformat(start_at)
                    if start_dt_obj > now:
                        due_local = f"未开始（{start_dt_obj.strftime('%Y-%m-%d %H:%M')} 起）"
                    else:
                        due_local = f"已开始（{start_dt_obj.strftime('%Y-%m-%d %H:%M')}）无截止"
                except Exception:
                    due_local = "未开始"
            elif "未开始" in status_text:
                due_local = "未开始"
            else:
                due_local = "无截止时间"

            ddls.append({
                "course": c.get("name", ""),
                "course_id": c.get("id"),
                "assignment": a["name"],
                "assignment_id": a["id"],
                "due_at": due_str,
                "due_dt": due_dt,
                "due_local": due_local,
                "start_at": start_at,
                "status_text": status_text,
                "submitted": submitted,
                "graded": graded,
                "late": False,
                "missing": not submitted and has_deadline and due_dt < now,
                "needs_grading": False,
                "has_feedback": False,
                "feedback": None,
                "points": a.get("points_possible"),
                "html_url": (
                    f"{BASE_URL}/mycourse/stu"
                    f"?courseid={c.get('id')}"
                    f"&clazzid={meta.get('clazzId', '')}"
                ),
                "is_new": False,
            })

        time.sleep(0.5)

    ddls.sort(key=lambda x: x["due_at"] or "zzz")
    return ddls


def get_semester_ddl_summary(start_date=None, profile_name=None):
    ddls = _scan_all_ddls(start_date=start_date, include_past=True, profile_name=profile_name)
    now = datetime.now(TZ_SHANGHAI)

    total = len(ddls)
    submitted = sum(1 for d in ddls if d["submitted"])
    graded = sum(1 for d in ddls if d["graded"])
    late = sum(1 for d in ddls if d["late"])
    missing = sum(1 for d in ddls if not d["submitted"] and d["due_dt"] < now)
    upcoming = [d for d in ddls if d["due_dt"] > now and not d["submitted"]]
    with_feedback = [d for d in ddls if d["has_feedback"]]

    return {
        "ddls": ddls,
        "stats": {
            "total": total,
            "submitted": submitted,
            "graded": graded,
            "late": late,
            "missing": missing,
            "upcoming_count": len(upcoming),
        },
        "upcoming": upcoming,
        "feedback": with_feedback,
    }


# ═══════════════════════════════════════════
# 日历事件（暂不支持）
# ═══════════════════════════════════════════

def list_calendar_events(course_ids, start_date, end_date, profile_name=None):
    return []


# ═══════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════

def _parse_cli_args(argv):
    profile_name = None
    args = []
    i = 0
    while i < len(argv):
        if argv[i] == "--profile" and i + 1 < len(argv):
            profile_name = argv[i + 1]
            i += 2
            continue
        args.append(argv[i])
        i += 1
    return args, profile_name


if __name__ == "__main__":
    cli_args, profile_name = _parse_cli_args(sys.argv[1:])
    cmd = cli_args[0] if cli_args else "courses"

    if cmd == "courses":
        for c in list_courses(profile_name=profile_name):
            role = (
                ((c.get("enrollments") or [{}])[0].get("role") or "")
                .replace("Enrollment", "")
            )
            suffix = f" [{role}]" if role else ""
            teacher = c.get("teacher", "")
            t_suffix = f" — {teacher}" if teacher else ""
            print(f"[{c['id']}] {c['name']}{suffix}{t_suffix}")

    elif cmd == "ddls":
        cats = get_categorized_unsubmitted_ddls(profile_name=profile_name)
        missing = cats["missing"]
        upcoming = cats["upcoming"]
        no_deadline = cats["no_deadline"]
        total = len(missing) + len(upcoming) + len(no_deadline)

        if total == 0:
            print("🎉 没有未交的作业！")
        else:
            print(f"📋 共 {total} 个未交作业\n")
            now = datetime.now(TZ_SHANGHAI)

            # 1) 未截止待交
            if upcoming:
                print(f"⏳ 未截止待交 ({len(upcoming)}个)：")
                for d in upcoming:
                    if not d.get("due_at"):
                        # 未开始（仅有 start_at）
                        print(f"  🆕 [{d['course']}] {d['assignment']}")
                        print(f"      {d['due_local']}")
                        continue
                    hours_left = (d["due_dt"] - now).total_seconds() / 3600
                    if hours_left < 24:
                        urgency, label = "🔴", f"{hours_left:.0f}h"
                    elif hours_left < 72:
                        urgency, label = "🟡", f"{hours_left:.0f}h"
                    elif hours_left < 24 * 7:
                        urgency, label = "🟢", f"{hours_left/24:.1f}d"
                    else:
                        urgency, label = "🔵", f"{hours_left/24:.0f}d"
                    print(f"  {urgency} [{d['course']}] {d['assignment']}")
                    print(f"      截止 {d['due_local']}  (剩 {label})")
                print()

            # 2) 已截止未交
            if missing:
                print(f"❌ 已截止未交 ({len(missing)}个)：")
                for d in missing:
                    hours_past = (now - d["due_dt"]).total_seconds() / 3600
                    if hours_past < 24:
                        label = f"过期 {hours_past:.0f}h"
                    else:
                        label = f"过期 {hours_past/24:.0f}d"
                    print(f"  💀 [{d['course']}] {d['assignment']}")
                    print(f"      截止 {d['due_local']}  ({label})")
                print()

            # 3) 无截止时间
            if no_deadline:
                print(f"❓ 无截止时间 ({len(no_deadline)}个)：")
                for d in no_deadline:
                    print(f"  ⚪ [{d['course']}] {d['assignment']}")

    elif cmd == "ddls-all":
        report = get_semester_ddl_summary(profile_name=profile_name)
        s = report["stats"]
        print(
            f"📊 本学期DDL全景："
            f"共{s['total']}个 | 已交{s['submitted']} | 已批{s['graded']} | "
            f"迟交{s['late']} | 已截止未交{s['missing']}"
        )

        now = datetime.now(TZ_SHANGHAI)
        unsubmitted = [d for d in report["ddls"] if not d["submitted"]]
        upcoming = []
        missing = []
        no_deadline = []
        for d in unsubmitted:
            if d.get("due_at"):
                if d["due_dt"] > now:
                    upcoming.append(d)
                else:
                    missing.append(d)
            elif d.get("start_at"):
                try:
                    sd = datetime.fromisoformat(d["start_at"])
                    if sd > now:
                        d["due_dt"] = sd
                except Exception:
                    pass
                upcoming.append(d)
            else:
                no_deadline.append(d)

        upcoming.sort(key=lambda x: x["due_dt"])
        missing.sort(key=lambda x: x["due_dt"], reverse=True)

        if upcoming:
            print(f"\n⏳ 未截止待交 ({len(upcoming)}个)：")
            for d in upcoming:
                if not d.get("due_at"):
                    print(f"  🆕 [{d['course']}] {d['assignment']} → {d['due_local']}")
                    continue
                hours_left = (d["due_dt"] - now).total_seconds() / 3600
                if hours_left < 24:
                    urgency, label = "🔴", f"{hours_left:.0f}h"
                elif hours_left < 72:
                    urgency, label = "🟡", f"{hours_left:.0f}h"
                elif hours_left < 24 * 7:
                    urgency, label = "🟢", f"{hours_left/24:.1f}d"
                else:
                    urgency, label = "🔵", f"{hours_left/24:.0f}d"
                print(f"  {urgency} [{d['course']}] {d['assignment']} → {d['due_local']} (剩 {label})")

        if missing:
            print(f"\n❌ 已截止未交 ({len(missing)}个)：")
            for d in missing:
                hours_past = (now - d["due_dt"]).total_seconds() / 3600
                label = f"过期 {hours_past:.0f}h" if hours_past < 24 else f"过期 {hours_past/24:.0f}d"
                print(f"  💀 [{d['course']}] {d['assignment']} → {d['due_local']} ({label})")

        if no_deadline:
            print(f"\n❓ 无截止时间 ({len(no_deadline)}个)：")
            for d in no_deadline:
                print(f"  ⚪ [{d['course']}] {d['assignment']}")

    elif cmd == "grades":
        for c in list_courses(profile_name=profile_name):
            grades = get_course_grades(c["id"], profile_name=profile_name)
            scored = [g for g in grades if g["score"] is not None]
            if scored:
                print(f"\n📚 {c['name']}:")
                for g in scored:
                    print(f"  {g['name']}: {g['score']}/{g['points_possible']}")

    elif cmd == "me":
        me = get_me(profile_name=profile_name)
        print(f"用户: {me['name']} (ID: {me['id']})")

    elif cmd == "files":
        if len(cli_args) < 2:
            print("用法: chaoxing_api.py files <course_id> [search_term]")
        else:
            cid = int(cli_args[1])
            st = cli_args[2] if len(cli_args) > 2 else None
            for f in list_course_files(cid, search_term=st, profile_name=profile_name):
                print(f"  [{f.get('type', '?')}] {f.get('display_name', '?')}")

    else:
        print("超星学习通 API (替代 canvas_api.py)")
        print()
        print("用法:")
        print("  chaoxing_api.py courses            # 列出课程")
        print("  chaoxing_api.py ddls               # 未交作业")
        print("  chaoxing_api.py ddls-all           # 学期全景")
        print("  chaoxing_api.py grades             # 成绩")
        print("  chaoxing_api.py me                 # 用户信息")
        print("  chaoxing_api.py files <cid> [搜索]  # 课程文件")
        print("  chaoxing_api.py --profile <name> <cmd>")
