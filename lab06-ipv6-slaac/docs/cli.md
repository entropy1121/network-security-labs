# Lab06 命令行复现与抓包说明

本项目最终主要采用 **GNS3 2.2.61 + MikroTik CHR + VPCS**，而不是最初尝试的 Huawei CE12800/AR1kV。本目录的 `configs/R*.txt` 是早期华为平台命令存档，不能直接粘贴到 CHR。实际 CHR 结果见 [实验主页](../README.md) 与 [实测记录](progress-2026-11-22.md)。

## 一、GNS3 API 与现有项目

使用 WSL 的 Python 3，GNS3 控制器监听 `127.0.0.1:3080`。脚本默认从本机 `~/.config/GNS3/2.2/gns3_server.conf` 读取 API 认证信息，仓库不包含这些凭据。

已建立的实际项目名为 `Lab06_IPv6_SLAAC_CHR`。从本目录上一级 `lab06-ipv6-slaac/` 执行：

```bash
python3 scripts/gns3_lab06.py --project Lab06_IPv6_SLAAC_CHR start
```

该命令针对**已有项目**启动尚未启动的设备并列出终端端口。请不要重新执行 `build-a` 或 `build-b`，以免改变已经验收过的拓扑。脚本原先的 `check` / `build-*` 子命令默认查找 AR1kV 模板；若要在另一台机器上创建全新 CHR 项目，必须先安装并核对 CHR 的精确 QEMU 模板名称，再通过 `--router-template "实际模板名"` 显式指定。不同系统设备接口、控制台可能不同。

实验连接关系为：PC1—SWA—R1 `ether3`；R1/R2/R3 `ether2` 分别连接 SWB。二层前缀为 A：`3001::/64`，B：`2000::/64`。

## 二、抓取 R1→PC1 的 RS/RA

```bash
python3 scripts/gns3_lab06.py --project Lab06_IPv6_SLAAC_CHR capture-start
```

在 PC1 控制台执行 `ip auto` 后，停止捕获：

```bash
python3 scripts/gns3_lab06.py --project Lab06_IPv6_SLAAC_CHR capture-stop
```

脚本会输出 GNS3 的抓包文件路径。为防止覆盖或误读旧文件，开始下一轮实验前先停止当前抓包，再开始新抓包。

## 三、抓取 R3 所在交换链路的 RA

```bash
python3 scripts/gns3_lab06.py --project Lab06_IPv6_SLAAC_CHR --link r3-swb capture-start
```

在 RouterOS 控制台核对 IPv6 地址、ND 和默认路由：

```text
/ipv6 address print detail
/ipv6 nd print detail
/ipv6 route print detail where dst-address="::/0"
```

结束后停止：

```bash
python3 scripts/gns3_lab06.py --project Lab06_IPv6_SLAAC_CHR --link r3-swb capture-stop
```

**实验注意：** R2 High 的报文优先级和 RouterOS R3 的路由表并非同一项结果。本次 PCAP 已确认 R2 High，但 R3 保留双 ECMP 路由；两者在 [实验结果](verification.md) 中分别记录。

## 四、Windows VMnet8 扩展

本机曾将 `Cloud_VMnet8` 接入 SWB，并在 WSL 的 `eth4` 上抓到 4 条 R1/R2 RA。Windows VMnet8（ifIndex 64）启用了 Router Discovery，但未取得 `2000::/64` 地址与默认路由。Windows Pktmon 定向抓包也未捕获到 IPv6 RA，因此此部分只作为宿主机与镜像接口之间的排障分析。

WSL 中 `eth4` 是与 Windows VMnet8 MAC 相同的镜像接口；**相同 MAC 并不保证两个协议栈之间具有完整的双向二层桥接能力**。不要在宿主机生产网络上继续广播测试性 RA。

## 五、抓包与文档位置

Wireshark 显示过滤器：

```text
icmpv6.type == 133 || icmpv6.type == 134
```

原始 GNS3 PCAP、Windows PCAPNG 与截图存储在本地实验档案中，公开仓库仅存放可复现脚本和不含敏感网络信息的结果说明。

- [实测与证据索引](verification.md)
- [详细进度日志](progress-2026-11-22.md)
- [安全扩展实验](ra-security-lab.md)
