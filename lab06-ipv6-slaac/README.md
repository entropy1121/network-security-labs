# Lab 06 · IPv6 无状态地址自动配置（SLAAC）

状态：配置与验收表已准备。AR1kV、VPCS 和 VMnet8 的实测结果待采集。

## 拓扑

| 二层链路 | 接入设备 | 地址 |
|---|---|---|
| A，GNS3 Ethernet Switch | R1 GE0/0/2、PC1（VPCS） | R1 为 `3001::1/64`，PC1 通过 SLAAC 生成地址 |
| B，另一台 GNS3 Ethernet Switch | R1、R2、R3 各自的 GE0/0/1，另按指导书接入隔离的 VMnet8 Cloud | R1 为 `2000::1/64` / `fe80::1`，R2 为 `2000::2/64` / `fe80::2`，R3 与 VMnet8 使用 SLAAC |

两条链路保持二层独立。先完成 A，再连 B。用空白 AR1kV 节点，完成初始控制台登录后再粘贴配置。GNS3 模板的端口编号和控制台接口名应先对照。配置按文件分段粘贴，出现命令错误就记录原信息，纠正后再继续。

## 执行顺序

1. R1 应用 [A 链路基线](configs/R1-phase1.txt)。先在 PC1 至交换机的链路启动抓包，再执行 [VPCS 命令](configs/PC1.txt)。保存 RS、RA、PC1 地址和 Ping 结果。若 VPCS 不支持 `show ipv6`，保存 `ip auto` 输出，并用 `show ?` 核对版本支持的显示命令。
2. 在 R1 应用 [RA 字段修改](configs/R1-ra-fields.txt)。等到新的 RA，或让 PC1 再执行 `ip auto`。以抓包中的 RA 正文核对四个字段。
3. B 链路先只开 R1 的 RA。应用 [R1-B 配置](configs/R1-phase2.txt) 和 [R3 SLAAC 配置](configs/R3-slaac.txt)，记录 R3 的地址和默认路由。
4. 在 R2 应用 [medium 配置](configs/R2-medium.txt)。抓到来自 `fe80::1` 和 `fe80::2` 的 RA 后，重新查看 R3 的 IPv6 路由表。
5. 将 R2 改为 [high](configs/R2-high.txt)。抓到 R2 的新 RA 后再查看路由表。R3 抓包和路由表分别证明通告优先级和设备安装的路由。若需重跑同优先级对照，在 R2 的接口视图恢复 `ipv6 nd ra preference medium`，收到新 RA 后再检查。
6. B 链路的 Windows VMnet8 部分在隔离的专用 VMware 网络内做。用 `ipconfig /all` 记录该适配器的地址与网关，用 `Get-NetRoute -AddressFamily IPv6 -DestinationPrefix '::/0' -InterfaceIndex <数字>` 查看对应接口的路由。把 `<数字>` 换成 `Get-NetIPInterface -AddressFamily IPv6` 查到的 VMnet8 接口索引。分别保留单路由、同优先级和 R2 high 三个阶段的输出。主机网卡的临时地址可以按实际情况记录，核心是确认 SLAAC 前缀和默认路由。

抓包显示过滤器 `icmpv6.type == 133 || icmpv6.type == 134`。同一交换机上优先在接收端所在链路抓包。若看不到 RS，确认抓包先于 `ip auto` 启动。若看到 RA 但缺少自动地址，依次检查 PIO 的 A 位、前缀长度和 DAD。若已有地址但无默认路由，检查 RA 源地址、IPv6 外层 Hop Limit 和 Router Lifetime。

- [验收与实验记录](docs/verification.md)
- [课堂测验速查](docs/quiz.md)
