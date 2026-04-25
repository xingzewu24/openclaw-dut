#!/usr/bin/env python3
"""
大工在线工具集合
整合多个在线服务的入口和使用指引
"""

import sys

# ============================================================
# 工具信息
# ============================================================

def get_all_tools() -> list[dict]:
    """列出所有可用工具"""
    tools = [
        {"name": "统一身份认证 (CAS)", "url": "https://portal.dlut.edu.cn",
         "cmd": "", "desc": "DUT 统一身份认证登录门户"},
        {"name": "超星学习通", "url": "https://dut.fanya.chaoxing.com",
         "cmd": "", "desc": "课程管理、作业、课件、成绩"},
        {"name": "大工邮箱", "url": "https://mail.dlut.edu.cn",
         "cmd": "", "desc": "Coremail 邮箱系统"},
        {"name": "大工云盘", "url": "https://pan.dlut.edu.cn",
         "cmd": "", "desc": "Seafile 云存储服务"},
        {"name": "教务系统", "url": "https://jxgl.dlut.edu.cn",
         "cmd": "", "desc": "选课、成绩、课表查询 (需校园网)"},
        {"name": "教学信息", "url": "https://teach.dlut.edu.cn",
         "cmd": "", "desc": "校历、选课入口、通知公告"},
        {"name": "图书馆", "url": "https://lib.dlut.edu.cn",
         "cmd": "", "desc": "馆藏查询、座位预约、数据库"},
        {"name": "碧海青天 BBS", "url": "https://bbs.dlut.edu.cn",
         "cmd": "", "desc": "校内论坛，课程讨论、二手交易"},
        {"name": "大工新闻网", "url": "https://news.dlut.edu.cn",
         "cmd": "", "desc": "学校新闻动态"},
        {"name": "信息公开网", "url": "https://info.dlut.edu.cn",
         "cmd": "", "desc": "学校信息公开"},
        {"name": "TUNA 镜像站", "url": "https://mirrors.tuna.tsinghua.edu.cn",
         "cmd": "", "desc": "开源软件镜像 (pip/conda/brew 等)"},
        {"name": "npmmirror", "url": "https://registry.npmmirror.com",
         "cmd": "", "desc": "npm 软件包镜像"},
        {"name": "Overleaf (公共)", "url": "https://www.overleaf.com",
         "cmd": "latex", "desc": "LaTeX 在线编辑器 (公共版)"},
        {"name": "DLUTThesis", "url": "https://github.com/DLUTcraft/DLUTThesis",
         "cmd": "thesis", "desc": "大连理工大学学位论文 LaTeX 模板"},
    ]
    return tools


def get_latex_info() -> str:
    """LaTeX 使用指引"""
    return """
LaTeX 论文写作指南

  推荐: 使用 Overleaf 在线编辑 + DLUTThesis 模板

  在线编辑:
    https://www.overleaf.com (公共版，免费)
    编译器选择 XeLaTeX（中文支持更好）

  学位论文模板:
    https://github.com/DLUTcraft/DLUTThesis
    大连理工大学学位论文 LaTeX 模板，支持本科/硕士/博士

  Beamer 演示模板:
    可在 Overleaf 搜索 "DLUT" 或 "大连理工" 获取

  快速开始:
    1. 在 Overleaf 创建新项目
    2. 上传 DLUTThesis 模板文件
    3. 选择 XeLaTeX 编译器
    4. 开始写作
""".strip()


def get_thesis_info() -> str:
    """学位论文模板使用指引"""
    return """
DLUTThesis 学位论文模板

  仓库: https://github.com/DLUTcraft/DLUTThesis

  支持类型:
    - 本科毕业设计论文
    - 硕士学位论文
    - 博士学位论文

  使用方法:
    1. git clone https://github.com/DLUTcraft/DLUTThesis.git
    2. 用 Overleaf 或本地 TeX 发行版打开
    3. 编辑 main.tex 中的个人信息
    4. 按章节编写论文内容

  注意事项:
    - 推荐使用 XeLaTeX 或 LuaLaTeX 编译
    - 字体需安装 Windows 或 Fandol 字体包
    - 详细文档见仓库 README
""".strip()


# ============================================================
# CLI
# ============================================================

def print_all_tools():
    """打印所有工具列表"""
    tools = get_all_tools()
    print("\n大工在线工具集合")
    print("-" * 60)
    for i, tool in enumerate(tools, 1):
        cmd_hint = f" (命令: {tool['cmd']})" if tool.get("cmd") else ""
        print(f"  {i:>2}. {tool['name']}{cmd_hint}")
        print(f"      {tool['desc']}")
        print(f"      {tool['url']}")
    print(f"\n使用 python3 dlut_tools.py <命令> 查看详细信息")
    print()


def main():
    tool_map = {
        "latex": get_latex_info,
        "thesis": get_thesis_info,
    }

    if len(sys.argv) < 2:
        print("用法: python3 dlut_tools.py <命令>")
        print()
        print("命令:")
        print("  list    列出所有可用工具")
        print("  latex   LaTeX 编辑器指引")
        print("  thesis  学位论文模板指引")
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "list":
        print_all_tools()
    elif cmd in tool_map:
        print(tool_map[cmd]())
    else:
        print(f"未知命令: {cmd}")
        print("运行 python3 dlut_tools.py 查看帮助")
        sys.exit(1)


if __name__ == "__main__":
    main()
