# 课堂实验六：IPv6 无状态地址自动配置（SLAAC）

**实验日期：**2026-11-22  
**主要环境：**Windows 11、WSL2 Ubuntu 24.04、GNS3 2.2.61、MikroTik CHR、VPCS、Wireshark / tcpdump

本实验围绕 IPv6 的 Router Solicitation（RS）、Router Advertisement（RA）、无状态地址自动配置（SLAAC）与默认路由学习展开，采用抓包数据和终端输出相互验证。原指导书使用华为路由器；由于本地虚拟设备链路无法完成接收端报文验证，主要实测拓扑改为 GNS3 中的 MikroTik CHR。原华为配置保留在 `configs/` 供命令对照，不作为 CHR 的可执行配置。

## 一、实验拓扑与地址规划

```text
PC1（VPCS）── SWA ── R1（CHR）
                        │
                       SWB ─── R2（CHR）
                        │
                        ├────── R3（CHR）
                        └────── Cloud_VMnet8 ── WSL eth4 / Windows VMnet8
```

| 链路 | 路由器接口 / 主机 | IPv6 前缀 | 作用 |
|---|---|---|---|
| A（SWA） | R1 `ether3`、PC1 | `3001::/64` | PC1 通过 RA 自动配置 IPv6 地址 |
| B（SWB） | R1/R2/R3 `ether2`、Cloud | `2000::/64` | 单路由、多路由及默认路由选择 |
| Windows 接口 | VMware Network Adapter VMnet8，ifIndex 64 | 目标前缀 `2000::/64` | 检查宿主系统能否学习 RA |

两组二层广播域独立；`Cloud_VMnet8` 绑定 WSL `eth4`，其网卡 MAC 为 `00:50:56:c0:00:08`。这条桥接链路在 WSL 侧能抓到 RA，但不能据此推定 Windows 主机已经接收并采用该通告。

## 二、主要实验结果

| 实验环节 | 观察结果 |
|---|---|
| RS/RA 与 PC1 SLAAC | PC1 自动获得 `3001::2050:79ff:fe66:6800/64`；Ping R1 `3001::1` 5/5 成功 |
| RA 参数修改 | 接收端 PCAP 确认 Cur Hop Limit 32、Router Lifetime 900 s、Reachable Time 600000 ms、Retrans Timer 2000 ms |
| R3 单路由器 | R3 自动生成 `2000::e17:68ff:fe42:1/64`，并通过 R1 链路本地地址学习 `::/0` |
| 双路由器 Medium | R1/R2 均通告 Medium，R3 出现两条活动默认路由（ECMP） |
| R2 High | R2 的 RA 已验证为 High，R1 仍为 Medium；RouterOS R3 实际仍保留两条 ECMP 默认路由 |
| Cloud 与 WSL | WSL `eth4` 抓到 R1/R2 共四条真实 RA，通告前缀均为 `2000::/64` |
| Windows VMnet8 | 接口 RouterDiscovery 已启用，但只有 `fe80::` 地址，未学习全局 IPv6 地址和默认路由 |
| RA 安全扩展 | 保留伪造 RA、受控发送及抓包核验脚本；接收端攻击效果未获得相应报文证据 |

其中 **R2 High 后 R3 仍为 ECMP** 是当前 RouterOS 的实际实验现象。RA 通告优先级与接收设备的路由选用结果必须分别判断，不能仅凭 RA 字段推断主机一定切换了默认路由。

## 三、协议分析要点

1. **RS（ICMPv6 Type 133）：**主机主动请求路由器通告。
2. **RA（ICMPv6 Type 134）：**通告前缀、Router Lifetime、Cur Hop Limit、Reachable Time、Retrans Timer 等参数；前缀选项包含 L（On-link）和 A（Autonomous）标志。
3. **IPv6 Hop Limit 与 RA Cur Hop Limit：**前者位于 IPv6 首部，链路上的有效 RA 通常要求 Hop Limit=255；后者是 RA 内向主机建议的跳数限制，二者并非同一字段。
4. **接收端判定：**RA 可以在网络接口被抓到，不意味着系统必然安装地址或默认路由；需同时核对主机地址、路由表与连通性。

在本次 VPCS 测试中，CHR 默认通告的 Cur Hop Limit 为 0 时 PC1 `ip auto` 未成功；将 `/ipv6 nd` 的 `hop-limit` 配置为 64 后 PC1 正常获取地址。这属于当前 VPCS/CHR 组合的兼容性观察。

## 四、文件与复现入口

| 文件 | 内容 |
|---|---|
| [GNS3 API 脚本](scripts/gns3_lab06.py) | 建立/检查项目、设备状态与接收侧抓包 |
| [Linux SLAAC 对照脚本](scripts/linux_slaac.sh) | 独立 network namespace 对照实验 |
| [RA 抓包检查](scripts/verify_ra_capture.py) | 解析并校验真实抓包中的通告字段 |
| [RA 安全实验说明](docs/ra-security-lab.md) | 隔离网络下的安全测试思路及限制 |
| [实验结果与证据](docs/verification.md) | 各阶段验证结果和材料索引 |
| [阶段实验记录](docs/progress-2026-11-22.md) | 详细实验输出、排障经过和抓包对应关系 |
| [实验总结](docs/final-handoff-2026-11-22.md) | 关键成果及未完成环节 |
| [命令行说明](docs/cli.md) | 原华为设备的历史操作记录与脚本入口 |
| [华为参考配置](configs/) | 原指导书平台的命令存档，非 CHR 命令 |

实际运行 GNS3 项目之前，应确认本机的项目名称、节点编号与接口映射。脚本可能要求已有项目和用户本地 GNS3 API 配置，不应直接在其他人的运行中拓扑上执行。

## 五、抓包与安全注意事项

Wireshark 过滤表达式：

```wireshark
icmpv6.type == 133 || icmpv6.type == 134
```

RA Spoofing 和 RA Flooding 必须限定在经授权的隔离网络。伪造 RA 的构造结果、发送端记录、接收端抓包和主机路由变化属于不同层次的证据；没有接收端和路由变化证据时，不可据此声称攻击已经产生效果。
