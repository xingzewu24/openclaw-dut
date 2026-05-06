#!/usr/bin/env python3
"""Portal 接口探测工具 v7

深入分析 uamSemsCommon.html 和 header.html 中的业务逻辑。
"""

import os
import sys
import re
import json

import _console  # noqa: F401
import requests

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

from dlut_portal import get_portal_session, PORTAL_BASE


def _fetch(session, url):
    try:
        r = session.get(url, timeout=20, headers={"Connection": "close"})
        return r
    except Exception as e:
        print(f"    获取失败: {e}")
        return None


def parse_constant_js(text):
    vars_dict = {}
    for m in re.finditer(r'var\s+(\w+)\s*=\s*"([^"]*)";', text):
        vars_dict[m.group(1)] = m.group(2)
    for m in re.finditer(r'var\s+(\w+)\s*=\s*([^;]+);', text):
        name, expr = m.groups()
        if name not in vars_dict:
            val = expr.strip()
            m2 = re.match(r'(\w+)\s*\+\s*"([^"]+)"', val)
            if m2 and m2.group(1) in vars_dict:
                vars_dict[name] = vars_dict[m2.group(1)] + m2.group(2)
            else:
                vars_dict[name] = val
    return vars_dict


def extract_context_around_keywords(text, keywords, context_lines=5):
    """提取关键词周围的上下文代码块"""
    lines = text.split('\n')
    results = []
    seen_ranges = set()

    for i, line in enumerate(lines):
        line_lower = line.lower()
        for kw in keywords:
            if kw.lower() in line_lower:
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                range_key = (start, end)
                if range_key not in seen_ranges:
                    seen_ranges.add(range_key)
                    context = '\n'.join(f"{j+1:4d}: {lines[j]}" for j in range(start, end))
                    results.append((kw, i + 1, context))
                break
    return results


def extract_js_from_html(html):
    """从 HTML 中提取所有 script 内容"""
    scripts = []
    for m in re.finditer(r'<script[^>]*>([\s\S]*?)</script>', html, re.I):
        content = m.group(1).strip()
        if content and len(content) > 10:
            scripts.append(content)
    return scripts


def extract_api_from_js(js_text):
    """提取 JS 中的 API 调用"""
    urls = set()
    for m in re.finditer(r'url\s*:\s*["\']([^"\']+)["\']', js_text):
        u = m.group(1)
        if "/" in u and not u.startswith(("http", "./", "../", "#")):
            urls.add(u)
    for m in re.finditer(r'\$\.(?:get|post|ajax)\s*\(\s*["\']([^"\']+)["\']', js_text):
        urls.add(m.group(1))
    return sorted(urls)


def main():
    print("=" * 70)
    print("Portal 业务接口深度分析")
    print("=" * 70)

    session = get_portal_session()
    print("登录成功\n")

    # ── 1. 解析 constant.js ──
    print("[1/5] 解析网关配置")
    print("-" * 50)
    r = _fetch(session, f"{PORTAL_BASE}/tp/defaults/js/constant.js")
    const_vars = parse_constant_js(r.text) if r else {}
    gateway_url = const_vars.get("gateway_url", "")
    contextpath = const_vars.get("contextpath", "")
    print(f"  gateway_url: {gateway_url}")
    print(f"  contextpath: {contextpath}")
    print()

    # ── 2. 下载关键 HTML 片段 ──
    print("[2/5] 下载关键 HTML 片段")
    print("-" * 50)
    fragments = {
        "header": "/tp/resource/defaults/html/include/header.html",
        "uam": "/tp/resource/defaults/html/uam/uamSemsCommon.html",
    }

    contents = {}
    for name, path in fragments.items():
        r = _fetch(session, f"{PORTAL_BASE}{path}")
        if r and r.status_code == 200:
            contents[name] = r.text
            print(f"  ✓ {name}: {len(r.text)} 字符")
        else:
            print(f"  ✗ {name}: 获取失败")
    print()

    # ── 3. 关键词上下文搜索 ──
    print("[3/5] 关键词上下文搜索")
    print("-" * 50)
    keywords = ["余额", "balance", "卡", "card", "ykt", "ecard", "一卡通",
                "网费", "network", "internet", "netfee",
                "电费", "用电", "electric", "elec", "power", "dorm",
                "用户信息", "userInfo", "个人信息"]

    for frag_name, text in contents.items():
        print(f"\n  === {frag_name}.html ===")
        contexts = extract_context_around_keywords(text, keywords, context_lines=3)
        if contexts:
            for kw, line_num, context in contexts[:20]:  # 最多显示20个匹配
                print(f"\n  匹配 '{kw}' (行 {line_num}):")
                print(context)
                print("  " + "-" * 40)
        else:
            print("  未匹配到关键词")
    print()

    # ── 4. 提取并分析内联 JS ──
    print("[4/5] 提取内联 JS 中的接口")
    print("-" * 50)
    all_js = ""
    for frag_name, text in contents.items():
        scripts = extract_js_from_html(text)
        print(f"\n  {frag_name}: {len(scripts)} 段脚本")
        for i, script in enumerate(scripts):
            all_js += "\n" + script
            urls = extract_api_from_js(script)
            if urls:
                print(f"    脚本[{i}] 发现 {len(urls)} 个 URL:")
                for u in urls[:10]:
                    print(f"      - {u}")
    print()

    # ── 5. 探测接口 ──
    print("[5/5] 探测接口")
    print("-" * 50)
    all_urls = extract_api_from_js(all_js)
    print(f"  共 {len(all_urls)} 个唯一 URL")

    # 解析完整 URL
    test_urls = []
    for u in all_urls:
        if u.startswith("http"):
            test_urls.append(u)
        elif u.startswith("/"):
            test_urls.append(contextpath + u)
        else:
            test_urls.append(contextpath + "/" + u)

    # 加上一些猜测的路径
    test_urls += [
        f"{contextpath}/home/pingcurrent",
        f"{contextpath}/home/getSubsiteInfo",
        f"{contextpath}/api/user/info",
        f"{contextpath}/user/info",
        f"{contextpath}/card/balance",
        f"{contextpath}/ykt/balance",
        f"{contextpath}/network/balance",
        f"{contextpath}/electric/balance",
        f"{contextpath}/api/me",
        f"{contextpath}/service/list",
        f"{contextpath}/comm/ub",
        f"{contextpath}/ping",
    ]

    test_urls = sorted(set(test_urls))
    found = []
    for url in test_urls[:40]:
        try:
            r = session.get(url, timeout=10, headers={"Connection": "close"})
            if r.status_code == 200:
                ct = r.headers.get("Content-Type", "")
                is_json = "json" in ct or r.text.strip().startswith(("{", "["))
                preview = r.text[:200].replace("\n", " ")
                found.append({"url": url, "type": "json" if is_json else "text", "preview": preview})
                print(f"\n  ✓ {url}")
                print(f"    [{'json' if is_json else 'text'}] {preview[:120]}")
            elif r.status_code in (401, 403):
                print(f"  ⊘ {url} -> {r.status_code}")
        except Exception as e:
            pass

    if not found:
        print("  未发现可用接口")
    print()

    # 保存 HTML 供后续分析
    os.makedirs("portal_html", exist_ok=True)
    for name, text in contents.items():
        with open(f"portal_html/{name}.html", "w", encoding="utf-8") as f:
            f.write(text)
    print("HTML 片段已保存到: portal_html/")
    print()

    # 保存结果
    result = {
        "contextpath": contextpath,
        "found_apis": found,
        "tested_urls": test_urls[:40],
    }
    with open("portal_probe_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print("结果已保存到: portal_probe_result.json")
    print()

    print("=" * 70)
    print("请把上面的完整输出复制发给我。")
    print("=" * 70)


if __name__ == "__main__":
    main()
