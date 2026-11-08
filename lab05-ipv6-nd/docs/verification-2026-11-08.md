# Lab05 — 实测结果与未完成项目（2026-11-08）

本文件根据实际运行日志和 Wireshark / tcpdump 抓包汇总。这里的“通过”只指对应测试平台中观察到的结果，不代表课堂所有华为原生命令均成功。

## 一、GNS3 数据平面

- 项目：`Lab05_NDP_Stable_L2`，GNS3 2.2.61，内置 Ethernet Switch + VPCS。
- PC1 `2000::1/64`、PC2 `2000::2/64`（VLAN100）；PC3 `3000::3/64`、PC4 `3000::4/64`（VLAN200）。
- 同 VLAN Ping：PC1→PC2、PC2→PC1、PC3→PC4、PC4→PC3，均为 3/3。
- 基础抓包：每个 PC-facing PCAP 统计 NS=2、NA=2、EchoReply=6。Wireshark 可查看 NS Type 135 与 NA Type 136；NS 从 `2000::1` 发往 `ff02::1:ff00:2` 查询 `2000::2`。
- Trunk 脚本增加 PC5 `2000::5/64`（SWB VLAN100）与 PC6 `3000::6/64`（SWA VLAN200）；两组跨交换机双向 Ping 均为 3/3。
- Trunk 上 32 帧，分别为带 VLAN100、VLAN200 标签的 16 帧；PC5 / PC6 所在 Access 侧分别记录 16 帧、不带 802.1Q 标签。这只证明 VLAN 内二层转发与标签处理，**不证明跨 VLAN 路由**。

## 二、Linux Namespace / NDP

- 正常 DAD：新地址无冲突时启用。
- 重复 DAD：出现 `dadfailed tentative`，在抓包中观察到 NS 与冲突回应。
- 静态邻居：PC1→PC2 正确映射 2/2；配置错误 MAC `02:ff:ff:00:00:01` 后 0/2；删除错误项后 2/2，邻居表恢复 `REACHABLE`。
- 链路本地通信：SWA→SWB 的 link-local IPv6 ping 2/2（显式指定接口）。
- NUD：观察到 `REACHABLE`、`DELAY`、`INCOMPLETE`。**未确认 `STALE` 和 `PROBE`**；不能因为未观察到就断言协议缺失这些状态。
- 在授权隔离环境中观察到 NS 缓存污染；NA 欺骗及 DAD 干扰的目标效果未证实。

## 三、任意播路由模型

- 两个临时命名空间各持有 `3888::/128`；客户端先经过 SWA 的下一跳 `2001:db8:5:a::2`，之后使用 SWB 的 `2001:db8:5:b::2`。
- 两阶段客户端 Ping 均 3/3，证明路由选择切换后地址仍可达。
- SWA 抓到 3 对 Echo 请求/响应，SWB 只抓到 2 对；**不能声称 SWB 的 3 对报文全部抓取成功**。
- 测试结束后临时命名空间已清理。这是 Linux 路由级任意播模型，**不是华为 CE12800 原生 anycast 命令实验**。

## 四、华为工程与局限

- 原 GNS3 华为 CE12800 工程能够运行 VRP 命令，VLAN、Trunk、Vlanif 与 IPv6 地址有配置记录。
- 抓包发现华为工程同 VLAN 的 NS 组播能够转发，单播 NA / IPv4 Echo Request 未在对端出现；不能归因于“IPv6 协议错误”，也不能在无更多证据时武断认定为镜像 bug。
- 由于 CE12800 工程的端到端单播通信未通过，不能将内置交换机或者 Linux Namespace 的成功结果称为华为原生实验成功。
- 原指导材料中的 Windows VMnet8 及某些设备原生命令未按原环境完整复现。
- 实验截图、PCAP 及原始日志保存在本地；这份 GitHub 记录为可公开的结果摘要。

## 五、与实际输出对应的标志

- GNS3 VLAN 内通信：`GNS3_L2_BASELINE_PASS`
- GNS3 跨交换机 Trunk：`GNS3_TRUNK_VLAN100_200_PASS`
- 静态邻居批量测试：`LAB05_NEIGHBOR_BATCH_FINISHED`（不代表所有 NUD 状态均捕获）。
- 任意播：两阶段 Ping 成功，但 SWB PCAP 少 1 对包；不将其表述为完全抓包通过。

