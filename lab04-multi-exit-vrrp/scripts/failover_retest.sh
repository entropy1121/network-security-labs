#!/usr/bin/env bash
# Scope: authorized local l04 Network Namespace lab only.
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo "Please use sudo"; exit 1; }
for ns in l04r1 l04r2 l04pc1 l04pc2 l04pc3 l04pc4; do
  ip netns list | grep -q "^$ns " || { echo "Missing $ns"; exit 1; }
done
BASE="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$BASE/evidence"
restore() {
  ip -n l04r1 link set wan up 2>/dev/null || true
  ip -n l04r2 link set wan up 2>/dev/null || true
  ip -n l04r1 route replace default via 172.30.41.1 dev wan 2>/dev/null || true
  ip -n l04r2 route replace default via 172.30.42.1 dev wan 2>/dev/null || true
}
trap restore EXIT
check() {
  echo "==== $1 ===="
  for r in 1 2; do
    echo "R$r"; ip -n "l04r$r" -br -4 addr show lan10; ip -n "l04r$r" -br -4 addr show lan20
  done
  for i in 1 2 3 4; do
    echo "PC$i"; ip netns exec "l04pc$i" ping -c 2 -W 2 198.51.100.10 || true
  done
}
{
check NORMAL
ip -n l04r1 link set wan down; sleep 7; check ISP1_DOWN
ip -n l04r1 link set wan up; ip -n l04r1 route replace default via 172.30.41.1 dev wan; sleep 7; check ISP1_RESTORED
ip -n l04r2 link set wan down; sleep 7; check ISP2_DOWN
ip -n l04r2 link set wan up; ip -n l04r2 route replace default via 172.30.42.1 dev wan; sleep 7; check ISP2_RESTORED
} | tee "$BASE/evidence/failover_newrun.txt"
