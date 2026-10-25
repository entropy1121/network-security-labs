# 实验三：MAC 泛洪攻击与端口安全防御（GNS3 / MikroTik CHR）

**实验时间：** 2026年10月26日（日志时间）；**环境：** Windows 11、WSL2 Ubuntu 24.04、GNS3 2.2.61、QEMU/KVM、MikroTik CHR RouterOS 7.23.8、VPCS；**目标网络：** 192.168.241.0/24。

## 1. 实验目的与总体结论

在隔离 GNS3 拓扑中建立双交换机局域网，从 Ubuntu 攻击端向 SW2 注入具有不同伪造源 MAC 的广播帧，观察 SW2 的桥接转发表（FDB / Bridge Host Table）变化；随后对攻击入口配置 MAC 学习限制与二层源 MAC 过滤，并检验正常通信。参考课件提出“在 GNS 拓扑中向 SW2 发起 MAC 泛洪并防御”的目标。实验未使用 Huawei 设备，而以两台 MikroTik CHR 软件桥代替 Cisco IOL。

**主要结果：** 攻击程序在防御前后分别发送 256 帧。攻击前在 SW2 的 ether4 出现 `02:AC:03:00:*` 连续伪造源 MAC 地址记录；防御后 `ether4 learn=no`，SW2 没有显示本轮 `02:AC:04:00:*` 地址；过滤规则 DROP 累计计数由 786 增至 1554（+768 次命中）；补齐白名单规则后攻击端到 PC1 Ping 3/3 成功，丢包率 0%。这验证了地址表污染与相应过滤防御，但**没有**验证交换机 CAM 容量耗尽、广播窃听或 Cisco 的 violation shutdown。

## 2. 网络拓扑与设备地址

```text
PC1 192.168.241.101 ─ ether1 SW2 ether3 ─ ether3 SW1 ether1 ─ PC3 192.168.241.103
PC2 192.168.241.102 ─ ether2  |                         | ether2 ─ PC4 192.168.241.104
                              ether4
                                │
                   Ubuntu Attack NS 192.168.241.139
                     via GNS3 Cloud (l03gcloud)
```

SW2、SW1 均设置 `br-lab`（RSTP），分别桥接 ether1–ether4、ether1–ether3。WSL2 中 `l03gnatk` namespace 通过专用 veth 与 GNS3 Cloud 接入 SW2；攻击端使用授权源 MAC `02:33:03:00:00:39`。网络未绑定对外物理网卡或外部目标。

## 3. 基线通信和地址学习

初次排障中 PC1→PC2 Ping 5/5 成功，但 PC3→PC4 失败；排查发现 SW1 的 `/interface bridge port print` 为空，说明其桥接配置尚未执行。补充 SW1 的 Bridge 配置后，用户反馈跨交换机通信恢复。此处未收到跨交换机 Ping 完整截图，因此报告区分“用户确认恢复”与可见证据。

攻击前 SW2 Host Table 已含正常主机地址（例如 PC1 00:50:79:66:68:00、PC3 00:50:79:66:68:02）以及攻击端授权 MAC (`02:33:03:00:00:39`)，攻击入口为 ether4。WSL 攻击端→PC1 Ping 2/2 成功，平均 RTT 0.968 ms，证明 Cloud 接入在攻击前可以通信。

## 4. MAC 泛洪攻击实施与观察

攻击程序通过 Linux `AF_PACKET` 原始套接字发送二层广播帧，目标广播 MAC `FF:FF:FF:FF:FF:FF`、EtherType `0x88B5`，按序改变源 MAC 后 2 字节。程序设置运行环境检查，仅允许在特定攻击命名空间地址与 MAC 下运行；每阶段 256 帧，间隔 4 ms。

防御前命令及真实输出：

```bash
sudo ip netns exec l03gnatk python3 attack.py --phase before
# PHASE=before FRAMES_SENT=256 PREFIX=02ac0300 ELAPSED=1.060s
```

SW2 的 `/interface bridge host print where on-interface=ether4` 出现伪造 `02:AC:03:00:00:00`、`:01`……`:FF`，均关联 `ether4`，可见连续范围与 256 个源 MAC 的发送参数一致。图片截取了地址表的首尾两段，不据此声称已证明 FDB 容量耗尽。课件关注的“MAC 泛洪导致错误地址学习”已得到实测支持。

## 5. SW2 防御配置与调试

实际防御采用两层机制：

1. `ether4 learn=no`：阻止攻击入口继续动态学习新源 MAC。
2. `bridge filter forward`：对 `ether4` 的合法源 MAC 放行，其他流量丢弃。匹配 MAC 的正确格式为 `MAC/FF:FF:FF:FF:FF:FF`。

```routeros
/interface bridge port set [find where interface=ether4] learn=no
/interface bridge host add bridge=br-lab interface=ether4 mac-address=02:33:03:00:00:39
/interface bridge filter add chain=forward in-interface=ether4 src-mac-address=02:33:03:00:00:39/FF:FF:FF:FF:FF:FF action=accept comment=LAB03_ALLOW place-before=0
/interface bridge filter add chain=forward in-interface=ether4 action=drop comment=LAB03_DROP_SPOOF
```

调试中最初只有 `drop` 规则，导致攻击端到 PC1 Ping 3/3 丢失（100%）。补充正确语法的放行规则后，同一测试连续两次 3/3 成功（0% 丢包，平均 RTT 分别为 1.178 ms、0.848 ms）。最终截图中仍保留两个同名 `LAB03_ALLOW` 放行规则：其中一条未新增命中，属于调试冗余，报告不将其描述为设计需要。

## 6. 防御后复测与量化结果

```bash
sudo ip netns exec l03gnatk python3 attack.py --phase after
# PHASE=after FRAMES_SENT=256 PREFIX=02ac0400 ELAPSED=1.068s
```

| 指标 | 复测前 | 复测后 | 差值 |
|---|---:|---:|---:|
| 第一条 ALLOW 规则（packets） | 4 | 8 | +4 |
| 第二条 ALLOW 规则（packets） | 6 | 6 | 0 |
| DROP 规则（packets） | 786 | 1554 | **+768** |
| DROP 规则（bytes） | 36336 | 71664 | **+35328** |
| SW2 ether4 `learn` | no | no | 维持关闭 |
| `02:AC:04:00:*` 在 SW2 Host Table | 未观察到 | 未观察到 | 无新学习证据 |

`DROP +768` 是桥接过滤链的**累计命中增量**，不是实际发送 768 帧、也不是 768 个不同 MAC。由于 256 个广播帧与 SW2 另三条可转发端口构成 256×3=768，存在按不同转发路径计数的合理解释，但未单独抓包确认，不能视为已证明的因果机制。

复测后 SW2 `ether4` 的 Host Table 只显示授权 MAC `02:33:03:00:00:39` 和本地地址 `0C:C9:8A:99:00:03`；配合过滤计数增量及合法 Ping 恢复，支持“防止新的伪造 MAC 学习，并阻断该测试流量转发”这一结论。

## 7. 结论、限制与反思

本实验在真实运行的 GNS3 RouterOS 软件桥中观察到 MAC 泛洪造成的动态地址学习，随后通过端口学习限制和源 MAC 过滤，使后续伪造地址不再出现在 SW2 学习表中，并保留合法通信。初次部署漏掉放行规则产生误拦截，说明端口防御需要同时测试**拦截非法流量**和**保留合法业务**。

**适用边界：** MikroTik 软件桥不同于 Cisco IOL 的 `switchport port-security`，未演示 `violation shutdown`；未验证硬件 CAM 溢出、窃听效果、性能退化；静态源 MAC 白名单不能防止攻击者冒用已经授权的 MAC。本实验是受控源 MAC 泛洪与二层过滤的可重复验证，不是对真实网络的攻击证明。

## 8. 证据索引

- `00_course_requirements.png`：课程目标与参考拓扑。
- `01_gns3_topology.png`：实际项目双交换机拓扑；截图时节点标识为红色，**不可作为运行状态证据**。
- `02_sw2_fdb_baseline.png`、`03_sw2_fdb_before_attack_port.png`：攻击前地址表与 `ether4`。
- `04_attack_fdb_first.png`、`05_attack_fdb_last.png`：攻击后伪造 MAC 学习表首尾。
- `06_initial_drop_ping_failure.png`：错误规则导致 100% 丢包。
- `07_defense_filter_before.png`、`08_defense_filter_after.png`：过滤命中复测前后对比。
- `09_final_sw2_port_and_rules.png`、`10_final_sw2_detail.png`：最终 `learn=no`、地址表和规则。
- `11_gui_startup_script_error.png`、`12_zip_location.png`：环境排障附录证据，不作为攻防验证依据。

**可复现性：** 代码见 `scripts/attack.py`，RouterOS 命令见 `configs/`。仅在隔离、已授权的 GNS3 实验环境运行。设备 qcow2 镜像和私有认证配置不入库。 
