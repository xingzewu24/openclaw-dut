#!/usr/bin/env python3
"""DUT 超星学习通 API — 替代 canvas_api.py

保持函数签名兼容，auto_homework.py / grading_assistant.py / calendar_sync.py 零改动。
认证: 手机号+密码 → AES-CBC 加密 → Cookie 会话
"""

import os
import sys
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

# 内部缓存
_session = None
_course_cache = {}  # courseId(str) -> {courseId, clazzId, cpi, name, teacher}


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


def _login_by_qrcode(s):
    """扫码登录 → 下载服务端二维码图片，终端显示或保存文件，等待手机超星 App 扫码"""
    import io

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

    # 3. 解码二维码图片，提取数据后在终端重新渲染
    print("\n请用「超星学习通」App 扫描二维码登录：\n")
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(qr_bytes))
        try:
            from pyzbar.pyzbar import decode as _pz_decode
            decoded = _pz_decode(img)
            if decoded:
                qr_data = decoded[0].data.decode()
                import qrcode
                qr = qrcode.QRCode(border=1)
                qr.add_data(qr_data)
                qr.make(fit=True)
                qr.print_ascii(invert=True)
                print()
            else:
                raise Exception("pyzbar decode returned empty")
        except ImportError:
            raise Exception("pyzbar not installed")
    except Exception:
        # 解码失败，直接保存图片让用户扫
        import tempfile
        tmp = os.path.join(tempfile.gettempdir(), "chaoxing_qr.jpg")
        with open(tmp, "wb") as f:
            f.write(qr_bytes)
        print(f"  二维码已保存到: {tmp}")
        print(f"  请用超星 App 扫描该图片，或在浏览器中打开查看\n")

    # 4. 轮询扫码状态
    for i in range(60):
        r = s.post(f"{_PASSPORT}/getauthstatus", data={
            "enc": enc,
            "uuid": uuid,
        }, timeout=10)
        try:
            data = r.json()
        except Exception:
            data = {}

        status = data.get("status", -1)
        if status == 1:
            print("✅ 扫码登录成功！")
            return True
        elif status == 0:
            print(f"\r⏳ 等待扫码... ({60 - i}s)", end="", flush=True)
        elif status == 2:
            print("\r⏳ 已扫码，请在手机上确认...", end="", flush=True)
        else:
            print(f"\r⏳ 等待扫码... ({60 - i}s)", end="", flush=True)
        time.sleep(1)

    print("\n❌ 扫码超时")
    return False


def _get_session(profile_name=None):
    global _session
    if _session is not None:
        return _session

    config = load_config()
    phone = config.get("chaoxing_phone", "")
    password = config.get("chaoxing_password", "")
    login_method = config.get("chaoxing_login", "auto")  # auto | phone | qrcode

    s = _new_session()

    # 方式 1: 手机号+密码（如果配置了）
    if phone and password and login_method in ("auto", "phone"):
        try:
            data = _login_by_phone(s, phone, password)
            if data.get("status"):
                print(f"✅ 超星登录成功")
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

    # Cookie 过期 → 重新登录
    if "passport2.chaoxing.com" in r.text or r.status_code == 302:
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

def list_assignments(course_id, profile_name=None):
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

            # workId: 从 data URL 中提取
            data_url = li.get("data", "")
            work_id = _re_first(data_url, r"workId=(\d+)")
            if not work_id:
                work_id = _re_first(html, r"workId[=:](\d+)")
            if not work_id:
                continue

            # 状态
            status_el = li.select_one("p.status")
            status_text = status_el.get_text(strip=True) if status_el else ""

            # 截止时间（超星不在列表页显示，需进入详情页）
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
        # Regex fallback
        for m in re.finditer(
            r'aria-label="([^"]*?)\s*;\s*([^"]*?)"[^>]*data="[^"]*workId=(\d+)',
            r2.text,
        ):
            name = m.group(1).strip()
            status_text = m.group(2).strip()
            work_id = m.group(3)
            submitted = any(k in status_text for k in ("已完成", "已交"))
            graded = "已批" in status_text
            assignments.append({
                "id": int(work_id),
                "name": name,
                "due_at": None,
                "points_possible": None,
                "submission_types": ["online_upload"],
                "description": "",
                "submission": {
                    "workflow_state": "graded" if graded else "submitted" if submitted else "unsubmitted",
                    "score": None,
                    "grade": None,
                },
            })

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
    ddls = _scan_all_ddls(profile_name=profile_name)
    now = datetime.now(TZ_SHANGHAI)
    return [d for d in ddls if d["due_dt"] > now and not d["submitted"]]


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
            assignments = list_assignments(c["id"], profile_name=profile_name)
        except Exception:
            continue

        for a in assignments:
            due_str = a.get("due_at")

            # 超星作业可能无截止时间，设一个远期占位
            if due_str:
                try:
                    due_dt = _parse_date(due_str)
                    if due_dt is None:
                        due_dt = datetime.fromisoformat(
                            due_str.replace("Z", "+00:00")
                        ).astimezone(TZ_SHANGHAI)
                except Exception:
                    due_dt = None
            else:
                due_dt = None

            if due_dt is None:
                due_dt = datetime(now.year, 12, 31, 23, 59, tzinfo=TZ_SHANGHAI)
            elif not due_dt.tzinfo:
                due_dt = due_dt.replace(tzinfo=TZ_SHANGHAI)

            if not include_past and due_str and due_dt < start_dt:
                continue

            sub = a.get("submission", {})
            submitted = sub.get("workflow_state") in ("submitted", "graded")
            graded = sub.get("workflow_state") == "graded"

            meta = _course_cache.get(str(c.get("id", "")), {})

            ddls.append({
                "course": c.get("name", ""),
                "course_id": c.get("id"),
                "assignment": a["name"],
                "assignment_id": a["id"],
                "due_at": due_str,
                "due_dt": due_dt,
                "due_local": (
                    due_dt.strftime("%Y-%m-%d %H:%M") if due_str else "无截止时间"
                ),
                "submitted": submitted,
                "graded": graded,
                "late": False,
                "missing": not submitted and due_dt < now,
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
        upcoming = get_all_upcoming_ddls(profile_name=profile_name)
        if not upcoming:
            print("🎉 没有未交的作业！")
        else:
            print(f"📋 {len(upcoming)} 个未交作业：")
            for d in upcoming:
                hours_left = (d["due_dt"] - datetime.now(TZ_SHANGHAI)).total_seconds() / 3600
                urgency = "🔴" if hours_left < 24 else "🟡" if hours_left < 72 else "🟢"
                print(f"  {urgency} [{d['course']}] {d['assignment']} → {d['due_local']} ({hours_left:.0f}h)")

    elif cmd == "ddls-all":
        report = get_semester_ddl_summary(profile_name=profile_name)
        s = report["stats"]
        print(
            f"📊 本学期DDL全景："
            f"共{s['total']}个 | 已交{s['submitted']} | 已批{s['graded']} | "
            f"迟交{s['late']} | 未交{s['missing']}"
        )
        print(f"\n⏰ 待交 ({s['upcoming_count']}个)：")
        for d in report["upcoming"]:
            hours_left = (d["due_dt"] - datetime.now(TZ_SHANGHAI)).total_seconds() / 3600
            urgency = "🔴" if hours_left < 24 else "🟡" if hours_left < 72 else "🟢"
            print(f"  {urgency} [{d['course']}] {d['assignment']} → {d['due_local']} ({hours_left:.0f}h)")

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
