# 附加 RA 安全实验的受控复现

这两个脚本只在本机 Linux network namespace 内创建三个节点和无地址的 Linux bridge。它们不连接 Windows 网卡、VMnet8 或物理网络。

## RA 欺骗与默认路由观察

先安装 Scapy，然后运行：

```bash
sudo apt install -y python3-scapy tcpdump
sudo python3 scripts/ra_spoof_lab.py
```

脚本先发一条合法的 R1 RA 并保存客户端基线路由，再发一条优先级为 high 的伪造 RA，记录客户端路由变化和 PCAP。实验结果只有在路由表确实出现相应变化时才能写成“默认路由被改变”。

## 有上限的 RA 处理观察

```bash
sudo python3 scripts/ra_bounded_load.py
```

默认上限为 5 个包/秒、持续 2 秒。可调参数硬限制为最多 10 个包/秒、3 秒，共 30 帧。PCAP 用来核对实际到达数量。该实验记录受控的报文处理现象，不据此声称设备资源耗尽或拒绝服务。

两项脚本各自创建 namespace 和隔离 bridge。各自结束后运行对应脚本的 `--cleanup` 删除该脚本的实验节点。输出默认保存在用户家目录的 `lab06-ra-spoof` 和 `lab06-ra-bounded`。
