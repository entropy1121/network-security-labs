#!/usr/bin/env bash
set -Eeuo pipefail
[[ $EUID == 0 ]] || { echo 'sudo required'; exit 1; }
command -v tcpdump >/dev/null || { echo 'Please install tcpdump first'; exit 1; }
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ip -n l05pc1 link show eth0 >/dev/null
mkdir -p "$DIR/evidence"
tcpdump -ni l05p1 -U -s 0 -w "$DIR/evidence/02_nd_resolution.pcap" 'icmp6' > "$DIR/evidence/02_tcpdump.log" 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true' EXIT
sleep 1
ip -n l05pc1 -6 neigh flush dev eth0 >/dev/null
ip netns exec l05pc1 ping -6 -c 3 -W 2 2000::2
sleep 1
kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true
trap - EXIT
echo '===== PC1 Neighbors ====='
ip -n l05pc1 -6 neigh show dev eth0
echo '===== PCAP Decode ====='
tcpdump -nn -r "$DIR/evidence/02_nd_resolution.pcap" 'icmp6' | head -25
