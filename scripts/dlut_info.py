#!/usr/bin/env python3
"""
大连理工大学校历与校园信息工具
功能：查询校历关键日期、当前教学周、校园概况
"""

import sys

# Windows stdout 默认 gbk，subprocess 捕获时 emoji 会 UnicodeEncodeError
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure") and (_s.encoding or "").lower() != "utf-8":
        _s.reconfigure(encoding="utf-8", errors="replace")
from datetime import datetime, date

# ============================================================
# 硬编码数据 - 2025-2026 学年春季学期 (2026年春)
# ============================================================

SEMESTER_INFO = {
    "semester": "2025-2026学年 春季学期",
    "start_date": "2026-02-23",
    "end_date": "2026-07-05",
    "total_weeks": 19,
    "key_dates": [
        {"date": "2026-02-23", "event": "春季学期开学"},
        {"date": "2026-02-23", "event": "第一周上课"},
        {"date": "2026-03-08", "event": "选课结束 (第二周周日)"},
        {"date": "2026-04-04", "event": "清明节放假 (4/4-4/6)"},
        {"date": "2026-05-01", "event": "劳动节放假 (5/1-5/5)"},
        {"date": "2026-05-31", "event": "端午节放假 (5/31-6/2)"},
        {"date": "2026-06-01", "event": "期中考试周 (约第14-15周)"},
        {"date": "2026-06-22", "event": "期末考试开始 (第18周起)"},
        {"date": "2026-07-05", "event": "暑假开始"},
        {"date": "2026-07-05", "event": "本科生毕业典礼 (约6月底-7月初)"},
    ],
}

CAMPUS_INFO = {
    "凌水校区": {
        "address": "辽宁省大连市甘井子区凌工路2号",
        "description": "主校区，大部分本科和研究生教学在此进行",
        "highlights": ["综合教学1-4号楼", "伯川图书馆", "令希图书馆", "创新园大厦", "各学院楼"],
    },
    "开发区校区": {
        "address": "辽宁省大连市金州区图强路321号",
        "description": "软件学院、国际信息与软件学院所在地",
        "highlights": ["综合教学1-2号楼", "开发区校区图书馆"],
    },
    "盘锦校区": {
        "address": "辽宁省盘锦市大洼区大工路2号",
        "description": "海洋科学与技术学院等所在地",
        "highlights": ["教学楼", "盘锦校区图书馆"],
    },
}


def get_academic_calendar():
    """获取当前学期校历关键日期"""
    return {
        "semester": SEMESTER_INFO["semester"],
        "start_date": SEMESTER_INFO["start_date"],
        "end_date": SEMESTER_INFO["end_date"],
        "total_weeks": SEMESTER_INFO["total_weeks"],
        "key_dates": SEMESTER_INFO["key_dates"],
        "source": "硬编码数据 (如有变动请以学校官方通知为准)",
    }


def get_current_week():
    """计算当前是第几教学周"""
    today = date.today()
    start = date.fromisoformat(SEMESTER_INFO["start_date"])
    end = date.fromisoformat(SEMESTER_INFO["end_date"])

    if today < start:
        delta = (start - today).days
        return {
            "week": 0,
            "day": today.strftime("%Y-%m-%d %A"),
            "semester": SEMESTER_INFO["semester"],
            "status": f"尚未开学，距开学还有 {delta} 天",
        }
    elif today > end:
        return {
            "week": SEMESTER_INFO["total_weeks"],
            "day": today.strftime("%Y-%m-%d %A"),
            "semester": SEMESTER_INFO["semester"],
            "status": "已放假",
        }
    else:
        delta = (today - start).days
        week = delta // 7 + 1
        weekday_cn = {
            "Monday": "周一", "Tuesday": "周二", "Wednesday": "周三",
            "Thursday": "周四", "Friday": "周五", "Saturday": "周六", "Sunday": "周日",
        }.get(today.strftime("%A"), today.strftime("%A"))

        upcoming = []
        for item in SEMESTER_INFO["key_dates"]:
            event_date = date.fromisoformat(item["date"])
            diff = (event_date - today).days
            if -1 <= diff <= 14:
                upcoming.append(f"{item['event']} ({item['date']})")

        return {
            "week": week,
            "day": f"{today.strftime('%Y-%m-%d')} {weekday_cn}",
            "semester": SEMESTER_INFO["semester"],
            "status": f"第 {week} 教学周 {weekday_cn}",
            "upcoming": upcoming if upcoming else None,
        }


def get_campus_info():
    """获取校区概况"""
    return CAMPUS_INFO


def _print_calendar():
    """终端输出校历"""
    cal = get_academic_calendar()
    print(f"\n{cal['semester']}")
    print("=" * 50)
    print(f"  学期: {cal['start_date']} -> {cal['end_date']}")
    print(f"  共 {cal['total_weeks']} 个教学周")
    print(f"\n  关键日期:")
    for item in cal["key_dates"]:
        print(f"     {item['date']}  {item['event']}")
    print(f"\n  {cal.get('source', '')}")
    print()


def _print_week():
    """终端输出当前教学周"""
    info = get_current_week()
    print(f"\n教学周信息")
    print("=" * 40)
    print(f"  {info['status']}")
    print(f"  日期: {info['day']}")
    print(f"  学期: {info['semester']}")
    if info.get("upcoming"):
        print(f"\n  近期事件:")
        for ev in info["upcoming"]:
            print(f"     {ev}")
    print()


def _print_campus():
    """终端输出校区概况"""
    campuses = get_campus_info()
    print(f"\n大连理工大学校区概况")
    print("=" * 50)
    for name, info in campuses.items():
        print(f"\n  {name}")
        print(f"    地址: {info['address']}")
        print(f"    说明: {info['description']}")
        print(f"    标志: {', '.join(info['highlights'])}")
    print()


def main():
    if len(sys.argv) < 2:
        print("用法: python3 dlut_info.py <命令>")
        print("  calendar  - 查看校历")
        print("  week      - 当前教学周")
        print("  campus    - 校区概况")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    try:
        if cmd == "calendar":
            _print_calendar()
        elif cmd == "week":
            _print_week()
        elif cmd == "campus":
            _print_campus()
        else:
            print(f"未知命令: {cmd}")
            print("可用命令: calendar / week / campus")
            sys.exit(1)
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
