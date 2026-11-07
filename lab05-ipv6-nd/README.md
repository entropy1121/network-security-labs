# Lab 05: IPv6 Neighbor Discovery

**Status: first-stage lab scripts awaiting validation on the user's WSL2.**

This replaces the Huawei CE12800 examples with Linux bridge VLAN filtering, Linux Network Namespace and real Linux IPv6 NDP/DAD behavior; no claims of Cisco/Huawei device execution. Distinct `l05` namespaces and interfaces avoid affecting Lab03/04.

- VLAN100: PC1 (`2000::1`), PC2 (`2000::2`), SWA (`2000::ffff`), SWB (`2000::eeee`), isolated test attacker (`2000::a`).
- VLAN200: PC3 (`3000::3`), PC4 (`3000::4`), SWA (`3000::ffff`), SWB (`3000::eeee`).
- Two Linux bridges as virtual switches connected by a tagged VLAN100/200 trunk; two namespace router stacks on tagged interfaces emulate SVIs.
- Stage 1: `sudo bash scripts/01_setup.sh` — creates topology, checks DAD failures, performs three baseline Pings.
- Stage 2: `sudo bash scripts/02_capture_nd.sh` — captures actual ICMPv6 NS, NA, Echo frames in `evidence/02_nd_resolution.pcap`. Requires `tcpdump`.
- Cleanup: `sudo bash scripts/99_cleanup.sh` — removes only Lab05 objects.

**Not yet implemented:** successful/failed DAD screenshots, neighbor state transitions, NS/NA spoofing and DAD attack tests; these are subsequent stages, not yet claimed done. All security demonstrations are limited to controlled, isolated namespace networks.
