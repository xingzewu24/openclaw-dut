#!/usr/bin/env python3
"""
大连理工大学校历与校园信息工具
功能：查询校历关键日期、当前教学周、校园概况

学期起止、总周数等数据优先从教务系统 jxgl.dlut.edu.cn 动态获取。
教务系统不可用时回退到硬编码 fallback 数据。
放假日期通过 chinese-calendar 库动态获取。
"""

import os
import sys

# Windows stdout 默认 gbk，subprocess 捕获时 emoji 会 UnicodeEncodeError
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure") and (_s.encoding or "").lower() != "utf-8":
        _s.reconfigure(encoding="utf-8", errors="replace")
from datetime import datetime, date, timedelta


# ============================================================
# 硬编码数据
# ============================================================

# Fallback 学期数据（教务系统不可用时使用，需按学年更新）
FALLBACK_SEMESTER = {
    "name": "2025-2026学年 春季学期",
    "start_date": "2026-03-02",
    "end_date": "2026-06-28",
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


def _get_semester_from_jxgl():
    """从教务系统 jxgl.dlut.edu.cn 获取当前学期信息"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        from dlut_jxgl import get_session, _get_semester_info

        s = get_session()
        semesters, current_id = _get_semester_info(s)
        current = next((s for s in semesters if s["id"] == current_id), None)
        if not current:
            return None

        start = date.fromisoformat(current["startDate"])
        end = date.fromisoformat(current["endDate"])
        total_weeks = (end - start).days // 7 + 1

        return {
            "name": current["nameZh"],
            "start_date": current["startDate"],
            "end_date": current["endDate"],
            "total_weeks": total_weeks,
        }
    except SystemExit:
        # get_session() 在未配置账号时会 sys.exit(1)
        return None
    except Exception:
        return None


def get_holidays_in_range(start_date, end_date):
    """获取指定日期范围内的中国法定节假日区间（含调休连休）

    Returns:
        list[dict]: [{"name": "清明节", "start": date, "end": date}, ...]
    """
    from chinese_calendar import get_holiday_detail

    NAME_MAP = {
        "New Year's Day": "元旦",
        "Spring Festival": "春节",
        "Tomb-sweeping Day": "清明节",
        "Labour Day": "劳动节",
        "Dragon Boat Festival": "端午节",
        "Mid-Autumn Festival": "中秋节",
        "National Day": "国庆节",
    }

    holiday_dates = []
    for n in range((end_date - start_date).days + 1):
        d = start_date + timedelta(days=n)
        is_hol, name = get_holiday_detail(d)
        if is_hol and name:
            holiday_dates.append((d, name))

    if not holiday_dates:
        return []

    intervals = []
    cur_start = holiday_dates[0][0]
    cur_end = holiday_dates[0][0]
    cur_name = holiday_dates[0][1]

    for d, name in holiday_dates[1:]:
        if d == cur_end + timedelta(days=1) and name == cur_name:
            cur_end = d
        else:
            intervals.append({
                "name": NAME_MAP.get(cur_name, cur_name),
                "start": cur_start,
                "end": cur_end,
            })
            cur_start = d
            cur_end = d
            cur_name = name

    intervals.append({
        "name": NAME_MAP.get(cur_name, cur_name),
        "start": cur_start,
        "end": cur_end,
    })
    return intervals


def _format_key_dates(start, end, total_weeks):
    """根据学期起止生成 key_dates 列表（假期 + 学期结束）"""
    key_dates = []
    holidays = get_holidays_in_range(start, end)
    for h in holidays:
        s_str = h["start"].strftime("%m/%d")
        e_str = h["end"].strftime("%m/%d")
        key_dates.append({
            "date": h["start"].isoformat(),
            "event": f"{h['name']}放假 ({s_str}-{e_str})",
        })
    key_dates.append({"date": end.isoformat(), "event": "学期结束"})
    return key_dates


def get_academic_calendar():
    """获取当前学期校历（学期数据优先来自教务系统）"""
    jxgl = _get_semester_from_jxgl()

    if jxgl:
        start = date.fromisoformat(jxgl["start_date"])
        end = date.fromisoformat(jxgl["end_date"])
        return {
            "semester": jxgl["name"],
            "start_date": jxgl["start_date"],
            "end_date": jxgl["end_date"],
            "total_weeks": jxgl["total_weeks"],
            "key_dates": _format_key_dates(start, end, jxgl["total_weeks"]),
            "source": "学期数据来自教务系统 jxgl.dlut.edu.cn，放假日期来自 chinese-calendar 库",
        }

    # fallback
    fb = FALLBACK_SEMESTER
    start = date.fromisoformat(fb["start_date"])
    end = date.fromisoformat(fb["end_date"])
    total_weeks = (end - start).days // 7 + 1
    return {
        "semester": fb["name"],
        "start_date": fb["start_date"],
        "end_date": fb["end_date"],
        "total_weeks": total_weeks,
        "key_dates": _format_key_dates(start, end, total_weeks),
        "source": "硬编码 fallback 数据 (教务系统不可用)",
    }


def get_current_week():
    """计算当前是第几教学周"""
    jxgl = _get_semester_from_jxgl()

    if jxgl:
        name = jxgl["name"]
        start = date.fromisoformat(jxgl["start_date"])
        end = date.fromisoformat(jxgl["end_date"])
        total_weeks = jxgl["total_weeks"]
    else:
        fb = FALLBACK_SEMESTER
        name = fb["name"]
        start = date.fromisoformat(fb["start_date"])
        end = date.fromisoformat(fb["end_date"])
        total_weeks = (end - start).days // 7 + 1

    today = date.today()

    if today < start:
        delta = (start - today).days
        return {
            "week": 0,
            "day": today.strftime("%Y-%m-%d %A"),
            "semester": name,
            "status": f"尚未开学，距开学还有 {delta} 天",
        }
    elif today > end:
        return {
            "week": total_weeks,
            "day": today.strftime("%Y-%m-%d %A"),
            "semester": name,
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
        holidays = get_holidays_in_range(start, end)
        for h in holidays:
            event_date = h["start"]
            diff = (event_date - today).days
            if -1 <= diff <= 14:
                s_str = h["start"].strftime("%m/%d")
                e_str = h["end"].strftime("%m/%d")
                upcoming.append(f"{h['name']}放假 ({s_str}-{e_str}) ({h['start'].isoformat()})")

        week_type = "考试周" if week == total_weeks else "教学周"
        return {
            "week": week,
            "day": f"{today.strftime('%Y-%m-%d')} {weekday_cn}",
            "semester": name,
            "status": f"第 {week} {week_type} {weekday_cn}",
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
