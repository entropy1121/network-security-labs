# GitHub 仓库同步与 README 自动更新

本说明适用于 `entropy1121/network-security-labs`，在 WSL/Linux 终端操作。仓库是公开仓库，请勿提交个人凭据、真实网络流量中的敏感内容、虚拟磁盘与未经筛选的抓包。

## 一、两种“同步”的区别

1. **本机 → GitHub：** 只有通过 `git add`、`git commit`、`git push` 的文件才会上传。网页端/聊天中的 GitHub 更新不会自动写回本机 WSL。
2. **GitHub README 自动更新：** 推送到 `main` 后，GitHub Actions 自动检查各个 `labXX-*` 文件夹，并据 Git 历史刷新仓库首页实验目录中的“最近提交”日期。工作流不需要访问本机电脑，也不会自动执行网络攻击脚本。

## 二、首次克隆

```bash
git clone https://github.com/entropy1121/network-security-labs.git
cd network-security-labs
```

如果仓库已经存在，直接进入原目录，不要重复克隆。

## 三、日常更新

**只需要拉取远端：** 确保没有本机未提交的改动后，运行：

```bash
bash scripts/sync-repo.sh
```

**希望把新的实验文档提交到 GitHub：** 先检查本地状态并明确选择文件：

```bash
git status --short
git add lab06-ipv6-slaac/README.md
git commit -m "docs: 更新 Lab06 实验记录"
bash scripts/sync-repo.sh
```

若要提交其他文件，把 `git add` 后面的路径换成实际文件名。**不要直接执行 `git add -A`**，防止将本地大体积数据、个人文件或新出现的敏感内容误传到公开仓库。

## 四、同步失败的处理

- **提示工作区不干净：** 先执行 `git status --short`，逐项检查；需要保留的内容先提交，不需要的内容先另存或自行处理。
- **提示本地与远端已分叉：** 先执行 `git log --oneline --graph --decorate -10 --all` 检查不同提交；备份后再考虑 `git rebase origin/main`。如遇冲突，修复后 `git rebase --continue`，无法确定时用 `git rebase --abort` 返回原状态。不要使用 `git push --force`。
- **GitHub 权限或网络错误：** 核对 `git remote -v`、登录凭据和代理连接。网络不通时文件仍保留在本机，不应反复重建实验拓扑。

## 五、README 自动更新是如何工作的

工作流：`.github/workflows/update-readme.yml`  
生成脚本：`scripts/update_readme.py`

每次推送 `lab*/**` 下的文件，或更新生成脚本/工作流时，Actions 将：

1. 检出仓库 `main` 分支及提交历史。
2. 查找根目录中名为 `labXX-*` 的实验子目录。
3. 用子目录真实存在的 README 文件链接和 Git 的最近提交日期生成表格。
4. 只改写根 `README.md` 中两个标记之间的实验目录；如果没有变化，就不生成额外提交。

要在本机提前预览：

```bash
python3 scripts/update_readme.py
git diff -- README.md
```

这个自动化**不会**自动更新每份实验报告的结论，也不会从未上传的抓包推断实验成功；实验内容仍由真实数据决定。

## 六、安全边界

`lab06-ipv6-slaac/.gitignore` 已排除 `evidence/`、`*.pcap`、`*.pcapng`。这只能降低误上传概率，不能代替提交前的隐私检查。不要把 WSL/Windows 的本地机密文件、账号或网络抓包原样提交公开仓库。
