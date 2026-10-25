# Lab 04 — Multi-Exit Gateway Redundancy (VRRP)

**日期：**2026-10-26 · **环境：**Windows 11 / WSL2 Ubuntu 24.04 / Linux Network Namespace / 802.1Q Linux Bridge / Keepalived 2.2.8

双 ISP 网关冗余实验，实际使用 **VRRP 而不是 Cisco HSRP**。核心目标：VLAN10/20、四个 VRRP 备份组、两个网关分别首选两个出口、WAN 链路故障时转移虚拟 IP、恢复后抢占。

- R1 首选：10.44.10.1、10.44.20.1
- R2 首选：10.44.10.254、10.44.20.254
- PC1–PC4：分别是 10.44.10.11、10.44.10.12、10.44.20.13、10.44.20.14；分别使用上述网关
- 测试目的：198.51.100.10，分别存在于两条**隔离模拟 ISP** 的 loopback；不是实际访问公网。
- 故障机制：Keepalived `track_interface { wan }`，WAN DOWN 后优先网关进入 FAULT，另一路由器接管。
- 路由：静态默认路由与回程路由，**没有运行 OSPF**。

## 已验证的真实结果

| 稳态 | R1 VIP | R2 VIP | PC1–PC4 到模拟外网 |
|---|---|---|---|
| 正常 | .1 两组 | .254 两组 | 各 2/2 成功 |
| ISP1 Down | 无 | 四个全部 | 各 2/2 成功 |
| ISP1 恢复 | .1 两组 | .254 两组 | 各 2/2 成功 |
| ISP2 Down | 四个全部 | 无 | 各 2/2 成功 |
| ISP2 恢复 | .1 两组 | .254 两组 | 各 2/2 成功 |

故障状态是等待约 7 秒后再测；**不代表故障瞬间无丢包或切换时间为 7 秒。**

## 复现修复记录

- 最初 `keepalived -t` 在宿主 Namespace 校验，导致接口 lan10/lan20/wan 不存在；必须 `ip netns exec l04r1|l04r2 keepalived -t`。
- 初始脚本中止后 R2 配置文件没有生成；补齐配置后两端 VRRP 选举成功。
- WAN 从 DOWN 恢复时须 `ip route replace default via 172.30.41.1|172.30.42.1 dev wan`，恢复被内核移除的静态默认路由。
- ISP1 第一轮日志 `tee` 因权限拒绝未保存到目标文件，但用户粘贴了运行输出；ISP2 通过 `sudo tee` 保存成功。

**局限：**不是教师参考报告中的 Cisco HSRP/OSPF/GNS3 设备搭建，也未捕获链路切换瞬间丢包、收敛时间及 traceroute 路径变化。

实验完整 DOCX/PDF、拓扑图与修复后的 Bash 脚本由对话产出，原始本机命令输出需在 WSL 继续归档后推送。仅在自有隔离网络执行。
