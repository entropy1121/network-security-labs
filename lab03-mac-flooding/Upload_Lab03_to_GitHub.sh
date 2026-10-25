#!/usr/bin/env bash
set -euo pipefail

# Usage: bash Upload_Lab03_to_GitHub.sh [ZIP_PATH] [REPO_DIR]
ZIP_PATH="${1:-$HOME/Download/Lab03_Report_Evidence_GitHub_Ready.zip}"
REPO_DIR="${2:-$HOME/network-security/network-security-labs}"
REPO_URL='https://github.com/entropy1121/network-security-labs.git'

if [[ ! -f "$ZIP_PATH" ]]; then
  echo "ERROR: ZIP not found: $ZIP_PATH" >&2
  exit 1
fi

if [[ ! -d "$REPO_DIR/.git" ]]; then
  if [[ -e "$REPO_DIR" ]]; then
    echo "ERROR: destination exists but is not a Git repository: $REPO_DIR" >&2
    exit 1
  fi
  mkdir -p "$(dirname "$REPO_DIR")"
  git clone "$REPO_URL" "$REPO_DIR"
fi

remote="$(git -C "$REPO_DIR" remote get-url origin)"
if [[ "$remote" != *'github.com/entropy1121/network-security-labs'* && "$remote" != *'github.com:entropy1121/network-security-labs'* ]]; then
  echo "ERROR: unexpected origin repository: $remote" >&2
  exit 1
fi

if [[ -n "$(git -C "$REPO_DIR" status --porcelain)" ]]; then
  echo 'ERROR: local repository has uncommitted changes; commit or stash them first.' >&2
  exit 1
fi

# Synchronize any files created via ChatGPT's connected GitHub app.
git -C "$REPO_DIR" checkout main
git -C "$REPO_DIR" pull --ff-only origin main

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
python3 -m zipfile -e "$ZIP_PATH" "$TMP"
SOURCE="$TMP/Lab03_Report_Package"
if [[ ! -f "$SOURCE/docs/report.md" || ! -d "$SOURCE/evidence/screenshots" ]]; then
  echo 'ERROR: unexpected report archive structure.' >&2
  exit 1
fi

TARGET="$REPO_DIR/lab03-mac-flooding"
mkdir -p "$TARGET"
cp -a "$SOURCE/." "$TARGET/"

git -C "$REPO_DIR" add lab03-mac-flooding
if git -C "$REPO_DIR" diff --cached --quiet; then
  echo '[OK] No new changes to upload.'
  exit 0
fi

git -C "$REPO_DIR" commit -m 'Add Lab03 report, screenshots and verified experiment files'
git -C "$REPO_DIR" push origin main

echo '[OK] GitHub upload complete:'
echo 'https://github.com/entropy1121/network-security-labs/tree/main/lab03-mac-flooding'
