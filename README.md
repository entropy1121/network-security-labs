# 网络安全课程实验仓库

本仓库整理网络安全课程中使用 **GNS3、MikroTik RouterOS（CHR）、VPCS、WSL2 Ubuntu 和 Linux Network Namespace** 完成的实验，包括网络拓扑、配置脚本、验证记录、协议分析以及排障过程。每个实验单独归档，便于查看、复现和提交课程材料。

## 实验目录

下表由 GitHub Actions 根据实际实验文件夹自动维护；新增实验或更新子目录后，会在提交到 `main` 时检查并更新目录。

<!-- LAB_INDEX_START -->
| 实验 | 主题 | 详细说明 |
|---|---|---|
| Lab 01 | ACL 访问控制与包过滤 | [查看实验](lab01-acl-filtering/README.md) |
| Lab 02 | MAC 地址学习与端口安全 | [查看实验](lab02-mac-security/README.md) |
| Lab 03 | MAC 泛洪与二层端口防御 | [查看实验](lab03-mac-flooding/README.md) |
| Lab 04 | 多出口网关冗余与 VRRP 故障切换 | [查看实验](lab04-multi-exit-vrrp/README.md) |
| Lab 05 | IPv6 邻居发现协议（NDP） | [查看实验](lab05-ipv6-nd/README.md) |
| Lab 06 | IPv6 无状态地址自动配置（SLAAC） | [查看实验](lab06-ipv6-slaac/README.md) |
<!-- LAB_INDEX_END -->

## 最新实验：Lab 06 — IPv6 无状态地址自动配置

使用 GNS3 + MikroTik CHR 验证 Router Solicitation（RS）、Router Advertisement（RA）、SLAAC 前缀学习和多路由器通告：

- PC1 自动生成 `3001::/64` 地址并与 R1 通信；接收端抓包观察到 RS/RA。
- 修改 RA 的 Hop Limit、路由器生存期、可达时间和重传计时器，并使用 PCAP 验证。
- R3 在 `2000::/64` 链路上学习默认路由；对比 R1/R2 均为 Medium 以及 R2 改为 High 的情况。
- 记录 Windows VMnet8 接入过程及主机未获取全局 IPv6 地址的现象；RA 安全测试保留脚本和证据边界。

进入 [Lab 06 中文 README](lab06-ipv6-slaac/README.md) 查看具体配置、实测结果和文档索引。

## 仓库组织方式

实验目录通常使用以下结构，具体以各实验的 README 为准：

| 目录 | 内容 |
|---|---|
| `configs/` | 设备配置、接口与地址规划 |
| `scripts/` | GNS3 自动化、网络验证和隔离实验程序 |
| `docs/` | 实验步骤、数据分析、排障和阶段记录 |
| `evidence/`、`results/` | 已公开且适合共享的输出摘要、测试数据或截图 |
| `report/` | 如有公开版本，保存实验报告 |

大体积系统镜像、凭据、虚拟磁盘以及仅用于本地核验的抓包不随仓库发布。仓库中的技术结论按各实验实际平台和验证结果描述，不将 Linux 对照实验直接当作华为设备实测。

## 克隆、更新与同步

在 WSL / Linux 终端执行：

```bash
git clone https://github.com/entropy1121/network-security-labs.git
cd network-security-labs
git pull --ff-only origin main
```

本仓库提供 [安全同步脚本](scripts/sync-repo.sh) 与 [同步使用说明](docs/github-sync.md)：只同步已明确暂存、提交的文件，不会自动把本地抓包、个人文件或未知新文件上传到公开仓库。

**自动更新机制：** 提交到 `main` 后，[GitHub Actions](.github/workflows/update-readme.yml) 会执行 [目录生成脚本](scripts/update_readme.py)，发现实验目录有增减时自动更新本页索引。它无法直接读取本地 Windows/WSL 尚未推送的文件，因此本地内容仍须先通过 Git 提交和推送。

## 使用范围

网络干扰、伪造 RA 和 MAC 测试仅限授权的隔离实验拓扑，不应在校园网、公共网络或日常使用的宿主网络中直接执行。
