# Lab 05 — IPv6 Neighbor Discovery (NDP)

**Updated: 2026-11-08.** This repository contains coursework experiments performed in **GNS3 2.2.61 / VPCS** and **isolated Linux Network Namespace** environments. The original Huawei CE12800 experiment and the alternative platforms are deliberately distinguished.

## Verified results

| Exercise | Platform | Observed outcome |
|---|---|---|
| NS / NA address resolution | GNS3 built-in Ethernet Switch + VPCS | Both VLAN100 and VLAN200: four same-VLAN ping directions, 3/3 replies each. ICMPv6 NS and NA captured. |
| Cross-switch 802.1Q trunk | GNS3 built-in switches + VPCS | VLAN100 PC1↔PC5 and VLAN200 PC3↔PC6: all four ping directions 3/3. Trunk PCAP: 16 VLAN100 and 16 VLAN200 tagged frames. |
| DAD (unique / duplicate) | Isolated Linux Namespace | Unique address accepted; duplicate address detected with `dadfailed tentative`. |
| Link-local and static neighbor mapping | Isolated Linux Namespace | Link-local ping 2/2; correct static MAC 2/2; deliberately wrong MAC 0/2; deletion restores 2/2. |
| NUD state observation | Isolated Linux Namespace | `REACHABLE`, `DELAY`, `INCOMPLETE` observed; `STALE` and `PROBE` **not confirmed**. |
| NS cache pollution demonstration | Isolated Linux Namespace | Neighbor-cache pollution observed in the controlled test. |
| NA spoofing / DAD interference | Isolated Linux Namespace | Attempts recorded; **success not confirmed**. |
| Anycast routing demonstration (`3888::/128`) | Temporary Linux Namespace routing model | Both paths ping 3/3 following route selection; SWA PCAP has 3 request/reply pairs, SWB PCAP only 2 pairs. |

**Huawei CE12800 (VRP 8.180):** VLAN, trunk, Vlanif, and IPv6 settings were entered and inspected, but end-to-end unicast forwarding did **not** pass the actual packet tests. The GNS3 built-in switch results do **not** prove Huawei CE12800 forwarding or native anycast operation. The Windows VMnet8 scenario from the teaching material was not fully replicated.

See [verification results](docs/verification-2026-11-08.md) and the [public, anonymized report summary](docs/report-public.md).

## Repository layout

- `scripts/`: earlier isolated Linux IPv6 experiment scripts, kept for history.
- `gns3/scripts/05_fix_verify.py` and `10_*.py`–`14_*.py`: Huawei diagnostics, control project, and GNS3 stable-project build/recovery.
- `gns3/scripts/16_trunk_cross_switch.py`: cross-switch 802.1Q test, used after the stable project was verified.
- `isolated/scripts/15_neighbor_batch.py`: static-neighbor and NUD test.
- `isolated/scripts/17_anycast_isolated.py`: standalone, temporary, routing-level anycast model.
- `docs/`: reviewed results and limitations.

## Reproduction notes

The GNS3 Python utilities are **experiment-history scripts, not a universal installer**. They contain safety checks for existing project names and UUIDs, use the local GNS3 API credentials from the user's configuration, and may require the original `~/network-security/Lab05_GNS3_Huawei_AutoKit` directory and saved state. In particular, **do not rerun `13_build_stable.py` on the already-created project**. Scripts 14 and 16 import its helpers when placed in the same `scripts` directory.

The Linux namespace tests require root privileges and a suitable isolated test network; script 15 expects the previously created `l05*` namespaces. Script 17 creates and removes its own temporary namespaces. Read source and verify local names/paths before executing anything.

No virtual disk image, GNS3 secrets, personally identifying course-report cover page, or raw final DOCX is included in this public repository. Original packet captures and full console logs remain in the experiment's local evidence directory. Do not present the anonymized report as the official signed submission.
