#!/usr/bin/env python3
"""根据仓库内的实验目录维护根 README 中的实验索引。

仅修改 LAB_INDEX_START / LAB_INDEX_END 之间的表格；使用 Python 标准库。
GitHub Actions 可以在 push 后调用此脚本，不依赖外部 API。
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
START = "<!-- LAB_INDEX_START -->"
END = "<!-- LAB_INDEX_END -->"

TITLES = {
    "lab01-acl-filtering": "ACL 访问控制与包过滤",
    "lab02-mac-security": "MAC 地址学习与端口安全",
    "lab03-mac-flooding": "MAC 泛洪与二层端口防御",
    "lab04-multi-exit-vrrp": "多出口网关冗余与 VRRP 故障切换",
    "lab05-ipv6-nd": "IPv6 邻居发现协议（NDP）",
    "lab06-ipv6-slaac": "IPv6 无状态地址自动配置（SLAAC）",
}


def latest_change(path: Path) -> str:
    """从该目录的 Git 历史获取最近一次提交的日期，而非推测实验完成日期。"""
    run = subprocess.run(
        ["git", "log", "-1", "--format=%cs", "--", path.name],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return run.stdout.strip() if run.returncode == 0 and run.stdout.strip() else "—"


def display_title(path: Path) -> str:
    if path.name in TITLES:
        return TITLES[path.name]
    readme = path / "README.md"
    if readme.is_file():
        for line in readme.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip().replace("|", "\\|")
    return path.name


def make_table() -> str:
    labs = [
        p for p in ROOT.iterdir()
        if p.is_dir() and re.fullmatch(r"lab\d{2}-[a-z0-9-]+", p.name)
    ]
    labs.sort(key=lambda p: p.name)
    rows = [
        "| 实验 | 主题 | 最近提交 | 详细说明 |",
        "|---|---|---|---|",
    ]
    for lab in labs:
        number = re.match(r"lab(\d{2})-", lab.name).group(1)
        link = f"{lab.name}/README.md" if (lab / "README.md").is_file() else lab.name
        rows.append(
            f"| Lab {number} | {display_title(lab)} | "
            f"{latest_change(lab)} | [查看实验]({link}) |"
        )
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="更新课程实验 README 索引")
    parser.add_argument(
        "--check", action="store_true",
        help="仅检查 README 索引是否需要更新，不写入文件",
    )
    args = parser.parse_args()

    raw = README.read_text(encoding="utf-8")
    if raw.count(START) != 1 or raw.count(END) != 1:
        raise SystemExit("README.md 必须恰好包含一组自动索引标记")
    left = raw.index(START) + len(START)
    right = raw.index(END, left)
    updated = raw[:left] + "\n" + make_table() + "\n" + raw[right:]

    if updated == raw:
        print("实验目录索引已经是最新")
        return 0
    if args.check:
        print("实验目录索引需要更新：运行 python3 scripts/update_readme.py")
        return 1

    README.write_text(updated, encoding="utf-8")
    print(f"已更新实验目录：{README}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
