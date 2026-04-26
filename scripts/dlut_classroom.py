#!/usr/bin/env python3
"""
DUT 教学楼教室查询工具

注意: jxgl.dlut.edu.cn 教务系统需要 CAS 登录，无公开 API。
本脚本提供凌水校区教学楼信息查询及课表辅助功能。
实时空教室查询需登录教务系统。

用法:
    python3 dlut_classroom.py empty [--building 综一]
    python3 dlut_classroom.py info [--building 综一]
"""

import argparse
import sys

import _console  # noqa: F401  forces UTF-8 stdout on Windows
from datetime import datetime
from typing import Optional

# ========== 凌水校区教学楼数据 ==========
# 数据来源: 公开资料整理 + 校园地图，教室容量为估算值

BUILDINGS = {
    "综一": {
        "code": "ZH1",
        "full_name": "综合教学一号楼",
        "location": "凌水校区中心区域",
        "floors": 5,
        "rooms": [
            ("101", 200, "大阶梯教室"),
            ("102", 120, "阶梯教室"),
            ("103", 120, "阶梯教室"),
            ("104", 80, "多媒体教室"),
            ("105", 80, "多媒体教室"),
            ("201", 80, "多媒体教室"),
            ("202", 80, "多媒体教室"),
            ("203", 60, "多媒体教室"),
            ("204", 60, "多媒体教室"),
            ("301", 60, "多媒体教室"),
            ("302", 60, "多媒体教室"),
            ("303", 60, "多媒体教室"),
            ("304", 45, "普通教室"),
            ("401", 45, "普通教室"),
            ("402", 45, "普通教室"),
            ("403", 45, "普通教室"),
        ],
        "description": "凌水校区主要教学楼，承担大量公共基础课",
    },
    "综二": {
        "code": "ZH2",
        "full_name": "综合教学二号楼",
        "location": "凌水校区中心区域",
        "floors": 5,
        "rooms": [
            ("101", 150, "大阶梯教室"),
            ("102", 120, "阶梯教室"),
            ("103", 80, "多媒体教室"),
            ("104", 80, "多媒体教室"),
            ("201", 80, "多媒体教室"),
            ("202", 60, "多媒体教室"),
            ("203", 60, "多媒体教室"),
            ("204", 60, "多媒体教室"),
            ("301", 60, "多媒体教室"),
            ("302", 60, "多媒体教室"),
            ("303", 45, "普通教室"),
            ("304", 45, "普通教室"),
            ("401", 45, "普通教室"),
            ("402", 45, "普通教室"),
        ],
        "description": "紧邻综一，承担公共课和专业课教学",
    },
    "综三": {
        "code": "ZH3",
        "full_name": "综合教学三号楼",
        "location": "凌水校区西部",
        "floors": 4,
        "rooms": [
            ("101", 120, "阶梯教室"),
            ("102", 80, "多媒体教室"),
            ("103", 60, "多媒体教室"),
            ("201", 60, "多媒体教室"),
            ("202", 60, "多媒体教室"),
            ("203", 45, "普通教室"),
            ("301", 45, "普通教室"),
            ("302", 45, "普通教室"),
        ],
        "description": "综合教学楼，用于中小班教学",
    },
    "综四": {
        "code": "ZH4",
        "full_name": "综合教学四号楼",
        "location": "凌水校区西部",
        "floors": 4,
        "rooms": [
            ("101", 120, "阶梯教室"),
            ("102", 80, "多媒体教室"),
            ("201", 60, "多媒体教室"),
            ("202", 60, "多媒体教室"),
            ("203", 45, "普通教室"),
            ("301", 45, "普通教室"),
            ("302", 45, "普通教室"),
        ],
        "description": "综合教学楼",
    },
    "建筑馆": {
        "code": "JZG",
        "full_name": "建筑与艺术学院楼",
        "location": "凌水校区东部",
        "floors": 5,
        "rooms": [
            ("101", 80, "多媒体教室"),
            ("102", 60, "多媒体教室"),
            ("201", 45, "专业教室"),
            ("202", 45, "专业教室"),
            ("203", 30, "设计工作室"),
            ("301", 30, "设计工作室"),
            ("302", 30, "设计工作室"),
            ("401", 30, "模型工坊"),
            ("501", 60, "评图厅"),
        ],
        "description": "建筑与艺术学院专用，含专业教室和工坊",
    },
    "机械馆": {
        "code": "JXG",
        "full_name": "机械工程学院楼",
        "location": "凌水校区北部",
        "floors": 4,
        "rooms": [
            ("101", 120, "阶梯教室"),
            ("102", 80, "多媒体教室"),
            ("201", 60, "多媒体教室"),
            ("202", 45, "普通教室"),
            ("301", 45, "普通教室"),
        ],
        "description": "机械工程学院教学和实验楼",
    },
    "化工馆": {
        "code": "HG",
        "full_name": "化工学院楼",
        "location": "凌水校区北部",
        "floors": 4,
        "rooms": [
            ("101", 120, "阶梯教室"),
            ("102", 80, "多媒体教室"),
            ("201", 60, "多媒体教室"),
            ("202", 45, "普通教室"),
            ("301", 45, "普通教室"),
        ],
        "description": "化工学院教学和实验楼",
    },
    "电信馆": {
        "code": "DXG",
        "full_name": "电信学部楼",
        "location": "凌水校区东部",
        "floors": 5,
        "rooms": [
            ("101", 120, "阶梯教室"),
            ("102", 80, "多媒体教室"),
            ("201", 60, "多媒体教室"),
            ("202", 60, "多媒体教室"),
            ("301", 45, "普通教室"),
            ("302", 45, "普通教室"),
        ],
        "description": "电子信息与电气工程学部教学楼",
    },
    "研教楼": {
        "code": "YJL",
        "full_name": "研究生教育大楼",
        "location": "凌水校区中心区域",
        "floors": 6,
        "rooms": [
            ("101", 80, "多媒体教室"),
            ("102", 60, "多媒体教室"),
            ("201", 45, "研讨室"),
            ("202", 45, "研讨室"),
            ("203", 30, "研讨室"),
            ("301", 45, "研讨室"),
            ("302", 30, "研讨室"),
        ],
        "description": "研究生课程和研讨专用",
    },
    "创新园": {
        "code": "CXY",
        "full_name": "创新园大厦",
        "location": "凌水校区南部",
        "floors": 10,
        "rooms": [
            ("B101", 200, "报告厅"),
            ("101", 80, "多媒体教室"),
            ("102", 60, "多媒体教室"),
            ("201", 45, "研讨室"),
            ("202", 45, "研讨室"),
        ],
        "description": "集教学、科研、办公于一体的综合建筑",
    },
}

# 课程时间段定义（大连理工标准时间表）
TIME_SLOTS = {
    1: ("08:00", "08:45"),
    2: ("08:55", "09:40"),
    3: ("10:00", "10:45"),
    4: ("10:55", "11:40"),
    5: ("13:30", "14:15"),
    6: ("14:25", "15:10"),
    7: ("15:30", "16:15"),
    8: ("16:25", "17:10"),
    9: ("18:00", "18:45"),
    10: ("18:55", "19:40"),
    11: ("19:50", "20:35"),
    12: ("20:45", "21:30"),
}


def get_empty_classrooms(building: Optional[str] = None, date: Optional[str] = None):
    """查询教室列表（基于硬编码数据）。

    真实的空闲教室查询需要登录教务系统:
    https://jxgl.dlut.edu.cn
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    target_buildings = {}
    if building:
        for name, info in BUILDINGS.items():
            if building in name or building in info.get("full_name", ""):
                target_buildings[name] = info
        if not target_buildings:
            print(f"未找到教学楼: {building}")
            print(f"可用的教学楼: {', '.join(BUILDINGS.keys())}")
            return []
    else:
        target_buildings = BUILDINGS

    results = []
    print(f"\n查询日期: {date}")
    print(f"注意: 以下为教学楼教室列表，非实时空闲数据")
    print(f"实时空教室查询请登录: https://jxgl.dlut.edu.cn\n")

    for bname, binfo in target_buildings.items():
        print(f"{binfo['full_name']} ({binfo['location']})")
        print(f"   {binfo['description']}")
        print(f"   共 {binfo['floors']} 层, {len(binfo['rooms'])} 间教室")
        print(f"   {'教室编号':<12} {'容量':>6}  {'类型':<12}")
        print(f"   {'─'*35}")
        for room_id, capacity, room_type in binfo["rooms"]:
            room_str = f"{bname} {room_id}"
            print(f"   {room_str:<12} {capacity:>4}人  {room_type:<12}")
            results.append({
                "building": bname,
                "room": room_id,
                "capacity": capacity,
                "type": room_type,
                "full_name": f"{bname} {room_id}",
            })
        print()

    print(f"共 {len(results)} 间教室")
    return results


def get_classroom_schedule(building: str, room: Optional[str] = None):
    """查询某教学楼/教室的详细信息。"""
    target = None
    for name, info in BUILDINGS.items():
        if building in name or building in info.get("full_name", ""):
            target = (name, info)
            break

    if not target:
        print(f"未找到教学楼: {building}")
        print(f"可用的教学楼: {', '.join(BUILDINGS.keys())}")
        return

    bname, binfo = target
    print(f"\n{binfo['full_name']} 教室信息")
    print(f"位置: {binfo['location']}")
    print(f"描述: {binfo['description']}")

    if room:
        found = False
        for room_id, capacity, room_type in binfo["rooms"]:
            if room == room_id:
                print(f"\n{bname} {room_id}")
                print(f"   容量: {capacity} 人")
                print(f"   类型: {room_type}")
                found = True
                break
        if not found:
            print(f"\n未找到教室: {bname} {room}")
            print(f"该楼可用教室:")
            for r_id, _, _ in binfo["rooms"]:
                print(f"  - {r_id}")
    else:
        print(f"\n所有教室:")
        for room_id, capacity, room_type in binfo["rooms"]:
            print(f"   {bname} {room_id}: {capacity}人, {room_type}")

    print(f"\n大连理工课程时间表:")
    print(f"   {'节次':>4}  {'时间段':<14}")
    print(f"   {'─'*22}")
    for slot, (start, end) in TIME_SLOTS.items():
        label = ""
        if slot == 1:
            label = " <- 上午"
        elif slot == 5:
            label = " <- 下午"
        elif slot == 9:
            label = " <- 晚上"
        print(f"   第{slot:>2}节  {start}-{end}{label}")

    print(f"\n查看实时课表请登录: https://jxgl.dlut.edu.cn")


def main():
    parser = argparse.ArgumentParser(
        description="DUT 教学楼教室查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 dlut_classroom.py empty                    # 查看所有教学楼教室
  python3 dlut_classroom.py empty --building 综一      # 查看综一教室
  python3 dlut_classroom.py info                      # 教学楼概览
  python3 dlut_classroom.py info --building 综一       # 综一详细信息
  python3 dlut_classroom.py info --building 综一 --room 101  # 特定教室
        """
    )
    subparsers = parser.add_subparsers(dest="command", help="操作类型")

    empty_parser = subparsers.add_parser("empty", help="查询教室列表")
    empty_parser.add_argument("--building", "-b", help="教学楼名称")
    empty_parser.add_argument("--date", "-d", help="日期 (YYYY-MM-DD)")

    info_parser = subparsers.add_parser("info", help="查看教学楼/教室信息")
    info_parser.add_argument("--building", "-b", help="教学楼名称")
    info_parser.add_argument("--room", "-r", help="教室编号")

    args = parser.parse_args()

    if args.command == "empty":
        get_empty_classrooms(building=args.building, date=args.date)
    elif args.command == "info":
        if args.building:
            get_classroom_schedule(args.building, room=args.room)
        else:
            print("\n凌水校区教学楼概览")
            print(f"{'─'*50}")
            for name, info in BUILDINGS.items():
                print(f"  {name:<6} | {info['full_name']:<14} | {len(info['rooms']):>2}间教室 | {info['location']}")
            print(f"\n共 {len(BUILDINGS)} 栋教学楼, "
                  f"{sum(len(b['rooms']) for b in BUILDINGS.values())} 间教室")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
