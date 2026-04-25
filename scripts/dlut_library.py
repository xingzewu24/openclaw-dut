#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大连理工大学图书馆信息与座位查询工具

功能：
  - 查询各图书馆基本信息（位置、开放时间、楼层功能）
  - 查询座位预约状态（需 CAS SSO 认证，当前为信息指引）

座位预约系统：
  - 预约系统地址: https://smart.lib.dlut.edu.cn
  - 认证方式: CAS SSO (https://sso.dlut.edu.cn)
  - 移动端入口: i大工 App → 图书馆 → 座位预约

数据来源：
  - 图书馆官网: https://lib.dlut.edu.cn
  - 开放时间: https://lib.dlut.edu.cn/gqgk/kfsj.htm
"""

import sys

# Windows stdout 默认 gbk，subprocess 捕获时 emoji 会 UnicodeEncodeError
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure") and (_s.encoding or "").lower() != "utf-8":
        _s.reconfigure(encoding="utf-8", errors="replace")
from datetime import date, datetime

# ============================================================
# 图书馆数据
# 数据来源: lib.dlut.edu.cn 官网
# ============================================================

LIBRARIES = [
    {
        "name": "伯川图书馆",
        "short_name": "伯川",
        "campus": "凌水主校区",
        "location": "大连市甘井子区凌工路2号，主校区中心位置",
        "floors": {
            "1F": "总服务台、借还书、新书展示、电子阅览区",
            "2F": "社科图书阅览区、凌水书屋、研讨间",
            "3F": "自科图书阅览区、期刊阅览室",
            "4F": "特藏文献、自习空间、研修间",
        },
        "hours": {
            "normal": "周一至周日 08:00-22:00",
            "vacation": "寒暑假另行通知",
        },
        "seats": "约 2500 个",
        "features": ["自助借还机", "研讨间预约", "研修间预约", "凌水书屋", "无线网络"],
    },
    {
        "name": "令希图书馆",
        "short_name": "令希",
        "campus": "凌水主校区",
        "location": "大连市甘井子区凌工路2号，主校区西部",
        "floors": {
            "1F": "总服务台、自助借还、密集书库",
            "2F": "图书阅览区、研讨间",
            "3F": "图书阅览区、期刊报纸阅览",
            "4F": "自习空间、展览区、研修间",
        },
        "hours": {
            "normal": "周一至周日 08:00-22:00",
            "vacation": "寒暑假另行通知",
        },
        "seats": "约 2500 个",
        "features": ["自助借还机", "研讨间预约", "研修间预约", "展览空间", "无线网络"],
    },
    {
        "name": "开发区校区图书馆",
        "short_name": "开发区馆",
        "campus": "开发区校区",
        "location": "大连经济技术开发区校区内",
        "hours": {
            "normal": "周一至周日 08:00-22:00",
        },
        "seats": "约 800 个",
        "features": ["自助借还", "阅览空间"],
    },
    {
        "name": "盘锦校区图书馆",
        "short_name": "盘锦馆",
        "campus": "盘锦校区",
        "location": "盘锦校区内",
        "hours": {
            "normal": "周一至周日 08:00-22:00",
        },
        "seats": "约 600 个",
        "features": ["阅览空间", "研讨间"],
    },
    {
        "name": "马克思主义图书馆",
        "short_name": "马院馆",
        "campus": "凌水主校区",
        "location": "主校区马克思主义学院内",
        "hours": {
            "normal": "周一至周五 08:00-11:40, 13:30-17:10",
            "weekend": "周六、周日闭馆",
        },
        "features": ["马列文献专藏"],
    },
]

SEAT_RESERVATION_INFO = {
    "system_url": "https://smart.lib.dlut.edu.cn",
    "auth_method": "DUT 统一身份认证 (CAS SSO: sso.dlut.edu.cn)",
    "mobile_access": [
        "i大工 App → 图书馆 → 座位预约",
        "微信搜索「大连理工大学图书馆」公众号 → 座位预约",
    ],
    "rules": [
        "需通过 DUT 统一身份认证登录",
        "预约生效后须按时到馆签到",
        "超时未签到自动取消并计违约",
        "离馆需在系统中释放座位",
    ],
    "tips": [
        "考试季座位紧张，建议提前预约",
        "伯川和令希均有大量座位，可根据课程就近选择",
        "年度预约量超 20000 人次",
        "临时离开可使用「暂离」功能",
    ],
    "api_status": "座位预约系统需 CAS SSO 认证，暂无公开 API",
}


def get_library_info(campus=None):
    """
    获取图书馆基本信息

    Args:
        campus: 校区过滤 ('凌水主校区', '开发区校区', '盘锦校区')，None 则返回全部

    Returns:
        list[dict]: 图书馆信息列表
    """
    libs = LIBRARIES
    if campus:
        libs = [lib for lib in libs if lib.get("campus", "") == campus]
    return libs


def get_seat_status():
    """
    获取座位预约状态

    当前实现: 返回预约系统信息和使用指引

    Returns:
        dict: 座位预约系统信息
    """
    today = date.today()
    is_weekend = today.weekday() >= 5

    return {
        "date": today.strftime("%Y-%m-%d"),
        "day_type": "周末" if is_weekend else "工作日",
        "realtime_available": False,
        "message": "座位预约系统需通过 CAS SSO 认证登录，暂无法提供实时数据",
        "reservation_info": SEAT_RESERVATION_INFO,
        "recommendation": _get_seat_recommendation(is_weekend),
    }


def _get_seat_recommendation(is_weekend=False):
    """根据时间给出座位选择建议"""
    now = datetime.now()
    hour = now.hour

    suggestions = []

    if hour < 8:
        suggestions.append("各馆尚未开放（8:00 开门）")
    elif hour < 10:
        suggestions.append("早间时段，各馆座位相对充裕")
        suggestions.append("建议: 伯川2F/令希2F 阅览区座位充足")
    elif hour < 14:
        suggestions.append("上午/午间时段，座位开始紧张")
        suggestions.append("建议: 伯川3F/令希3F 高楼层通常人少一些")
    elif hour < 18:
        suggestions.append("下午时段，热门区域座位可能紧张")
        suggestions.append("建议: 尝试高楼层或研修间")
    elif hour < 22:
        suggestions.append("晚间时段，考试季各馆较满")
        suggestions.append("建议: 通过 smart.lib.dlut.edu.cn 查看实时余位")
    else:
        suggestions.append("已过 22:00，各馆已闭馆")

    if is_weekend:
        suggestions.append("周末人流相对工作日少，可直接前往")

    return suggestions


def _print_library_info():
    """终端输出图书馆信息"""
    libs = get_library_info()
    print(f"\n📚 大连理工大学图书馆信息")
    print("=" * 60)
    for lib in libs:
        print(f"\n🏛️  {lib['name']}")
        print(f"   📍 校区: {lib['campus']}")
        if lib.get("location"):
            print(f"   📍 位置: {lib['location']}")
        if isinstance(lib.get("hours"), dict):
            for label, time in lib["hours"].items():
                print(f"   🕐 {label}: {time}")
        if lib.get("seats"):
            print(f"   💺 座位: {lib['seats']}")
        if lib.get("features"):
            print(f"   ✨ 特色: {', '.join(lib['features'])}")
        if lib.get("floors"):
            print(f"   🏢 楼层:")
            for floor, desc in lib["floors"].items():
                print(f"      {floor}: {desc}")
    print()


def _print_seat_status():
    """终端输出座位信息"""
    info = get_seat_status()
    print(f"\n💺 座位预约信息 ({info['date']} {info['day_type']})")
    print("=" * 60)

    if not info["realtime_available"]:
        print(f"\n⚠️  {info['message']}")

    res = info["reservation_info"]
    print(f"\n🔗 预约系统: {res['system_url']}")
    print(f"🔐 认证方式: {res['auth_method']}")
    print(f"\n📱 移动端入口:")
    for entry in res["mobile_access"]:
        print(f"   • {entry}")
    print(f"\n📋 预约规则:")
    for rule in res["rules"]:
        print(f"   • {rule}")
    print(f"\n💡 小贴士:")
    for tip in res["tips"]:
        print(f"   • {tip}")

    print(f"\n🎯 当前建议:")
    for sug in info["recommendation"]:
        print(f"   {sug}")
    print()


def main():
    if len(sys.argv) < 2:
        print("用法: python3 dlut_library.py <命令>")
        print()
        print("命令:")
        print("  info    - 查看各图书馆基本信息")
        print("  seats   - 查看座位预约信息")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    try:
        if cmd == "info":
            _print_library_info()
        elif cmd == "seats":
            _print_seat_status()
        else:
            print(f"❌ 未知命令: {cmd}")
            print("可用命令: info / seats")
            sys.exit(1)
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
