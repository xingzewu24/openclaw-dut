#!/usr/bin/env python3
"""大连理工大学教务系统 API — 课表 / 考试 / 成绩查询

认证: CAS SSO (sso.dlut.edu.cn) → jxgl.dlut.edu.cn/student/ucas-sso/login
数据: 课表/成绩走 JSON API，考试从服务端渲染 HTML 提取
"""

import os
import re
import sys

# Windows stdout 默认 gbk，subprocess 捕获时 emoji 会 UnicodeEncodeError
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure") and (_s.encoding or "").lower() != "utf-8":
        _s.reconfigure(encoding="utf-8", errors="replace")
import json
import platform
import requests
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser

# ─── 常量 ───
TZ_SHANGHAI = timezone(timedelta(hours=8))
CAS_BASE = "https://sso.dlut.edu.cn"
JXGL_BASE = "http://jxgl.dlut.edu.cn"
JXGL_SSO_PATH = "/student/ucas-sso/login"

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATHS = [
    os.path.join(SKILL_DIR, "config.json"),
    os.path.join(os.path.expanduser("~/.openclaw/workspace/skills/openclaw-dut"), "config.json"),
]

_IS_MACOS = platform.system() == "Darwin"
_IS_WINDOWS = platform.system() == "Windows"

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    if _IS_WINDOWS
    else "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_session = None
_student_id = None


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
# CAS 登录页隐藏字段提取
# ═══════════════════════════════════════════

class _CASFormParser(HTMLParser):
    """从 CAS 登录页 HTML 提取 lt / execution 等隐藏字段"""

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


def _des_encrypt(data, first_key="1", second_key="2", third_key="3"):
    """CAS 登录 DES 加密：strEnc(username+password+lt, '1', '2', '3')"""
    import execjs
    des_js_path = os.path.join(os.path.dirname(__file__), "..", "vendor", "des.js")
    if not os.path.exists(des_js_path):
        # 首次使用，下载 des.js 到本地缓存
        r = requests.get(f"{CAS_BASE}/cas/comm/js/des.js?v=20240515", timeout=15)
        r.raise_for_status()
        os.makedirs(os.path.dirname(des_js_path), exist_ok=True)
        with open(des_js_path, "w") as f:
            f.write(r.text)
    with open(des_js_path) as f:
        ctx = execjs.compile(f.read())
    return ctx.call("strEnc", data, first_key, second_key, third_key)


def _extract_cas_fields(html):
    parser = _CASFormParser()
    parser.feed(html)
    return parser.fields


# ═══════════════════════════════════════════
# CAS 认证
# ═══════════════════════════════════════════

def cas_login(username, password):
    """CAS SSO 登录 → 返回已认证的 requests.Session

    流程:
    1. GET jxgl SSO 入口 → 跳转到 CAS login page（含 service 参数）
    2. 提取 CAS 登录页 lt/execution → DES 加密
    3. POST 加密凭证 → CAS 回调 jxgl（携带 ServiceTicket）→ 完成认证
    """
    s = requests.Session()
    s.headers.update({"User-Agent": _UA})

    # Step 1: 访问教务系统 SSO 入口，获取 CAS 登录页 URL
    sso_entry = f"{JXGL_BASE}{JXGL_SSO_PATH}"
    r = s.get(sso_entry, timeout=15, allow_redirects=False)
    if r.status_code not in (301, 302, 307):
        raise RuntimeError(f"教务系统 SSO 入口未跳转 (HTTP {r.status_code})")
    cas_login_url = r.headers["Location"]

    # Step 2: 获取 CAS 登录页
    r = s.get(cas_login_url, timeout=15)
    r.raise_for_status()

    if "系统提示" in r.text and "请求出错" in r.text:
        raise RuntimeError("CAS 登录页返回异常（HTTP 500），service URL 可能不被允许")

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

    # 成功跳转回教务系统（携带 ticket 完成认证）
    if r.url.startswith(JXGL_BASE):
        return s

    # 还在 CAS 登录页 → 密码错误
    if "lt" in r.text and "username" in r.text:
        raise RuntimeError("CAS 登录失败：用户名或密码错误")

    if "errormsg" in r.text.lower() or "密码错误" in r.text or "用户名或密码" in r.text:
        raise RuntimeError("CAS 登录失败：用户名或密码错误")

    return s


def test_cas_login(username, password):
    """测试 CAS 登录，返回 (success, message)"""
    try:
        s = cas_login(username, password)
        r = s.get(f"{JXGL_BASE}/student/home", timeout=10, allow_redirects=False)
        if r.status_code in (200, 302):
            return True, "登录成功"
        return False, f"意外响应: HTTP {r.status_code}"
    except RuntimeError as e:
        return False, str(e)
    except Exception as e:
        return False, f"连接失败: {e}"


def get_session():
    """获取已认证的 session（懒加载，全局缓存）"""
    global _session
    if _session is not None:
        return _session

    config = load_config()
    username = config.get("jxgl_username", "")
    password = config.get("jxgl_password", "")

    if not username or not password:
        print("ERROR: 未配置教务系统账号。请运行 python3 scripts/setup.py 或在 config.json 中填写 jxgl_username / jxgl_password")
        sys.exit(1)

    s = cas_login(username, password)
    _session = s
    return s


# ═══════════════════════════════════════════
# 辅助
# ═══════════════════════════════════════════

def _get_student_id(session):
    """从考试页面 302 跳转中提取 studentId"""
    global _student_id
    if _student_id is not None:
        return _student_id
    r = session.get(f"{JXGL_BASE}/student/for-std/exam-arrange",
                     timeout=15, allow_redirects=True)
    m = re.search(r"/exam-arrange/info/(\d+)", r.url)
    if not m:
        raise RuntimeError("无法获取 studentId")
    _student_id = int(m.group(1))
    return _student_id


def _get_semester_info(session):
    """从课表页面提取学期列表和当前学期 ID"""
    r = session.get(f"{JXGL_BASE}/student/for-std/course-table", timeout=15)
    # 提取 semesters JSON（JS 中用单引号包裹，含 unicode 转义）
    m = re.search(r"var semesters\s*=\s*JSON\.parse\(\s*'(.+?)'\s*\);", r.text)
    if not m:
        raise RuntimeError("无法解析学期列表")
    raw = m.group(1).encode("utf-8").decode("unicode_escape")
    semesters = json.loads(raw)
    # 提取当前学期 id — 根据 today 落在哪个学期的 startDate~endDate 区间
    now = datetime.now(TZ_SHANGHAI)
    current_id = semesters[0]["id"]
    for sem in semesters:
        sd = datetime.strptime(sem["startDate"], "%Y-%m-%d").replace(tzinfo=TZ_SHANGHAI)
        ed = datetime.strptime(sem["endDate"], "%Y-%m-%d").replace(tzinfo=TZ_SHANGHAI)
        if sd <= now <= ed:
            current_id = sem["id"]
            break
    return semesters, current_id


# ═══════════════════════════════════════════
# 数据查询
# ═══════════════════════════════════════════

def get_courses(session):
    """查询当前学期课表 → 返回 list[dict]

    每个 dict: {name, teacher, time, location, weeks}
    """
    _, semester_id = _get_semester_info(session)
    r = session.get(
        f"{JXGL_BASE}/student/for-std/course-table/get-data",
        params={"bizTypeId": 2, "semesterId": semester_id},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    results = []
    for lesson in data.get("lessons", []):
        # 教师列表
        teachers = []
        for ta in lesson.get("teacherAssignmentList", []):
            if ta.get("role") == "MAJOR":
                teachers.append(ta["person"]["nameZh"])
        teacher_str = "; ".join(teachers) if teachers else ""
        # 时间地点 — 用 dateTimePlaceText（含地点不含教师）
        dt_text = lesson.get("scheduleText", {}).get("dateTimeText", {}).get("textZh", "")
        dtp_text = lesson.get("scheduleText", {}).get("dateTimePlaceText", {}).get("textZh", "")
        # 提取地点: 从完整文本中去掉时间部分，取第一个地点
        location = ""
        if dt_text and dtp_text:
            # dtp_text 可能是多行，每行格式: "1~12周 周四 ... 教学楼 教室"
            first_line = dtp_text.split("\n")[0].strip()
            # 去掉时间前缀
            time_part = dt_text.split(";")[0].strip()
            location = first_line.replace(time_part, "").strip()
        # 从时间文本中提取周次
        weeks = ""
        wm = re.match(r"([\d~]+周)", dt_text)
        if wm:
            weeks = wm.group(1)

        results.append({
            "name": lesson.get("nameZh", ""),
            "teacher": teacher_str,
            "time": dt_text,
            "location": location,
            "weeks": weeks,
        })
    return results


def get_exams(session):
    """查询考试安排 → 返回 list[dict]

    每个 dict: {name, datetime, location, building, campus, seat}
    """
    student_id = _get_student_id(session)
    r = session.get(
        f"{JXGL_BASE}/student/for-std/exam-arrange/info/{student_id}",
        timeout=15,
    )
    r.raise_for_status()
    html = r.text
    # 考试数据在 <table id="exams"> 中
    # 每行: <tr><td>课程</td><td class="time">时间</td><td>考场</td><!-- comment --><td>楼宇</td><td>校区</td></tr>
    rows = re.findall(
        r"<tr>\s*<td>\s*(.+?)\s*</td>\s*"
        r'<td class="time">(.+?)</td>\s*'
        r"<td>(.*?)</td>\s*"
        r"(?:<!--.*?-->\s*)?"
        r"<td>(.*?)</td>\s*"
        r"<td>(.*?)</td>",
        html,
        re.S,
    )
    results = []
    for name_raw, time_str, location_raw, building, campus in rows:
        name = re.sub(r"<[^>]+>", "", name_raw).strip()
        if not name:
            continue
        location = re.sub(r"<[^>]+>", "", location_raw).strip()
        # 解析时间: "2026-05-10 10:05~11:45"
        dt = None
        tm = re.match(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})", time_str)
        if tm:
            dt = datetime.strptime(f"{tm.group(1)} {tm.group(2)}", "%Y-%m-%d %H:%M")
            dt = dt.replace(tzinfo=TZ_SHANGHAI)
        results.append({
            "name": name,
            "datetime": dt,
            "location": location,
            "building": building.strip(),
            "campus": campus.strip(),
            "seat": "",
        })
    # 过滤：考试结束一天后不再显示
    now = datetime.now(TZ_SHANGHAI)
    results = [
        ex for ex in results
        if ex["datetime"] is None or ex["datetime"] + timedelta(days=1) > now
    ]
    return results


def get_grades(session):
    """查询所有学期成绩 → 返回 list[dict]

    每个 dict: {semester, name, credit, score, gp, passed}
    """
    student_id = _get_student_id(session)
    r = session.get(
        f"{JXGL_BASE}/student/for-std/grade/sheet/info/{student_id}",
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    grades_map = data.get("semesterId2studentGrades", {})
    id2semesters = data.get("id2semesters", {})

    results = []
    # 按学期倒序输出（最新在前）
    for sem_id in sorted(grades_map.keys(), key=lambda x: int(x), reverse=True):
        sem_name = id2semesters.get(sem_id, {}).get("nameZh", f"学期{sem_id}")
        for g in grades_map[sem_id]:
            course = g.get("course", {})
            results.append({
                "semester": sem_name,
                "name": course.get("nameZh", ""),
                "credit": course.get("credits", 0),
                "score": g.get("score", "") or "",
                "gp": g.get("gp", ""),
                "passed": g.get("passed", ""),
            })
    return results


# ═══════════════════════════════════════════
# 考试日历同步
# ═══════════════════════════════════════════

def _build_exam_ics(exams):
    """将考试列表转为 ICS 内容"""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//DUT JXGL//Exam Sync//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:教务考试",
        "X-WR-TIMEZONE:Asia/Shanghai",
        "BEGIN:VTIMEZONE",
        "TZID:Asia/Shanghai",
        "BEGIN:STANDARD",
        "DTSTART:19700101T000000",
        "TZOFFSETFROM:+0800",
        "TZOFFSETTO:+0800",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]

    import hashlib
    for ex in exams:
        dt = ex["datetime"]
        uid = hashlib.md5(f"{ex['name']}_{dt}".encode()).hexdigest()[:12]
        summary = f"📝 {ex['name']}".replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
        desc = f"地点: {ex.get('location', '待定')}\\n座位号: {ex.get('seat', '待定')}"
        utc_start = dt.astimezone(timezone.utc)
        utc_end = (dt + timedelta(hours=2)).astimezone(timezone.utc)

        lines += [
            "BEGIN:VEVENT",
            f"UID:exam-{uid}@dlut-jxgl",
            f"DTSTART:{utc_start.strftime('%Y%m%dT%H%M%SZ')}",
            f"DTEND:{utc_end.strftime('%Y%m%dT%H%M%SZ')}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{desc}",
            "BEGIN:VALARM",
            "TRIGGER:-P1D",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{ex['name']} 明天考试!",
            "END:VALARM",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def exams_to_ics(exams, output_path=None):
    """导出考试为 ICS 文件"""
    ics = _build_exam_ics(exams)
    if not output_path:
        output_path = os.path.join(os.path.expanduser("~"), "Downloads", "jxgl_exams.ics")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ics)
    return output_path


def sync_exams_to_calendar(exams):
    """同步考试到系统日历（macOS AppleScript / Windows ICS）"""
    cal_name = load_config().get("calendar_name", "教务考试")

    if _IS_MACOS:
        subprocess_run = __import__("subprocess").run
        subprocess_run(["open", "-a", "Calendar"], capture_output=True)
        import time; time.sleep(2)

        # 确保日历存在
        script = f'''
tell application "Calendar"
    set calNames to name of every calendar
    if calNames does not contain "{cal_name}" then
        make new calendar with properties {{name:"{cal_name}"}}
    end if
end tell'''
        subprocess_run(["osascript", "-e", script], capture_output=True, timeout=30)

        # 列出已有事件用于去重
        script = f'''
tell application "Calendar"
    tell calendar "{cal_name}"
        set eventList to {{}}
        repeat with e in events
            set end of eventList to summary of e
        end repeat
        return eventList
    end tell
end tell'''
        r = subprocess_run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)
        existing = [s.strip() for s in r.stdout.strip().split(",")] if r.returncode == 0 else []

        synced, skipped = 0, 0
        for ex in exams:
            summary = f"📝 {ex['name']}"
            if summary in existing:
                skipped += 1
                continue

            dt = ex["datetime"]
            end_dt = dt + timedelta(hours=2)
            desc = f"地点: {ex.get('location', '待定')}\\n座位号: {ex.get('seat', '待定')}"
            script = f'''
tell application "Calendar"
    tell calendar "{cal_name}"
        set startDate to current date
        set year of startDate to {dt.year}
        set month of startDate to {dt.month}
        set day of startDate to {dt.day}
        set hours of startDate to {dt.hour}
        set minutes of startDate to {dt.minute}
        set seconds of startDate to 0

        set endDate to current date
        set year of endDate to {end_dt.year}
        set month of endDate to {end_dt.month}
        set day of endDate to {end_dt.day}
        set hours of endDate to {end_dt.hour}
        set minutes of endDate to {end_dt.minute}
        set seconds of endDate to 0

        make new event with properties {{summary:"{summary}", start date:startDate, end date:endDate, description:"{desc}"}}
    end tell
end tell'''
            r = subprocess_run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                print(f"  ✅ {ex['name']} → {dt.strftime('%Y-%m-%d %H:%M')}")
                synced += 1
            else:
                print(f"  ❌ {ex['name']}")
        print(f"\n同步完成: {synced} 新增, {skipped} 已存在")
        return synced
    else:
        # Windows / Linux: 生成 ICS
        path = exams_to_ics(exams)
        print(f"ICS 文件已生成: {path}")
        if _IS_WINDOWS:
            os.startfile(path)
        return len(exams)


# ═══════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="大连理工大学教务系统")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("courses", help="查询课表")
    sub.add_parser("exams", help="查询考试安排")
    sub.add_parser("grades", help="查询成绩")

    p_ics = sub.add_parser("exams-ics", help="导出考试为 ICS 文件")
    p_ics.add_argument("--output", "-o", help="输出路径")

    sub.add_parser("exams-sync", help="考试同步到日历")

    sub.add_parser("login", help="测试 CAS 登录")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    if args.cmd == "login":
        config = load_config()
        username = config.get("jxgl_username", "")
        password = config.get("jxgl_password", "")
        if not username or not password:
            print("ERROR: 未配置教务系统账号")
            sys.exit(1)
        ok, msg = test_cas_login(username, password)
        if ok:
            print(f"✅ {msg}")
        else:
            print(f"❌ {msg}")
            sys.exit(1)
        return

    s = get_session()

    if args.cmd == "courses":
        courses = get_courses(s)
        for c in courses:
            print(f"{c['name']}\t{c['teacher']}\t{c['time']}\t{c['location']}\t{c['weeks']}")

    elif args.cmd == "exams":
        exams = get_exams(s)
        for ex in exams:
            dt = ex.get("datetime", "")
            if isinstance(dt, datetime):
                dt = dt.strftime("%Y-%m-%d %H:%M")
            print(f"{ex['name']}\t{dt}\t{ex.get('location', '')}\t{ex.get('seat', '')}")

    elif args.cmd == "grades":
        grades = get_grades(s)
        for g in grades:
            print(f"{g['semester']}\t{g['name']}\t{g['credit']}\t{g['score']}")

    elif args.cmd == "exams-ics":
        exams = get_exams(s)
        path = exams_to_ics(exams, args.output)
        print(f"ICS 已导出: {path} ({len(exams)} 场考试)")

    elif args.cmd == "exams-sync":
        exams = get_exams(s)
        sync_exams_to_calendar(exams)


if __name__ == "__main__":
    main()
