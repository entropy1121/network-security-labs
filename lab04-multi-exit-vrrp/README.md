# 课堂实验四：多出口网关冗余与 VRRP 故障切换

**实验日期：**2026-10-26  
**实验环境：**Windows 11、WSL2 Ubuntu 24.04、Linux Network Namespace、802.1Q Linux Bridge、Keepalived 2.2.8

## 实验目标与环境差异

构建 VLAN10/20 中的冗余网关，配置四个 VRRP 备份组，验证主备网关在双出口网络故障和恢复时的虚拟 IP 接管。本实验采用 **VRRP，而非 Cisco HSRP**；路由使用静态默认路由及回程路由，**未运行 OSPF**。

- R1 优先使用虚拟网关：`10.44.10.1`、`10.44.20.1`。
- R2 优先使用虚拟网关：`10.44.10.254`、`10.44.20.254`。
- PC1–PC4：`10.44.10.11`、`10.44.10.12`、`10.44.20.13`、`10.44.20.14`。
- 模拟外网目标：两条**隔离 ISP** 的 Loopback `198.51.100.10`，不代表实际访问公网。
- 故障追踪：Keepalived `track_interface { wan }`，WAN 接口 DOWN 后由另一台设备接管 VIP。

## 实验结果

| 网络状态 | R1 持有 VIP | R2 持有 VIP | PC1–PC4 到模拟外网 |
|---|---|---|---|
| 正常 | 每 VLAN 的 .1 | 每 VLAN 的 .254 | 全部 2/2 成功 |
| ISP1 断开 | 无 | 四个 VIP | 全部 2/2 成功 |
| ISP1 恢复 | 每 VLAN 的 .1 | 每 VLAN 的 .254 | 全部 2/2 成功 |
| ISP2 断开 | 四个 VIP | 无 | 全部 2/2 成功 |
| ISP2 恢复 | 每 VLAN 的 .1 | 每 VLAN 的 .254 | 全部 2/2 成功 |

故障测试是在等待约 7 秒后重新发起的，不代表故障瞬间零丢包，也不代表测得的收敛时间为 7 秒。

## 关键排障与复现记录

1. `keepalived -t` 需要在对应的 Network Namespace 内执行，即 `ip netns exec l04r1 keepalived -t` 或 `l04r2`，否则找不到 `lan10`、`lan20`、`wan` 接口。
2. 初始脚本中止后 R2 配置尚未生成；补齐配置文件后两端 VRRP 选举恢复正常。
3. WAN 重新 UP 时需要恢复被内核移除的静态默认路由，例如 `ip route replace default via 172.30.41.1 dev wan`；另一出口使用 `172.30.42.1`。
4. ISP1 首次日志因 `tee` 权限问题未写入目标文件，但终端保留了实验输出；ISP2 使用 `sudo tee` 成功保存。

**实验范围：**这是 Linux Namespace 下的 Keepalived VRRP 对照实现，不是教师参考的 Cisco HSRP/OSPF GNS3 设备复现。实验也未测得故障瞬间的丢包率、精确收敛时间和 Traceroute 路径变化。

生成的 DOCX/PDF、拓扑图、修复后的脚本及本机原始日志按实验档案保存。相关测试仅用于授权隔离网络。
