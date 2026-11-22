# Lab06 最终交付状态（2026-11-22）

本文件为真实实验验收摘要，区分成功与未通过，不编造实验输出。

## 已通过

1. GNS3 + MikroTik CHR：PC1 从 R1 的 RA 生成 `3001::2050:79ff:fe66:6800/64`，`ping 3001::1` 成功 5/5。
2. PC1 侧 RA 实测更改 Cur Hop Limit=32、Router Lifetime=900s、Reachable Time=600000ms、Retrans Timer=2000ms。VPCS 正常 SLAAC 需要将 ND 通告 Cur Hop Limit 恢复至 64。
3. B 链路：R3 从 R1 的 RA 生成 `2000::e17:68ff:fe42:1/64`，经 R1 链路本地下一跳安装 `::/0`，Ping `2000::1` 成功。
4. R1、R2 均 Medium：R3 实测两条 `DAg +` 活动 `::/0` 路由，`belongs-to="slaac"`。
5. R2 High：真实新抓包证实 R2 发送 High RA，但 RouterOS R3 **仍保留两条 ECMP 默认路由**；不伪造指导书期待的高优先级独占选路。
6. GNS3 Cloud 接入 WSL `eth4`（MAC `00:50:56:c0:00:08`）后，WSL 25 秒抓到 R1、R2 的 RA 共 4 条，0 kernel drops。

## Windows VMnet8 未通过

- Windows VMnet8 ifIndex 64，RouterDiscovery=Enabled，ConnectionState=Connected，但仅有 `fe80::7986:6f53:884a:139%64`，**无 `2000::/64` 全局地址和 `::/0` 默认路由**；Ping R1 链路本地地址报告目标不可达。
- 用户上传 `lab06-windows.pcapng`：实际解析 130 帧，IPv6=104（NA Type 136:60、MLDv2 Type 143:44），RS/RA=0；主要捕获 Wi-Fi MAC 不能代表 VMnet8 RX。
- 用户上传 `lab06-vmnet8.pcapng`：通过 Pktmon 组件 1 专抓 VMware VMnet8，实际解析 20 帧（IPv4=10，ARP=10），IPv6/RS/RA=0，帧跨度约 49.77 秒。本链路未能在 Windows 侧观察到 RA，不能声称 SLAAC 成功；根因可能在 WSL 镜像接入 / Windows 网卡处理路径，但未最终证实。
- 已停止重复该 WSL-Cloud-VMnet8 方案，避免干扰宿主网络。

## 安全附加题证据边界

- Windows Scapy/Npcap RA Spoofing 和 bounded RA 发包脚本构造/dry-run 已准备；此前两份接收端相关抓包 RA=0，没有伪造 RA 被接收或路由劫持的证据。
- 没有 RA Flooding 导致 DoS、丢包或延迟升高的可验证记录。不得以构造好的 `constructed_*_NOT_CAPTURED.pcap` 冒充接收端证据。
- 发包仅限授权、独立隔离的虚拟二层网络，禁止在共享 VMnet8、真实 Wi-Fi 或校园网发送干扰性 RA。

## 已生成的本会话交付文件

- `Lab06_IPv6_SLAAC_实验报告_实测终稿.docx`：6 页、已有真实用户截图、明确标注未通过项。
- 对应 PDF、两份 Windows PCAPNG 统计 CSV、包含用户截图和现有脚本的 ZIP 交付包。
- 这些二进制文件保存在本次会话附件中；当前 GitHub 工具仅支持 UTF-8 文本文件，**没有将 DOCX/PDF/原始 PCAP 上传公共仓库**。

## 原始依据

完整复现和阶段记录：[progress-2026-11-22.md](progress-2026-11-22.md)；Linux namespace 对照：[linux-results.md](linux-results.md)。最终结论应以这两份日志、用户本地 GNS3 PCAP 和本次对 Windows PCAPNG 的原始解析为准。
