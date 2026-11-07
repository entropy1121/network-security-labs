#!/usr/bin/env bash
# Lab05-only: bounded NS/NA and DAD tests, evidence capture and recovery.
set -Eeuo pipefail
[[ $EUID == 0 ]] || { echo 'Run with sudo'; exit 1; }
DIR="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$DIR/evidence"
for ns in l05atk l05pc1 l05pc2 l05swa l05swb; do
  ip netns list | grep -q "^$ns " || { echo "Missing $ns"; exit 1; }
done
for p in l05atkp l05p1; do ip link show "$p" >/dev/null; done
command -v tcpdump >/dev/null || { echo 'Install tcpdump'; exit 1; }
cap_pid=''; cap2_pid=''; dad_pid=''
restore() {
  ip -n l05pc1 -6 addr del 2000::55aa/64 dev eth0 2>/dev/null || true
  for pid in "$dad_pid" "$cap_pid" "$cap2_pid"; do
    if [[ -n "$pid" ]]; then kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi
  done
  ip -n l05pc1 -6 neigh flush to 2000::2 dev eth0 >/dev/null 2>&1 || true
  ip -n l05pc2 -6 neigh flush to 2000::1 dev eth0 >/dev/null 2>&1 || true
  ip -n l05swa -6 neigh flush dev lan100 >/dev/null 2>&1 || true
  ip -n l05swb -6 neigh flush dev lan100 >/dev/null 2>&1 || true
}
trap restore EXIT
echo '===== START CAPTURE ====='
tcpdump -i l05atkp -nn -U -s 0 -w "$DIR/evidence/04_security_tests.pcap" icmp6 > "$DIR/evidence/04_tcpdump.log" 2>&1 &
cap_pid=$!
tcpdump -i l05p1 -nn -U -s 0 -w "$DIR/evidence/04_pc1_nd.pcap" icmp6 > "$DIR/evidence/04_pc1_tcpdump.log" 2>&1 &
cap2_pid=$!
sleep .5
kill -0 "$cap_pid"; kill -0 "$cap2_pid"

echo '===== NS BASELINE ====='
ip -n l05pc2 -6 neigh flush to 2000::1 dev eth0 >/dev/null || true
ip netns exec l05pc2 ping -6 -c 2 -W 2 2000::1
ip -n l05pc2 -6 neigh show 2000::1 dev eth0

echo '===== FORGED NS: 5 FRAMES ====='
ip netns exec l05atk python3 -u "$DIR/scripts/nd_probe.py" ns
sleep .5
result="$(ip -n l05pc2 -6 neigh show 2000::1 dev eth0)"
echo "PC2_NEIGHBOR_AFTER_NS: $result"
if [[ "$result" == *02:05:05:00:01:aa* ]]; then
  echo 'NS_CACHE_POISON_OBSERVED'
else
  echo 'NS_CACHE_POISON_NOT_CONFIRMED'
fi
ip -n l05pc2 -6 neigh flush to 2000::1 dev eth0 >/dev/null || true
ip netns exec l05pc2 ping -6 -c 2 -W 2 2000::1

echo '===== NA BASELINE ====='
ip -n l05pc1 -6 neigh flush to 2000::2 dev eth0 >/dev/null || true
ip netns exec l05pc1 ping -6 -c 2 -W 2 2000::2
ip -n l05pc1 -6 neigh show 2000::2 dev eth0

echo '===== FORGED NA: 5 FRAMES ====='
ip netns exec l05atk python3 -u "$DIR/scripts/nd_probe.py" na
sleep .5
result="$(ip -n l05pc1 -6 neigh show 2000::2 dev eth0)"
echo "PC1_NEIGHBOR_AFTER_NA: $result"
if [[ "$result" == *02:05:05:00:01:aa* ]]; then
  echo 'NA_CACHE_POISON_OBSERVED'
else
  echo 'NA_CACHE_POISON_NOT_CONFIRMED'
fi
ip -n l05pc1 -6 neigh flush to 2000::2 dev eth0 >/dev/null || true
ip netns exec l05pc1 ping -6 -c 2 -W 2 2000::2

echo '===== DAD INTERFERENCE: 2000::55aa ====='
if ip -n l05pc1 -6 addr show dev eth0 | grep -q '2000::55aa'; then
  echo 'Candidate address exists; no changes'; exit 1
fi
if [[ "$(ip netns exec l05pc1 sysctl -n net.ipv6.conf.eth0.accept_dad)" == 0 ]]; then
  echo 'DAD disabled; cannot test'; exit 1
fi
ip netns exec l05atk python3 -u "$DIR/scripts/nd_probe.py" dad > "$DIR/evidence/04_dad_spoof.log" 2>&1 &
dad_pid=$!
ready=0
for i in $(seq 1 30); do
  if grep -q 'DAD_SENDER_READY' "$DIR/evidence/04_dad_spoof.log"; then ready=1; break; fi
  if ! kill -0 "$dad_pid" 2>/dev/null; then break; fi
  sleep .1
done
if [[ $ready != 1 ]]; then cat "$DIR/evidence/04_dad_spoof.log"; echo 'DAD_SENDER_NOT_READY'; exit 1; fi
ip -n l05pc1 -6 addr add 2000::55aa/64 dev eth0
sleep 3
cat "$DIR/evidence/04_dad_spoof.log"
ip -n l05pc1 -6 addr show dev eth0 | grep -A 2 '2000::55aa' || true
result="$(ip -n l05pc1 -o -6 addr show dev eth0 | grep '2000::55aa/64' || true)"
if [[ "$result" == *dadfailed* ]]; then
  echo 'DAD_SPOOF_EFFECT_CONFIRMED'
else
  echo 'DAD_SPOOF_EFFECT_NOT_CONFIRMED'
fi
ip -n l05pc1 -6 addr del 2000::55aa/64 dev eth0
wait "$dad_pid" || true
dad_pid=''

echo '===== RESTORE AND VERIFY ====='
restore
ip netns exec l05pc1 ping -6 -c 2 -W 2 2000::2
ip netns exec l05pc2 ping -6 -c 2 -W 2 2000::1
ip -n l05pc1 -6 neigh show 2000::2 dev eth0
ip -n l05pc2 -6 neigh show 2000::1 dev eth0
echo '===== PCAP DECODE ====='
tcpdump -nn -r "$DIR/evidence/04_security_tests.pcap" icmp6 | grep -Ei 'neighbor solicitation|neighbor advertisement' | tail -25 || true
echo 'SECURITY_STAGE_FINISHED'
