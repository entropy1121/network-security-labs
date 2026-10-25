# Lab 03 — MAC Flooding & Bridge Port Security (GNS3 / CHR)

2026-10-26 | Windows 11 + WSL2 Ubuntu 24.04 | GNS3 2.2.61 | MikroTik CHR 7.23.8

完整正文：[实验报告](docs/report.md) ｜ 截图：[evidence/screenshots](evidence/screenshots) ｜ 攻击脚本：[scripts/attack.py](scripts/attack.py)

- 双 CHR + 4 VPCS + Ubuntu Network Namespace，经 GNS3 Cloud 组成完全隔离的 192.168.241.0/24 二层网络。
- 防御前攻击程序发送 256 个不同伪造源 MAC 的广播帧；SW2 `ether4` 的地址表出现连续 `02:AC:03:00:00:00` 至 `:FF`。
- 防御后 `ether4 learn=no`，源 MAC 白名单 + Bridge forward DROP，复测 256 帧，过滤计数 `786→1554`（新增 768 次命中），未观察到 `02:AC:04:00:*` 新增 MAC。
- 误拦截修复后合法攻击端到 PC1 Ping 3/3 成功。没有验证 CAM 耗尽或 Cisco 原生 port-security shutdown。

> 安全范围：仅用于授权的隔离课堂实验。`docs/report.md` 对于计数与局限性提供了明确解释。

**注意：** 最初自动化实验包的 VPCS `startup_script` 字段与当前 GNS3 GUI 不兼容；设备 IP 在 VPCS 控制台配置。最初防御配置脚本缺少 `src-mac-address` 掩码，`configs/` 已更新为正确的复现实验命令。不要将最初实验包的早期错误命令当作最终版。
