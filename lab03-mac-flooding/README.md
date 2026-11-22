# 课堂实验三：MAC 泛洪与二层端口安全防护

**实验日期：**2026-10-26  
**实验环境：**Windows 11、WSL2 Ubuntu 24.04、GNS3 2.2.61、MikroTik CHR 7.23.8

完整材料：[实验报告](docs/report.md) · [实验截图](evidence/screenshots) · [测试脚本](scripts/attack.py)

## 实验拓扑与目标

在 GNS3 中使用两台 CHR、四台 VPCS 和 Ubuntu Network Namespace，经 Cloud 连接为隔离的 `192.168.241.0/24` 二层实验网络。先观察多源 MAC 帧对交换设备地址表的影响，再配置端口学习限制与二层过滤规则，并检查正常通信是否受到影响。

## 实测结果

- 防御前，测试脚本发送 **256 帧**携带不同伪造源 MAC 的广播帧；SW2 的 `ether4` 地址表出现从 `02:AC:03:00:00:00` 到 `02:AC:03:00:00:FF` 的连续记录。
- 防御后启用 `ether4 learn=no`，结合源 MAC 白名单与 Bridge Forward DROP 规则，再次发送 256 帧；过滤计数由 **786** 增至 **1554**（新增 768 次规则命中），未观察到 `02:AC:04:00:*` 新 MAC 被学习。
- 修复误拦截配置后，合法测试主机到 PC1 的 Ping **3/3 成功**。
- 本实验验证了受控多源地址学习与限制效果，**未验证真实 CAM 表耗尽，也未使用 Cisco 原生 Port Security Shutdown**。

## 复现与排障说明

最初自动化实验包中 VPCS 的 `startup_script` 字段与当前 GNS3 GUI 不兼容，设备 IP 在 VPCS 控制台设置。早期防护配置缺少 `src-mac-address` 掩码，`configs/` 已保存修正后的命令；复现时应以最终配置为准。

原始实验使用受控的隔离二层网络。关于过滤计数、测试范围及局限性的完整解释见 [实验报告](docs/report.md)，测试代码仅用于授权教学环境。
