# 实验三：MAC 泛洪攻击与端口安全防御（GNS3 / MikroTik CHR）

实验日期：2026-10-26；平台：Windows 11、WSL2 Ubuntu 24.04、GNS3 2.2.61、QEMU/KVM、RouterOS CHR 7.23.8、VPCS。

## 目标与环境

依据课堂课件要求，设计双交换机拓扑，对 SW2 进行伪造源 MAC 地址攻击，观察 MAC 学习表，并实施端口学习限制和二层转发过滤。SW1、SW2 均为 MikroTik CHR 软件桥，不使用 Huawei。

网络 192.168.241.0/24：PC1 .101、PC2 .102 分别接 SW2 ether1/ether2；PC3 .103、PC4 .104 分别接 SW1 ether1/ether2；两机通过 ether3 相连。Ubuntu Namespace .139（源 MAC 02:33:03:00:00:39）通过 GNS3 Cloud 接入 SW2 ether4。SW1、SW2 均配置 br-lab + RSTP，实验网络与外部网卡隔离。

## 基线与排障

PC1→PC2 Ping 5/5 成功；起初 PC3→PC4 失败。检查 SW1 的 bridge port 表为空，补齐 ether1–ether3 桥接后，跨交换机通信恢复（用户确认，未收到单独 Ping 成功截图）。攻击前，WSL 攻击端到 PC1 Ping 2/2 成功，平均 RTT 0.968 ms。SW2 学到正常 MAC，攻击端授权 MAC 出现在 ether4。

## 攻击：地址表污染

攻击代码见 [scripts/attack.py](../scripts/attack.py)。在限定 Namespace 内通过 AF_PACKET 发送 256 个广播以太帧，源 MAC 按序使用 02:AC:03:00:00:00—FF，EtherType 0x88B5，间隔 4 ms。终端真实输出：

```text
PHASE=before FRAMES_SENT=256 PREFIX=02ac0300 ELAPSED=1.060s
```

SW2 的 /interface bridge host print where on-interface=ether4 显示大量 02:AC:03:00:XX:XX 的 DYNAMIC 记录，首尾截图覆盖 00:00 至 00:FF。可证实测试造成 FDB 污染，但未测 CAM 硬件容量/耗尽，也未测转发性能衰减。

## 防御配置与误拦截修复

SW2 ether4 配置 learn=no 并添加授权 MAC；Bridge filter 的 forward 链先以 `src-mac-address=02:33:03:00:00:39/FF:FF:FF:FF:FF:FF` allow，再 drop 此端口其他源 MAC。初次漏掉 ALLOW，导致合法 Ping 0/3；补上正确 MAC/MASK 语法的 ALLOW 并移至 DROP 前后，两次合法 Ping 均 3/3 成功，平均 RTT 1.178 与 0.848 ms。最终控制台仍有两条同名 ALLOW（第二条冗余），不影响本次证据但复现时应去重。

## 重新攻击与量化

```text
PHASE=after FRAMES_SENT=256 PREFIX=02ac0400 ELAPSED=1.068s
```

| 防御规则累计统计 | 复测前 | 复测后 | 增量 |
|---|---:|---:|---:|
| 第一条 ALLOW packets | 4 | 8 | +4 |
| 第二条 ALLOW packets | 6 | 6 | 0 |
| DROP packets | 786 | 1554 | **+768** |
| DROP bytes | 36336 | 71664 | **+35328** |

复测后 SW2 ether4 Host Table 只显示 02:33:03:00:00:39 及本地 0C:C9:8A:99:00:03，未出现本轮 02:AC:04:00:* 新源 MAC。DROP 的 +768 表示桥接过滤链累计命中次数，**不是 768 个不同 MAC 或 768 个独立攻击发送帧**。768=256×3 与 SW2 的其他三条潜在广播转发接口数对应，可能是对多个转发副本分别计数，但实验未逐口抓包，不能将其作为已证实的机理。

## 结论与局限

验证了 MAC 泛洪对 RouterOS Bridge 动态地址学习表的污染、学习限制与白名单转发过滤的有效性，同时说明错误的全量 DROP 会使合法业务中断。该防御不等同 Cisco 的 switchport port-security / violation shutdown；未证明硬件 CAM 表耗尽、攻击导致的窃听或性能退化。合法 MAC 仍可能被冒用，故源 MAC 白名单不能替代更强的身份验证。

**证据索引：** 原始截图包包含课件要求、GNS3 拓扑、攻击前 FDB、伪造 MAC 表首尾、误拦截、复测前后规则计数和最终 learn=no 详情；程序与命令配置见本目录。所有结果源自本次实际 GNS3 实验记录，未将先前 Linux Bridge 实验结果混入。
