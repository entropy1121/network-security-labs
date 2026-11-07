#!/usr/bin/env bash
# Isolated IPv6 ND lab: only interfaces/netns with l05 prefix
set -Eeuo pipefail
[[ $EUID == 0 ]] || { echo "sudo required"; exit 1; }
for x in ip bridge ping; do command -v "$x" >/dev/null || { echo "Missing $x"; exit 1; }; done
[[ -d /proc/sys/net/ipv6 ]] || { echo "IPv6 unavailable"; exit 1; }
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if ip netns list | grep -qE '^l05'; then echo "l05 namespace already exists; no changes"; exit 1; fi
for p in l05brA l05brB l05ab l05ba l05aTr l05bTr l05p1 l05p2 l05p3 l05p4 l05atkp; do
  if ip link show "$p" &>/dev/null; then echo "$p already exists; no changes"; exit 1; fi
done
rollback(){ echo 'Setup failed; cleaning Lab05 only'; bash "$DIR/scripts/99_cleanup.sh"; }
trap rollback ERR
mkdir -p "$DIR/evidence"
ip link add l05brA type bridge vlan_filtering 1 vlan_default_pvid 0
ip link add l05brB type bridge vlan_filtering 1 vlan_default_pvid 0
ip link set l05brA up; ip link set l05brB up
ip link add l05ab type veth peer name l05ba
ip link set l05ab master l05brA; ip link set l05ba master l05brB
for p in l05ab l05ba; do
  bridge vlan add dev "$p" vid 100
  bridge vlan add dev "$p" vid 200
  ip link set "$p" up
done
make_svi(){
  local ns="$1" p="$2" br="$3" mac="$4"
  ip netns add "$ns"; ip -n "$ns" link set lo up
  ip link add "$p" type veth peer name trunk netns "$ns"
  ip link set "$p" master "$br"
  bridge vlan add dev "$p" vid 100
  bridge vlan add dev "$p" vid 200
  ip link set "$p" up
  ip -n "$ns" link set trunk address "$mac"
  ip -n "$ns" link set trunk up
  for v in 100 200; do
    ip -n "$ns" link add link trunk name "lan$v" type vlan id "$v"
    ip -n "$ns" link set "lan$v" up
  done
}
make_svi l05swa l05aTr l05brA 02:05:05:00:00:0a
make_svi l05swb l05bTr l05brB 02:05:05:00:00:0b
make_pc(){
  local ns="$1" p="$2" br="$3" vid="$4" address="$5" mac="$6"
  ip netns add "$ns"; ip -n "$ns" link set lo up
  ip link add "$p" type veth peer name eth0 netns "$ns"
  ip link set "$p" master "$br"
  bridge vlan add dev "$p" vid "$vid" pvid untagged
  ip link set "$p" up
  ip -n "$ns" link set eth0 address "$mac"
  ip -n "$ns" link set eth0 up
  ip -n "$ns" -6 addr add "$address" dev eth0
}
make_pc l05pc1 l05p1 l05brA 100 2000::1/64 02:05:05:00:01:01
make_pc l05pc2 l05p2 l05brB 100 2000::2/64 02:05:05:00:01:02
make_pc l05pc3 l05p3 l05brA 200 3000::3/64 02:05:05:00:02:03
make_pc l05pc4 l05p4 l05brB 200 3000::4/64 02:05:05:00:02:04
make_pc l05atk l05atkp l05brA 100 2000::a/64 02:05:05:00:01:aa
ip -n l05swa -6 addr add fe80::1/64 dev lan100
ip -n l05swa -6 addr add fe80::1/64 dev lan200
ip -n l05swa -6 addr add 2000::ffff/64 dev lan100
ip -n l05swa -6 addr add 3000::ffff/64 dev lan200
ip -n l05swb -6 addr add 2000::eeee/64 dev lan100
ip -n l05swb -6 addr add 3000::eeee/64 dev lan200
sleep 3
for ns in l05pc1 l05pc2 l05pc3 l05pc4 l05atk l05swa l05swb; do
  if ip -n "$ns" -6 addr show | grep -q dadfailed; then echo "Unexpected DAD failure $ns"; false; fi
done
echo "===== VLAN trunk ====="
bridge vlan show dev l05ab
bridge vlan show dev l05ba
echo "===== PC1 -> PC2 VLAN100 ====="
ip netns exec l05pc1 ping -6 -c 2 -W 2 2000::2
echo "===== PC3 -> PC4 VLAN200 ====="
ip netns exec l05pc3 ping -6 -c 2 -W 2 3000::4
echo "===== SWA -> SWB VLAN100 ====="
ip netns exec l05swa ping -6 -c 2 -W 2 2000::eeee
echo "SETUP_PASS"
trap - ERR
