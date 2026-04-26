#!/usr/bin/env python3
"""
DUT 校园照片浏览工具
提供大连理工大学校园风光相册入口
"""

import sys

import _console  # noqa: F401  forces UTF-8 stdout on Windows

# ============================================================
# 校园相册数据
# ============================================================

ALBUMS = [
    {
        "name": "凌水校区全景",
        "desc": "主校区鸟瞰、标志性建筑群",
        "tags": ["航拍", "全景", "校园"],
        "url": "https://www.dlut.edu.cn/dlfw/xxgk/xxyz.htm",
    },
    {
        "name": "四季大工",
        "desc": "春夏秋冬凌水校区风光",
        "tags": ["四季", "风光", "季节"],
        "url": "https://www.dlut.edu.cn/dlfw/xxgk/xxyz.htm",
    },
    {
        "name": "图书馆",
        "desc": "伯川图书馆、令希图书馆内外景",
        "tags": ["图书馆", "阅读", "学习"],
        "url": "https://lib.dlut.edu.cn",
    },
    {
        "name": "实验室与科研",
        "desc": "国家重点实验室、科研平台",
        "tags": ["实验室", "科研", "科技"],
        "url": "https://www.dlut.edu.cn/dlfw/xxgk/xxyz.htm",
    },
    {
        "name": "校园活动",
        "desc": "运动会、文化节、毕业典礼",
        "tags": ["活动", "体育", "毕业"],
        "url": "https://news.dlut.edu.cn",
    },
    {
        "name": "盘锦校区",
        "desc": "盘锦校区校园风光",
        "tags": ["盘锦", "校区"],
        "url": "https://pj.dlut.edu.cn",
    },
    {
        "name": "开发区校区",
        "desc": "软件学院校区风光",
        "tags": ["开发区", "软件"],
        "url": "https://ssdut.dlut.edu.cn",
    },
]


def list_albums() -> list[dict]:
    """列出所有相册"""
    return ALBUMS


def search_photos(keyword: str) -> list[dict]:
    """搜索照片（基于标签匹配）"""
    results = []
    keyword_lower = keyword.lower()
    for album in ALBUMS:
        name_match = keyword_lower in album["name"].lower()
        desc_match = keyword_lower in album.get("desc", "").lower()
        tag_match = any(keyword_lower in tag for tag in album.get("tags", []))
        if name_match or desc_match or tag_match:
            results.append({
                "album": album["name"],
                "desc": album.get("desc", ""),
                "url": album["url"],
                "match": "标签" if tag_match else ("名称" if name_match else "描述"),
            })
    if not results:
        results.append({
            "album": f"搜索 \"{keyword}\"",
            "desc": "未匹配到结果，建议访问大工官网查看更多照片",
            "url": "https://www.dlut.edu.cn/dlfw/xxgk/xxyz.htm",
            "match": "建议",
        })
    return results


def print_albums():
    """打印相册列表"""
    albums = list_albums()
    print(f"\nDUT 校园照片")
    print(f"   共 {len(albums)} 个主题")
    print("-" * 60)
    for i, album in enumerate(albums, 1):
        tags = " ".join(f"#{t}" for t in album.get("tags", []))
        print(f"  {i:>2}. {album['name']}")
        if album.get("desc"):
            print(f"      {album['desc']}")
        if tags:
            print(f"      {tags}")
        print(f"      {album['url']}")
    print(f"\n更多校园照片: https://www.dlut.edu.cn/dlfw/xxgk/xxyz.htm")
    print()


def print_search(keyword: str):
    """打印搜索结果"""
    results = search_photos(keyword)
    print(f"\n搜索: \"{keyword}\"")
    print("-" * 60)
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r['album']} ({r['match']})")
        if r.get("desc"):
            print(f"     {r['desc']}")
        print(f"     {r['url']}")
    print()


def main():
    if len(sys.argv) < 2:
        print("用法: python3 dlut_visual.py <命令> [参数]")
        print()
        print("命令:")
        print("  albums           列出所有相册")
        print("  search <关键词>  搜索照片")
        print()
        print("示例:")
        print('  python3 dlut_visual.py search "图书馆"')
        sys.exit(0)

    cmd = sys.argv[1].lower()
    if cmd == "albums":
        print_albums()
    elif cmd == "search":
        if len(sys.argv) < 3:
            print("请提供搜索关键词")
            sys.exit(1)
        print_search(sys.argv[2])
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
