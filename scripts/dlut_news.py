#!/usr/bin/env python3
"""
DUT 新闻 + 教务通知爬虫
目标:
  - https://news.dlut.edu.cn （大工新闻网）
  - https://teach.dlut.edu.cn （教务处通知 + 教研教改）
"""

import sys
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# ============================================================
# 常量
# ============================================================

TIMEOUT = 10
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

NEWS_URL = "https://news.dlut.edu.cn"
TEACH_URL = "https://teach.dlut.edu.cn"


# ============================================================
# 大工新闻网 (news.dlut.edu.cn)
# ============================================================

def get_news(limit: int = 10) -> list[dict]:
    """爬取大工新闻网最新新闻"""
    results = []

    try:
        # 主页新闻列表页
        resp = requests.get(f"{NEWS_URL}/zyxw.htm", headers=HEADERS, timeout=TIMEOUT)
        resp.encoding = resp.apparent_encoding or "utf-8"
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # news.dlut.edu.cn 列表结构: ul.nylistn > li.bg-mask
        # 每项: div.pic > time(日期) + div.txt > h4 > a(标题) + p(摘要)
        items = soup.select("ul.nylistn li.bg-mask")

        for item in items:
            if len(results) >= limit:
                break

            # 标题链接
            a = item.select_one("div.txt h4 a")
            if not a:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 4:
                continue

            href = a["href"]
            if not href.startswith("http"):
                href = f"{NEWS_URL}/{href}"

            # 日期: time > span(日) + time文本(年月)
            date_str = ""
            time_el = item.select_one("div.pic time")
            if time_el:
                span_el = time_el.find("span")
                if span_el:
                    day = span_el.get_text(strip=True)
                    # time 文本 = "YYYY-MM"（span 之后）
                    time_text = time_el.get_text(strip=True)
                    ym = re.search(r'(\d{4}-\d{1,2})', time_text)
                    if ym:
                        date_str = f"{ym.group(1)}-{int(day):02d}"

            # 摘要
            summary = ""
            p = item.select_one("div.txt p.l3")
            if p:
                summary = p.get_text(strip=True)[:120]

            results.append({"title": title, "url": href, "date": date_str, "summary": summary})

        if not results:
            results = _news_from_homepage(limit)

    except Exception as e:
        print(f"⚠️ 爬取新闻网失败: {e}", file=sys.stderr)
        results = _news_from_homepage(limit)

    return results[:limit]


def _news_from_homepage(limit: int = 10) -> list[dict]:
    """从 news.dlut.edu.cn 首页提取新闻（轮播图 + 列表）"""
    results = []
    try:
        resp = requests.get(NEWS_URL, headers=HEADERS, timeout=TIMEOUT)
        resp.encoding = resp.apparent_encoding or "utf-8"
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        seen = set()
        # 轮播图: div.swiper-slide > a.ablink + h4 标题
        for slide in soup.select("div.swiper-slide"):
            if len(results) >= limit:
                break
            link = slide.find("a", href=True)
            h4 = slide.find("h4")
            if not link or not h4:
                continue
            title = h4.get_text(strip=True)
            if title in seen:
                continue
            seen.add(title)
            href = link["href"]
            if not href.startswith("http"):
                href = f"{NEWS_URL}/{href}"
            results.append({"title": title, "url": href, "date": ""})

        # 侧边列表
        for a in soup.select("a.l3"):
            if len(results) >= limit:
                break
            title = a.get_text(strip=True)
            if not title or len(title) < 4 or title in seen:
                continue
            seen.add(title)
            href = a.get("href", "")
            if not href.startswith("http"):
                href = f"{NEWS_URL}/{href}"
            results.append({"title": title, "url": href, "date": ""})

    except Exception as e:
        print(f"⚠️ 爬取新闻网首页失败: {e}", file=sys.stderr)

    if not results:
        results = [{"title": "（无法获取最新新闻，请直接访问网站）", "url": NEWS_URL, "date": ""}]

    return results[:limit]


# ============================================================
# 教务处通知 (teach.dlut.edu.cn 通知公告)
# ============================================================

def get_jwc_notices(limit: int = 10) -> list[dict]:
    """爬取教务处通知公告"""
    results = []
    current_year = datetime.now().year

    try:
        resp = requests.get(TEACH_URL, headers=HEADERS, timeout=TIMEOUT)
        resp.encoding = resp.apparent_encoding or "utf-8"
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 找到通知公告区域 (index05.png 和 index08.png 之间)
        # 结构: div.list.fl > div.date.fl + div.txt.fr > a
        items = soup.select("div.list.fl")

        for item in items:
            if len(results) >= limit:
                break

            # 日期块: div.date.fl → "X月<SPAN>DD</SPAN>"
            date_div = item.select_one("div.date.fl")
            # 文本块: div.txt.fr > a
            txt_div = item.select_one("div.txt.fr")
            if not txt_div:
                continue

            a = txt_div.find("a", href=True)
            if not a:
                continue

            # 标题: <H2> 或 <a> title 属性
            h2 = a.find("h2")
            title = h2.get_text(strip=True) if h2 else a.get("title", "")
            if not title:
                title = a.get_text(strip=True)
            if not title or len(title) < 4:
                continue

            # 链接
            href = a["href"]
            if not href.startswith("http"):
                href = f"{TEACH_URL}/{href}"

            # 日期解析
            date_str = ""
            if date_div:
                date_text = date_div.get_text(strip=True)
                # 格式: "4月21" 或 "11月05"
                dm = re.search(r'(\d{1,2})月(\d{1,2})', date_text)
                if dm:
                    month = int(dm.group(1))
                    day = int(dm.group(2))
                    # 推断年份: 如果月份 > 当前月份，可能是去年
                    year = current_year
                    if month > datetime.now().month:
                        year = current_year - 1
                    date_str = f"{year}-{month:02d}-{day:02d}"

            # 摘要: <a> 内 H2 之后的文本
            summary = ""
            if h2:
                full_text = a.get_text(strip=True)
                title_text = h2.get_text(strip=True)
                summary = full_text.replace(title_text, "").strip()[:120]

            results.append({
                "title": title,
                "url": href,
                "date": date_str,
                "summary": summary,
            })

    except Exception as e:
        print(f"⚠️ 爬取教务处失败: {e}", file=sys.stderr)
        results = [{"title": "（无法获取，请直接访问）", "url": TEACH_URL, "date": ""}]

    return results[:limit]


# ============================================================
# 教研教改 (teach.dlut.edu.cn 教学文件)
# ============================================================

def get_gk_notices(limit: int = 10) -> list[dict]:
    """爬取教务处教研教改/教学文件通知"""
    results = []

    try:
        resp = requests.get(TEACH_URL, headers=HEADERS, timeout=TIMEOUT)
        resp.encoding = resp.apparent_encoding or "utf-8"
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 教研教改区域使用 table 结构
        # div.list > table > tr > td > a + td(日期)
        for div in soup.select("div.list"):
            if len(results) >= limit:
                break

            table = div.find("table")
            if not table:
                continue

            td = table.find("td")
            if not td:
                continue

            a = td.find("a", href=True)
            if not a:
                continue

            title = a.get("title", "") or a.get_text(strip=True)
            if not title or len(title) < 4:
                continue

            href = a["href"]
            if not href.startswith("http"):
                href = f"{TEACH_URL}/{href}"

            # 日期: 第二个 td
            date_str = ""
            tds = table.find_all("td")
            for td_item in tds:
                dm = re.search(r'(\d{4}-\d{1,2}-\d{1,2})', td_item.get_text())
                if dm:
                    date_str = dm.group(1)
                    break

            results.append({
                "title": title,
                "url": href,
                "date": date_str,
            })

    except Exception as e:
        print(f"⚠️ 爬取教研教改失败: {e}", file=sys.stderr)
        results = [{"title": "（无法获取，请直接访问）", "url": TEACH_URL, "date": ""}]

    return results[:limit]


# ============================================================
# 输出格式化
# ============================================================

def print_items(title: str, items: list[dict]):
    """格式化输出列表"""
    print(f"\n📰 {title}")
    print("─" * 60)
    if not items:
        print("  （暂无数据）")
        return
    for i, item in enumerate(items, 1):
        date_part = f" [{item['date']}]" if item.get("date") else ""
        print(f"  {i:>2}. {item['title']}{date_part}")
        if item.get("summary"):
            print(f"      📝 {item['summary'][:100]}")
        if item.get("url"):
            print(f"      🔗 {item['url']}")
    print()


# ============================================================
# CLI
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("用法: python3 dlut_news.py <命令> [数量]")
        print()
        print("命令:")
        print("  news [n]  大工新闻网最新新闻 (默认10条)")
        print("  jwc  [n]  教务处通知公告 (默认10条)")
        print("  gk   [n]  教务处教研教改通知 (默认10条)")
        print("  all  [n]  全部获取")
        sys.exit(0)

    cmd = sys.argv[1].lower()
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    if cmd == "news":
        items = get_news(limit)
        print_items("大工新闻网", items)
    elif cmd == "jwc":
        items = get_jwc_notices(limit)
        print_items("教务处通知公告", items)
    elif cmd == "gk":
        items = get_gk_notices(limit)
        print_items("教务处教研教改", items)
    elif cmd == "all":
        print_items("大工新闻网", get_news(limit))
        print_items("教务处通知公告", get_jwc_notices(limit))
        print_items("教务处教研教改", get_gk_notices(limit))
    else:
        print(f"❌ 未知命令: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
