# Lab06 实验结果与证据索引

**测试环境：**GNS3 2.2.61、MikroTik CHR、VPCS、WSL2 Ubuntu、Windows VMnet8。原始截图和 PCAP 保留于本地 `evidence/`，公开仓库记录可重复的观察结果。下表中的“实测”是本次实验终端输出与真实捕获文件对应的结果。

| 阶段 | 主要证据 | 结果 |
|---|---|---|
| A 链路 PC1 SLAAC | `chr-pc1-baseline.pcap`、PC1 终端截图 | 从 `3001::/64` 自动配置 `3001::2050:79ff:fe66:6800/64`，Ping R1 5/5 |
| RA 四字段变更 | `chr-ra-fields.pcap`、R1 参数输出 | Cur Hop Limit 32；Router Lifetime 900 s；Reachable Time 600000 ms；Retrans Timer 2000 ms |
| B 链路单路由 | R3 IPv6 地址与 `::/0` 终端输出 | 从 R1 学习 `2000::/64` 地址以及经 R1 链路本地地址的默认路由 |
| 双 Medium | `chr-r3-medium.pcap`、R3 路由表 | R1/R2 的 RA 均为 Medium，R3 有两条 `DAg +` 活动默认路由 |
| R2 High | `chr-r3-high.pcap`、R3 路由表 | 抓包确认 R2 High；RouterOS R3 仍显示两个 ECMP 默认下一跳 |
| Cloud 接收 RA | WSL `eth4` 的 `tcpdump` 输出 | 25 秒内捕获 R1/R2 的 4 条 RA，IPv6 Hop Limit=255，0 次内核丢包 |
| Windows VMnet8 地址学习 | `Get-NetIPAddress`、`Get-NetRoute`、两份 Windows PCAPNG | Windows 只有链路本地地址，无 `2000::/64` 地址和默认路由；定向捕获未发现 RA |
| RA 安全扩展 | Scapy 脚本、历史接收端抓包 | 提供隔离环境的构造与验证方法；现有抓包未证实伪造 RA 到达接收端或造成路由变化 |

## 报文分析说明

- **Type 133（RS）** 与 **Type 134（RA）** 的存在由接收端 PCAP 观察；不同实验阶段分开抓包。
- RA IPv6 首部的 Hop Limit=255 与 RA 内 Cur Hop Limit 字段作用不同。
- 在 R3 的 Medium 与 High 对照中，应将**通告优先级**和**R3 实际路由选择**分别陈述。
- `2000::/64` 在 WSL `eth4` 可见，不代表 Windows VMnet8 协议栈已经采用 SLAAC 参数。
- 安全测试中，报文构造、报文发送、接收端抓包、主机路由变化、连通性影响属于不同证据层次。

详细终端输出和时间顺序见 [进度日志](progress-2026-11-22.md)；复现入口见 [CLI 说明](cli.md)。
