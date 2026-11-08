# Network Security Labs

网络安全课程实验记录，主要使用 GNS3、WSL2 Ubuntu、Linux Network Namespace、虚拟网络设备及相关安全测试工具。每项实验分别记录配置、实测结果、排错过程和未完成的部分，不把替代平台的结果当作原设备验证。

## 实验目录

| 实验 | 主题 | 日期 | 记录 |
|---|---|---|---|
| [Lab 01](lab01-acl-filtering/README.md) | ACL 访问控制与包过滤 | 2026-10-17 | 实验报告与记录 |
| [Lab 02](lab02-mac-security/README.md) | MAC 地址表、端口安全与 MAC 泛洪攻防 | 2026-10-19 | 实验报告与记录 |
| [Lab 03](lab03-mac-flooding/README.md) | GNS3 MikroTik CHR MAC 泛洪与二层端口防御 | 2026-10-26 | 实测与复现代码 |
| [Lab 04](lab04-multi-exit-vrrp/README.md) | 双出口 VRRP 网关冗余与故障切换（WSL2） | 2026-10-26 | 实测与故障分析 |
| [Lab 05](lab05-ipv6-nd/README.md) | IPv6 邻居发现协议（NDP） | 2026-11-08 | 部分验证完成，附平台限制与测试记录 |

## Lab 05 — IPv6 Neighbor Discovery

第五次实验包括 NS/NA 地址解析、DAD 重复地址检测、静态邻居映射、邻居状态观察、跨交换机 802.1Q Trunk、任意播路由模型和隔离环境下的安全测试。

**已经取得的实测结果：** GNS3 内置 Ethernet Switch + VPCS 的 VLAN100/200 内通信成功；加入跨交换机测试主机后，两组 VLAN 的双向 Ping 均为 3/3，Trunk 抓包可见两种 802.1Q 标签；Linux Namespace 中完成了正常/冲突 DAD、正确与错误静态邻居项对照、部分 NUD 状态观察以及任意播路由切换。

**尚未完全验证：** 华为 CE12800 虽已配置 VLAN、Trunk、Vlanif 和 IPv6 地址，但端到端单播转发未通过；`STALE` / `PROBE` 状态未被确认；NA 欺骗、DAD 干扰的预期效果未证实。任意播成功结果来自独立 Linux 路由模型，**不等同于华为原生命令测试**。

查看 [Lab 05 完整实验说明](lab05-ipv6-nd/README.md)、[实测结果与局限](lab05-ipv6-nd/docs/verification-2026-11-08.md) 和 [匿名版实验记录](lab05-ipv6-nd/docs/report-public.md)。

## 实验环境与记录原则

使用过的环境和设备包括 Windows 11、WSL2 Ubuntu、GNS3、QEMU/KVM、MikroTik RouterOS、华为 CE12800 虚拟设备、VPCS、Linux Network Namespace、Wireshark 等。具体实验的设备与平台以各子目录 README 为准，不能据此认定所有环境目前均可直接运行。

本仓库公开保存可复现的脚本和必要的结果说明，不上传大型虚拟机镜像、认证凭据或包含个人身份信息的正式课程报告。完整原始抓包、日志与提交版 Word 由本地实验档案保存。
