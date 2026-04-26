#!/usr/bin/env python3
"""
镜像源换源工具
主镜像: https://mirrors.tuna.tsinghua.edu.cn (清华大学 TUNA)
备用:   https://mirrors.hit.edu.cn (哈尔滨工业大学)
功能: 列出可用镜像、生成换源配置、自动换源
"""

import sys

import _console  # noqa: F401  forces UTF-8 stdout on Windows
import platform
import json
import requests

# ============================================================
# 常量
# ============================================================

MIRROR_BASE = "https://mirrors.tuna.tsinghua.edu.cn"
TUNA_STATUS_API = f"{MIRROR_BASE}/static/tunasync.json"
TIMEOUT = 10
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        if platform.system() == "Windows"
        else "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# 常用镜像（降级用）
FALLBACK_MIRRORS = [
    {"name": "pypi", "desc": "PyPI 软件包"},
    {"name": "anaconda", "desc": "Anaconda 仓库"},
    {"name": "homebrew-bottles", "desc": "Homebrew Bottles"},
    {"name": "docker-ce", "desc": "Docker CE 软件源"},
    {"name": "ubuntu", "desc": "Ubuntu 软件源"},
    {"name": "debian", "desc": "Debian 软件源"},
    {"name": "archlinux", "desc": "Arch Linux"},
    {"name": "archlinuxcn", "desc": "Arch Linux CN"},
    {"name": "crates.io-index.git", "desc": "Rust crates"},
    {"name": "CTAN", "desc": "CTAN (TeX)"},
    {"name": "CPAN", "desc": "CPAN (Perl)"},
    {"name": "CRAN", "desc": "CRAN (R)"},
    {"name": "manjaro", "desc": "Manjaro Linux"},
    {"name": "fedora", "desc": "Fedora"},
    {"name": "centos-stream", "desc": "CentOS Stream"},
    {"name": "deepin", "desc": "Deepin"},
]


# ============================================================
# 镜像列表
# ============================================================

def list_mirrors() -> list[dict]:
    """从 TUNA 获取镜像列表"""
    try:
        resp = requests.get(TUNA_STATUS_API, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            mirrors = []
            for item in data:
                status = item.get("status", "unknown")
                mirrors.append({
                    "name": item.get("name", ""),
                    "url": f"{MIRROR_BASE}/{item.get('name', '')}",
                    "desc": item.get("name", ""),
                    "status": status,
                })
            return mirrors
    except Exception:
        pass

    # 降级：硬编码
    return [
        {**m, "url": f"{MIRROR_BASE}/{m['name']}", "status": "unknown"}
        for m in FALLBACK_MIRRORS
    ]


# ============================================================
# 各工具换源配置
# ============================================================

def get_pip_config() -> str:
    """返回 pip 换源命令和配置"""
    is_windows = platform.system() == "Windows"
    config_file = "~/pip/pip.ini" if is_windows else "~/.pip/pip.conf"
    return f"""
╔══════════════════════════════════════════════════════════╗
║  pip 换源到清华 TUNA 镜像                                  ║
╚══════════════════════════════════════════════════════════╝

▶ 临时使用:
  pip install <包名> -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple

▶ 永久配置 (推荐):
  pip config set global.index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple

▶ 或手动编辑 {config_file}:
  [global]
  index-url = https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
""".strip()


def get_conda_config() -> str:
    """返回 conda 换源命令和配置"""
    return """
╔══════════════════════════════════════════════════════════╗
║  conda 换源到清华 TUNA 镜像                                ║
╚══════════════════════════════════════════════════════════╝

▶ 编辑 ~/.condarc，写入以下内容:

channels:
  - defaults
show_channel_urls: true
default_channels:
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/r
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/msys2
custom_channels:
  conda-forge: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud
  pytorch: https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud

▶ 清除缓存:
  conda clean -i
""".strip()


def get_brew_config() -> str:
    """返回 brew 换源命令和配置（仅 macOS/Linux）"""
    if platform.system() == "Windows":
        return """
╔══════════════════════════════════════════════════════════╗
║  Homebrew 换源                                            ║
╚══════════════════════════════════════════════════════════╝

⚠️ Homebrew 仅支持 macOS / Linux，Windows 不可用。
   Windows 用户可使用 scoop 或 winget 作为替代包管理器。
""".strip()
    return """
╔══════════════════════════════════════════════════════════╗
║  Homebrew 换源到清华 TUNA 镜像                              ║
╚══════════════════════════════════════════════════════════╝

▶ 设置环境变量 (添加到 ~/.zshrc 或 ~/.bashrc):

  export HOMEBREW_API_DOMAIN="https://mirrors.tuna.tsinghua.edu.cn/homebrew-bottles/api"
  export HOMEBREW_BOTTLE_DOMAIN="https://mirrors.tuna.tsinghua.edu.cn/homebrew-bottles/bottles"
  export HOMEBREW_BREW_GIT_REMOTE="https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/brew.git"
  export HOMEBREW_CORE_GIT_REMOTE="https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/homebrew-core.git"
  export HOMEBREW_PIP_INDEX_URL="https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple"

▶ 生效:
  source ~/.zshrc
""".strip()


def get_docker_config() -> str:
    """返回 Docker 换源命令和配置"""
    is_windows = platform.system() == "Windows"
    if is_windows:
        return """
╔══════════════════════════════════════════════════════════╗
║  Docker Desktop (Windows) 换源                             ║
╚══════════════════════════════════════════════════════════╝

▶ Docker Hub 镜像加速:
  国内公共加速源已基本关停，建议使用云服务商提供的私有加速地址。
  配置路径: Docker Desktop → Settings → Docker Engine → 添加 registry-mirrors
""".strip()
    return """
╔══════════════════════════════════════════════════════════╗
║  Docker CE 安装源换到清华 TUNA                              ║
╚══════════════════════════════════════════════════════════╝

注意: 此为 Docker CE 软件安装源 (apt/yum)，非 Docker Hub 镜像加速。

▶ Ubuntu/Debian:
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://mirrors.tuna.tsinghua.edu.cn/docker-ce/linux/ubuntu/gpg | \\
    sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \\
    https://mirrors.tuna.tsinghua.edu.cn/docker-ce/linux/ubuntu \\
    $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \\
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt update

▶ CentOS/RHEL:
  sudo yum-config-manager --add-repo \\
    https://mirrors.tuna.tsinghua.edu.cn/docker-ce/linux/centos/docker-ce.repo

▶ Docker Hub 镜像加速:
  国内公共加速源已基本关停，建议使用云服务商提供的私有加速地址。
""".strip()


def get_npm_config() -> str:
    """返回 npm 换源配置"""
    return """
╔══════════════════════════════════════════════════════════╗
║  npm 换源到 npmmirror (阿里)                                ║
╚══════════════════════════════════════════════════════════╝

注意: TUNA 不提供 npm registry，使用阿里 npmmirror 替代。

▶ 临时使用:
  npm install <包名> --registry https://registry.npmmirror.com

▶ 永久配置:
  npm config set registry https://registry.npmmirror.com

▶ 使用 nrm 管理 (推荐):
  npx nrm use taobao
""".strip()


def auto_setup(tool: str) -> str:
    """根据工具名返回对应配置"""
    configs = {
        "pip": get_pip_config,
        "conda": get_conda_config,
        "brew": get_brew_config,
        "docker": get_docker_config,
        "npm": get_npm_config,
    }
    func = configs.get(tool.lower())
    if func:
        return func()
    return f"不支持的工具: {tool}\n支持的工具: {', '.join(configs.keys())}"


# ============================================================
# CLI
# ============================================================

def print_mirrors():
    """打印镜像列表"""
    mirrors = list_mirrors()
    print(f"\n镜像站 ({MIRROR_BASE})")
    print(f"   共 {len(mirrors)} 个镜像\n")
    print(f"{'序号':<4} {'状态':<4} {'名称':<30} {'URL'}")
    print("-" * 75)
    for i, m in enumerate(mirrors, 1):
        name = m.get("name", "")
        status = m.get("status", "")
        url = m.get("url", "")
        flag = "+" if status == "success" else "~" if status == "syncing" else "!"
        print(f"{i:<4} [{flag}]  {name:<28} {url[:42]}")


def main():
    if len(sys.argv) < 2:
        print("用法: python3 dlut_mirror.py <命令>")
        print()
        print("命令:")
        print("  list    列出所有可用镜像")
        print("  pip     pip 换源配置")
        print("  conda   conda 换源配置")
        print("  brew    Homebrew 换源配置")
        print("  docker  Docker CE 换源配置")
        print("  npm     npm 换源配置")
        sys.exit(0)

    cmd = sys.argv[1].lower()
    if cmd == "list":
        print_mirrors()
    elif cmd in ("pip", "conda", "brew", "docker", "npm"):
        print(auto_setup(cmd))
    else:
        print(f"未知命令: {cmd}")
        print("运行 python3 dlut_mirror.py 查看帮助")
        sys.exit(1)


if __name__ == "__main__":
    main()
