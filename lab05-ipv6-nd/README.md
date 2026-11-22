# 课堂实验五：IPv6 邻居发现协议（NDP）

**最后核对：**2026-11-08  
**实验环境：**GNS3 2.2.61、VPCS 与隔离的 Linux Network Namespace；另保留 Huawei CE12800 测试记录。

## 实验内容与结果

| 实验项目 | 使用平台 | 实测结果 |
|---|---|---|
| NS/NA 地址解析 | GNS3 内置 Ethernet Switch + VPCS | VLAN100、VLAN200 内四个 Ping 方向均为 3/3 成功，抓到 ICMPv6 NS/NA |
| 跨交换机 802.1Q Trunk | GNS3 内置交换机 + VPCS | VLAN100 PC1↔PC5、VLAN200 PC3↔PC6，四个方向均 3/3；Trunk PCAP 中 VLAN100 和 VLAN200 标签报文各 16 帧 |
| DAD 唯一地址与重复地址检测 | Linux Namespace | 唯一地址通过；重复地址呈现 `dadfailed tentative` |
| 链路本地通信及静态邻居映射 | Linux Namespace | Link-local Ping 2/2；正确静态 MAC 2/2；错误 MAC 0/2；删除后恢复 2/2 |
| NUD 邻居状态观察 | Linux Namespace | 观察到 `REACHABLE`、`DELAY`、`INCOMPLETE`；`STALE`、`PROBE` 未确认 |
| 邻居缓存污染演示 | Linux Namespace | 在受控测试中观察到邻居缓存污染 |
| NA 欺骗与 DAD 干扰 | Linux Namespace | 有操作记录，但未确认预期攻击效果 |
| 任意播路由对照（`3888::/128`） | 独立 Linux Namespace 模型 | 路由选路后两条路径的 Ping 均 3/3；SWA 捕获 3 对请求/应答，SWB 捕获 2 对 |

## 华为设备与替代平台的区别

华为 CE12800（VRP 8.180）已完成 VLAN、Trunk、Vlanif 和 IPv6 配置检查，但端到端单播转发未通过实际报文测试。GNS3 内置交换机上的成功结果**不能等同于** CE12800 转发成功；独立 Linux Namespace 的任意播演示也不等于华为设备原生任意播行为。

参见 [详细验证记录](docs/verification-2026-11-08.md) 与 [公开实验报告摘要](docs/report-public.md)。

## 目录结构与复现入口

- `scripts/`：早期 Linux IPv6 对照实验脚本，作为历史记录保存。
- `gns3/scripts/05_fix_verify.py`、`10_*.py`—`14_*.py`：华为设备诊断、控制项目和稳定拓扑构建/恢复。
- `gns3/scripts/16_trunk_cross_switch.py`：跨交换机 802.1Q 测试。
- `isolated/scripts/15_neighbor_batch.py`：静态邻居和 NUD 测试。
- `isolated/scripts/17_anycast_isolated.py`：创建并清理临时 Namespace 的任意播路由对照。
- `docs/`：经检查的实测记录与平台差异说明。

GNS3 的 Python 工具是实验历史脚本，**不是可任意重复执行的一键安装器**。它们依赖原有项目名称、UUID、本机 GNS3 API 配置和部分历史工作目录。尤其不要对已建立的稳定项目直接重复执行 `13_build_stable.py`；脚本 14、16 会导入同目录下其他辅助函数。

Linux Namespace 实验需要管理员权限与隔离网络。脚本 15 依赖已经建立的 `l05*` Namespace；脚本 17 会创建并移除自己的临时 Namespace。运行前先核对脚本涉及的接口、路径与设备名称。

仓库不提供虚拟磁盘镜像、GNS3 凭据、含个人信息的报告封面或原始完整 DOCX。抓包和完整控制台日志保存在本地实验档案。
