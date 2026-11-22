# Lab 06 命令行操作顺序

使用现有 WSL、Python 3 和 GNS3 2.2。脚本只连接本机 GNS3 API，从本机配置文件读取认证信息。默认使用 `127.0.0.1:3080`，不经代理。需要课件使用的 Huawei AR1kV QEMU 模板和镜像，仓库中没有设备镜像。

## 1. 检查现有环境

从仓库的 `lab06-ipv6-slaac` 目录执行：

```bash
python3 scripts/gns3_lab06.py check
```

- 若 GNS3 未监听，在一个独立的 WSL 终端用现有环境启动：`~/network-security/gns3/.venv/bin/gns3server`。
- 若监听但 API 超时，先核对 GNS3 启动窗口与端口。可用 `ss -ltnp '( sport = :3080 )'` 查监听，用 `sudo iptables -nvL INPUT --line-numbers` 查看规则和计数。先查原因，避免清空或重置整套规则。
- 若 API 通而 AR1kV 模板缺失，从课程提供的来源获取并导入镜像及模板，再执行 `check`。有多个匹配或模板以自定义名称注册时，在命令中加 `--router-template '确切模板名'`。镜像或模板缺失时，`build-a` 会在创建项目之前报错。

## 2. 第一条链路：单路由器和 RA 参数

```bash
python3 scripts/gns3_lab06.py build-a &&
python3 scripts/gns3_lab06.py start
```

脚本生成 `Lab06_IPv6_SLAAC`，连上 R1、SWA、PC1，并列出设备控制台端口。R1 按课件完成首启登录后，检查模板里的接口编号，用控制台粘贴 [R1 基线配置](../configs/R1-phase1.txt)。GNS3 GUI 同样可以打开相应控制台。

```bash
python3 scripts/gns3_lab06.py capture-start
```

在 PC1 执行 [VPCS 命令](../configs/PC1.txt)。保留终端输出后执行 `python3 scripts/gns3_lab06.py capture-stop`。要记录 RA 四项参数修改后的值，再开一轮新抓包，粘贴 [R1 RA 参数配置](../configs/R1-ra-fields.txt)，让 PC1 再执行 `ip auto` 或等待下一条 RA。两次抓包分别保存，文件名带 UTC 时间。

## 3. 第二条链路：双路由器优先级

```bash
python3 scripts/gns3_lab06.py build-b &&
python3 scripts/gns3_lab06.py start &&
python3 scripts/gns3_lab06.py capture-start --link r3-swb
```

依次用 [R1-B](../configs/R1-phase2.txt)、[R3 SLAAC](../configs/R3-slaac.txt)、[R2 medium](../configs/R2-medium.txt)、[R2 high](../configs/R2-high.txt)。分别在仅 R1、双 medium、R2 high 三个阶段记录 R3 的接口和路由表。结束用 `python3 scripts/gns3_lab06.py capture-stop --link r3-swb`。

在 GNS3 GUI 中按课件把 VMware VMnet8 的 Cloud 接到 SWB 的空闲口（脚本给 SWB 留了 Ethernet3）。确认 Cloud 绑定的是 Windows 上的目标虚拟网卡，再在 Windows 记录各阶段的地址和默认路由。脚本不推定 WSL 里的接口名称等同于 Windows VMnet8。需要 VMnet8 三阶段记录时，先接好该网卡再执行阶段对照。

抓包从脚本打印的路径或 GNS3 项目的 `captures` 中取。每组的命令输出和抓包帧号按 [验收表](verification.md) 记到本地。仓库只同步配置、脚本和匿名结果摘要。
