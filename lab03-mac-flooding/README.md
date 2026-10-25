# Lab 03 — MAC Flooding / Bridge MAC Security

GNS3 2.2.61 · WSL2 Ubuntu 24.04 · MikroTik CHR 7.23.8 · VPCS · 2026-10-26

[完整实验报告](docs/report.md) · [操作结果摘录](docs/observations.txt) · [交换机配置](configs/sw2_defense.rsc) · [有界攻击脚本](scripts/attack.py)

**结果：** 防御前伪造源 MAC 广播帧 256 个，SW2 ether4 学习到 02:AC:03:00:00:00—:FF；防御后 ether4 设置 learn=no，过滤器 DROP 计数 786→1554（增加 768 次累计规则命中），未见 02:AC:04:00:* 的新学习记录。错误 DROP-only 策略曾造成合法 Ping 100% 丢包，补齐 MAC/MASK 放行规则后合法 Ping 3/3 成功。

**限制：** 本实验仅证明 GNS3 中 RouterOS 软件桥的 FDB 污染与学习/转发限制；不证明 CAM 溢出或 Cisco switchport port-security violation shutdown。隔离授权课堂网络专用。

实验截图及 Word 正式报告已打包交付，需将截图归档到本目录 evidence/screenshots；不向仓库上传交换机 qcow2 镜像、用户身份凭据或 GNS3 Server 认证配置。
