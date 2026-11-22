# 证据和验收

| 编号 | 保存位置（本地） | 验收 |
|---|---|---|
| V01 | `evidence/01-topology.png` | GNS3 截图显示两组独立链路、节点与接口 |
| V02 | `evidence/02-pc1-baseline.pcapng`、`02-pc1-console.txt` | 见 RS 和 RA，PC1 获得 `3001::/64` 地址，Ping R1 的结果有记录 |
| V03 | `evidence/03-ra-fields.pcapng`、`03-r1-interface.txt` | RA 正文的 32、900 s、600000 ms、2000 ms 与接口显示可对应 |
| V04 | `evidence/04-r3-single.pcapng`、`04-r3-routes.txt` | R3 自动生成 `2000::/64` 地址，预期默认下一跳为 `fe80::1` |
| V05 | `evidence/05-r3-medium.pcapng`、`05-r3-routes.txt` | 两台路由器的 Prf 均为 medium，指导书的 R3 路由表预期显示两个默认下一跳 |
| V06 | `evidence/06-r3-high.pcapng`、`06-r3-routes.txt` | `fe80::2` 的 Prf 为 high，`fe80::1` 仍为 medium，指导书的 R3 预期安装经 `fe80::2` 的默认路由 |
| V07 | `evidence/07-vmnet8.txt` | 对照三个阶段的 IPv6 地址、网关列表和路由表，标明 Windows 版本和接口 |
| V08 | `evidence/08-ra-analysis.txt` | 安全分析注明证据范围，网关变化看主机路由，业务中断看独立连通性或延迟测量 |

实测记录可按编号附上抓包帧号、终端输出和观察到的差异。课程附件、同学报告、镜像、原始抓包与含身份信息的截图留在本地。公开仓库后续可同步匿名化的结果摘要。

附加安全题可分析已有抓包，并说明 RA Guard 通过限定可信路由器端口减少未经授权的 RA 进入链路。捕获到异常 RA 说明抓包点可见该报文。主机是否接受、默认路由是否改变、业务是否受影响，各自需要独立证据。指导书中的两个主动实验暂无本人实测结果。
