#!/usr/bin/env python3
"""DDL → 日历同步工具（跨平台：macOS Apple Calendar / Windows 默认日历）"""

import os
import sys

# Windows stdout 默认 gbk，subprocess 捕获时 emoji 会 UnicodeEncodeError
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure") and (_s.encoding or "").lower() != "utf-8":
        _s.reconfigure(encoding="utf-8", errors="replace")
import subprocess
import platform
import json
from datetime import datetime, timezone, timedelta

TZ_SHANGHAI = timezone(timedelta(hours=8))
CALENDAR_NAME = "超星作业"
_IS_MACOS = platform.system() == "Darwin"
_IS_WINDOWS = platform.system() == "Windows"


def _macos_ensure_calendar():
    """macOS: 确保 Canvas作业 日历存在"""
    script = f'''
tell application "Calendar"
    set calNames to name of every calendar
    if calNames does not contain "{CALENDAR_NAME}" then
        make new calendar with properties {{name:"{CALENDAR_NAME}"}}
    end if
end tell
'''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)
    return r.returncode == 0


def _macos_create_event(summary, due_dt, description=""):
    """macOS: 在 Apple Calendar 创建事件"""
    script = f'''
tell application "Calendar"
    tell calendar "{CALENDAR_NAME}"
        set startDate to current date
        set year of startDate to {due_dt.year}
        set month of startDate to {due_dt.month}
        set day of startDate to {due_dt.day}
        set hours of startDate to {max(0, due_dt.hour - 1)}
        set minutes of startDate to 0
        set seconds of startDate to 0

        set endDate to current date
        set year of endDate to {due_dt.year}
        set month of endDate to {due_dt.month}
        set day of endDate to {due_dt.day}
        set hours of endDate to {due_dt.hour}
        set minutes of endDate to {due_dt.minute}
        set seconds of endDate to 0

        make new event with properties {{summary:"{summary}", start date:startDate, end date:endDate, description:"{description}"}}
    end tell
end tell
'''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)
    return r.returncode == 0


def _macos_list_existing_events():
    """macOS: 列出 Canvas作业 日历中的现有事件"""
    script = f'''
tell application "Calendar"
    tell calendar "{CALENDAR_NAME}"
        set eventList to {{}}
        repeat with e in events
            set end of eventList to summary of e
        end repeat
        return eventList
    end tell
end tell
'''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)
    if r.returncode == 0:
        return [s.strip() for s in r.stdout.strip().split(",")]
    return []


def _ics_build_content(events):
    """生成 ICS 文件内容"""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//DUT Chaoxing//Calendar Sync//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:DUT Chaoxing DDL",
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

    for ev in events:
        utc_start = ev["start"].astimezone(timezone.utc)
        utc_end = ev["end"].astimezone(timezone.utc)
        summary = ev["summary"].replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
        desc = ev.get("description", "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

        lines += [
            "BEGIN:VEVENT",
            f"UID:{ev['uid']}",
            f"DTSTART:{utc_start.strftime('%Y%m%dT%H%M%SZ')}",
            f"DTEND:{utc_end.strftime('%Y%m%dT%H%M%SZ')}",
            f"SUMMARY:{summary}",
        ]
        if desc:
            lines.append(f"DESCRIPTION:{desc}")
        lines += [
            "BEGIN:VALARM",
            "TRIGGER:-PT1H",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{summary} 即将截止!",
            "END:VALARM",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def _sync_via_ics(ddls):
    """跨平台: 生成 ICS 文件并用系统默认程序打开"""
    import hashlib
    now = datetime.now(TZ_SHANGHAI)
    events = []
    for d in ddls:
        due_str = d["due_at"]
        due_dt = datetime.fromisoformat(due_str.replace("Z", "+00:00")).astimezone(TZ_SHANGHAI)
        if due_dt < now:
            continue
        summary = f"📝 [{d['course']}] {d['assignment']}"
        h = hashlib.md5(summary.encode()).hexdigest()[:12]
        events.append({
            "uid": f"ddl-{h}@dlut-chaoxing",
            "start": due_dt - timedelta(minutes=30),
            "end": due_dt,
            "summary": summary,
            "description": f"课程: {d['course']}\n作业: {d['assignment']}\nDDL: {d['due_local']}\n满分: {d.get('points', '?')}",
        })

    if not events:
        print("没有未来的DDL需要同步")
        return 0

    ics_content = _ics_build_content(events)
    ics_path = os.path.join(os.path.expanduser("~"), "Downloads", "ddl_sync.ics")
    os.makedirs(os.path.dirname(ics_path), exist_ok=True)
    with open(ics_path, "w", encoding="utf-8") as f:
        f.write(ics_content)

    print(f"ICS 文件已生成: {ics_path}")

    # 用系统默认程序打开
    if _IS_MACOS:
        subprocess.run(["open", ics_path], capture_output=True)
    elif _IS_WINDOWS:
        os.startfile(ics_path)
    else:
        print(f"请手动导入 ICS 文件: {ics_path}")

    return len(events)


def sync_ddls(ddls):
    """同步 DDL 列表到日历（跨平台）"""
    if _IS_MACOS:
        # macOS: 使用 AppleScript 直接同步
        subprocess.run(["open", "-a", "Calendar"], capture_output=True)
        import time; time.sleep(2)

        _macos_ensure_calendar()
        existing = _macos_list_existing_events()

        synced = 0
        skipped = 0
        for d in ddls:
            summary = f"📝 [{d['course']}] {d['assignment']}"
            if summary in existing:
                skipped += 1
                continue

            due_str = d["due_at"]
            due_dt = datetime.fromisoformat(due_str.replace("Z", "+00:00")).astimezone(TZ_SHANGHAI)
            desc = f"课程: {d['course']}\n作业: {d['assignment']}\nDDL: {d['due_local']}\n满分: {d.get('points', '?')}"

            if _macos_create_event(summary, due_dt, desc):
                print(f"✅ {summary} → {d['due_local']}")
                synced += 1
            else:
                print(f"❌ {summary}")

        print(f"\n同步完成: {synced} 新增, {skipped} 已存在")
        return synced
    else:
        # Windows / Linux: 生成 ICS 并打开
        count = _sync_via_ics(ddls)
        print(f"\n同步完成: {count} 个 DDL 已导出为 ICS 文件")
        if _IS_WINDOWS:
            print("提示: ICS 文件会自动用 Windows 日历打开，确认导入即可")
        else:
            print("提示: 请将 ICS 文件导入到你的日历应用中")
        return count


if __name__ == "__main__":
    from chaoxing_api import get_all_upcoming_ddls
    ddls = get_all_upcoming_ddls()
    if not ddls:
        print("没有未来的DDL")
    else:
        print(f"找到 {len(ddls)} 个未来DDL:")
        sync_ddls(ddls)
