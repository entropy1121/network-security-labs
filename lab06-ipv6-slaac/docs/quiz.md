# SLAAC 测验速查

| 问题 | 要点 |
|---|---|
| SLAAC 怎样得到地址？ | 主机建立链路本地通信并执行 DAD。它可发送 RS 请求路由信息，收到 RA 后根据 PIO 通告的前缀及本机生成的接口标识形成地址，再对新地址做 DAD。接口标识可以由 EUI-64、稳定地址算法或隐私扩展生成，按平台和抓包判断。 |
| RS 怎么封装？ | ICMPv6 Type 133、Code 0，IPv6 Next Header 58（无扩展头时），IPv6 Hop Limit 255。目的通常为所有路由器 `ff02::2`，映射到 `33:33:00:00:00:02`。源通常为主机链路本地地址，地址尚不可用时可以为 `::`。 |
| RA 怎么封装？ | ICMPv6 Type 134、Code 0，IPv6 外层 Hop Limit 255，源为路由器链路本地地址。周期通告通常发往 `ff02::1`，对应 `33:33:00:00:00:01`。应答 RS 时也可单播。 |
| 怎么判定源、目的 MAC 类型？ | 看首字节最低位 I/G（0 单播、1 组播）和次低位 U/L（0 全球管理、1 本地管理）。IPv6 组播以 `33:33` 加目的 IPv6 地址的低 32 位映射。 |
| RA 正文的 Cur Hop Limit 是什么？ | 路由器建议主机在发出 IPv6 包时采用的默认跳数限制。实验改为 32 后，合法 RA 自己的外层 IPv6 Hop Limit 依然是 255。 |
| M/O 和 A/L/R 各管什么？ | M 指示可用有状态 DHCPv6 地址配置，O 指示可用 DHCPv6 获取其他参数。PIO 的 A 允许该前缀用于 SLAAC，L 表示可把前缀视为链路内。R 是移动 IPv6 的 Router Address 标志，普通 SLAAC 一般为 0。 |
| 三种生存时间怎么区分？ | Router Lifetime 决定该 RA 源可作为默认路由器保持多久，0 表示它不应作为默认路由器。PIO 的 Preferred Lifetime 到期后地址进入 deprecated，Valid Lifetime 到期后地址失效。 |
| Reachable Time 与 Retrans Timer 有何用途？ | 前者通告邻居可达性的参考时间，后者通告 NS 重传间隔。两字段在 RA 中的单位为毫秒。 |
| 两台路由器谁当网关？ | 可用性相当时，high 优先于 medium。指导书同优先级的 R3 路由表列出 `fe80::1` 和 `fe80::2`，R2 调为 high 后只显示 `fe80::2`。其他系统可能保留两个候选，具体采用哪个下一跳要看路由选择。 |
| 哪些答案应现场抄值？ | IPv6 Traffic Class、Flow Label、Payload Length、实际 MAC/IP、ICMPv6 校验和、选项数量及前缀生存时间以本次抓包为准。校验和包含 IPv6 伪首部。 |
