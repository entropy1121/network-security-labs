#!/usr/bin/env bash
# WSL/Linux 安全同步：只同步已由使用者明确提交的文件。
# 不会自动 git add -A，不会读取未跟踪的文件，也不会强制推送。
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ "$(git rev-parse --is-inside-work-tree)" != "true" ]]; then
  echo "错误：当前目录不是 Git 仓库" >&2
  exit 1
fi

BRANCH="$(git branch --show-current)"
if [[ "$BRANCH" != "main" ]]; then
  echo "为避免误推送，只允许从 main 同步；当前分支：$BRANCH" >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "检测到尚未提交或未跟踪的本地文件，已停止同步。" >&2
  echo "请先运行 git status --short，逐个检查文件，并仅提交希望公开的内容。" >&2
  echo "例如：git add lab06-ipv6-slaac/README.md" >&2
  echo "然后：git commit -m 'docs: 更新 Lab06 实验记录'" >&2
  exit 1
fi

echo "同步远端 main（仅快进，不覆盖本地提交）..."
git fetch origin main

if git merge-base --is-ancestor HEAD origin/main; then
  git merge --ff-only origin/main
elif git merge-base --is-ancestor origin/main HEAD; then
  echo "本地 main 有待推送的提交"
else
  echo "本地和远端 main 已分叉，出于安全原因不自动 rebase 或强制推送。" >&2
  echo "先备份/检查本地提交，再使用 git rebase origin/main 手动解决冲突。" >&2
  exit 1
fi

git push origin main
echo "GitHub 同步完成；如更新了实验目录，Actions 会自动检查根 README。"
