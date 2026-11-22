#!/usr/bin/env bash
# Run normal Router Discovery and SLAAC in an offline WSL/Linux topology.
set -euo pipefail

if (( EUID != 0 )); then
  echo "用法：sudo bash scripts/linux_slaac.sh <新建的证据目录>" >&2
  exit 1
fi
for tool in ip radvd tcpdump ping; do
  command -v "$tool" >/dev/null || { echo "缺少 $tool" >&2; exit 1; }
done

out=${1:?需要一个尚未存在的证据目录}
mkdir -m 700 -- "$out"
out=$(realpath "$out")
exec > >(tee "$out/run.txt") 2>&1

prefix="lab06-$$"
r1="$prefix-r1"; r2="$prefix-r2"; r3="$prefix-r3"
pc="$prefix-pc"; sw="$prefix-sw"
namespaces=()
r1_daemon=""; r2_daemon=""; capture=""
cleanup() {
  set +e
  for pid in "$capture" "$r1_daemon" "$r2_daemon"; do
    if [[ -n $pid ]]; then
      kill -INT "$pid" 2>/dev/null
      wait "$pid" 2>/dev/null
    fi
  done
  for ns in "${namespaces[@]}"; do ip netns del "$ns"; done
  if [[ -n ${SUDO_UID:-} ]]; then chown -R "$SUDO_UID:$SUDO_GID" -- "$out"; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

for ns in "$r1" "$r2" "$r3" "$pc" "$sw"; do
  ip netns add "$ns"
  namespaces+=("$ns")
  ip -n "$ns" link set lo up
done

router_iface() {
  local ns=$1 nic=$2 address=$3
  ip netns exec "$ns" sysctl -qw net.ipv6.conf.all.forwarding=1
  ip netns exec "$ns" sysctl -qw "net.ipv6.conf.$nic.disable_ipv6=0"
  ip -n "$ns" link set dev "$nic" addrgenmode none
  ip -n "$ns" -6 addr add "$address" dev "$nic"
  ip -n "$ns" link set "$nic" up
}

pause_client() {
  local ns=$1 nic=$2
  ip netns exec "$ns" sysctl -qw "net.ipv6.conf.$nic.disable_ipv6=1"
  ip -n "$ns" link set "$nic" up
}

start_client() {
  local ns=$1 nic=$2
  ip netns exec "$ns" sysctl -qw "net.ipv6.conf.$nic.accept_ra=1" \
    "net.ipv6.conf.$nic.autoconf=1" "net.ipv6.conf.$nic.disable_ipv6=0"
}

write_ra() {
  local file=$1 nic=$2 net=$3 pref=$4 hop=$5 lifetime=$6 reachable=$7 retrans=$8
  cat > "$file" <<RA
interface $nic {
    AdvSendAdvert on;
    MinRtrAdvInterval 3;
    MaxRtrAdvInterval 5;
    AdvDefaultPreference $pref;
    AdvCurHopLimit $hop;
    AdvDefaultLifetime $lifetime;
    AdvReachableTime $reachable;
    AdvRetransTimer $retrans;
    prefix $net {
        AdvOnLink on;
        AdvAutonomous on;
    };
};
RA
}

start_ra() {
  local file=$1 ns=$2 variable=$3 pid
  ip netns exec "$ns" radvd -n -m stderr -C "$file" -p "${file%.conf}.pid" \
    >> "$out/radvd.log" 2>&1 &
  pid=$!
  printf -v "$variable" '%s' "$pid"
  sleep 0.6
  if ! kill -0 "$pid" 2>/dev/null; then
    cat "$out/radvd.log"
    echo "radvd 未启动：$file" >&2
    exit 1
  fi
}

stop_ra() {
  kill -TERM "$1"
  wait "$1" || true
}

start_capture() {
  local stage=$1 ns=$2 nic=$3
  ip netns exec "$ns" tcpdump -Z root -i "$nic" -U -w "$out/$stage.pcap" icmp6 \
    >> "$out/tcpdump.log" 2>&1 &
  capture=$!
  sleep 0.5
  kill -0 "$capture"
}

finish_capture() {
  local stage=$1
  kill -INT "$capture"
  wait "$capture" || true
  capture=""
  tcpdump -nn -vv -r "$out/$stage.pcap" > "$out/$stage-packets.txt" 2>&1
}

await_routes() {
  local ns=$1 nic=$2 net=$3; shift 3
  local routes addr hop ready attempt
  for ((attempt=0; attempt<60; attempt++)); do
    routes=$(ip -n "$ns" -6 route show default)
    addr=$(ip -n "$ns" -6 addr show dev "$nic" scope global)
    ready=1
    for hop; do
      if [[ " $routes " != *" via $hop "* ]]; then ready=0; fi
    done
    if (( ready )) && awk -v net="$net" '
      /inet6/ && index($2,net)==1 && !/tentative|dadfailed/ {ok=1}
      END {exit !ok}
    ' <<< "$addr"; then return 0; fi
    sleep 0.25
  done
  echo "超时：$ns 未获得所需地址或网关，继续保存当前证据。"
  return 1
}

record() {
  local stage=$1 ns=$2 nic=$3 router=$4
  {
    echo "=== $stage ==="
    ip -n "$ns" -6 addr show dev "$nic"
    echo '--- IPv6 默认路由 ---'
    ip -n "$ns" -6 route show default
    echo '--- 离链目标的路由选择（只查询，不发包） ---'
    ip -n "$ns" -6 route get 2001:db8:ffff::1 || true
    echo '--- Ping 在链路内的 R1 ---'
    ip netns exec "$ns" ping -6 -c 2 -W 1 "$router" || true
  } | tee "$out/$stage-state.txt"
}

date -Is
uname -r
printf '证据目录：%s\n' "$out"
printf '拓扑 A：R1（a1）直连 PC1（pa）。拓扑 B：R1、R2、R3 接隔离 Linux bridge。\n'
ip -n "$r1" link add a1 type veth peer name pa netns "$pc"
router_iface "$r1" a1 3001::1/64
ip -n "$r1" -6 addr add fe80::a1/64 dev a1 nodad
pause_client "$pc" pa
write_ra "$out/a-base.conf" a1 3001::/64 medium 64 1800 0 0
start_capture a-base "$pc" pa
start_ra "$out/a-base.conf" "$r1" r1_daemon
start_client "$pc" pa
await_routes "$pc" pa 3001: fe80::a1 || true
sleep 2
record a-base "$pc" pa 3001::1
finish_capture a-base

stop_ra "$r1_daemon"; r1_daemon=""
write_ra "$out/a-fields.conf" a1 3001::/64 medium 32 900 600000 2000
start_capture a-fields "$pc" pa
start_ra "$out/a-fields.conf" "$r1" r1_daemon
await_routes "$pc" pa 3001: fe80::a1 || true
sleep 5
record a-fields "$pc" pa 3001::1
finish_capture a-fields
stop_ra "$r1_daemon"; r1_daemon=""

ip -n "$sw" link add br0 type bridge
ip -n "$sw" link set br0 type bridge mcast_snooping 0
ip -n "$sw" link set br0 up
for side in 1 2 3; do
  case "$side" in
    1) ns=$r1 ;;
    2) ns=$r2 ;;
    3) ns=$r3 ;;
  esac
  ip -n "$ns" link add "b$side" type veth peer name "s$side" netns "$sw"
  ip -n "$sw" link set "s$side" master br0
  ip -n "$sw" link set "s$side" up
done
router_iface "$r1" b1 2000::1/64
router_iface "$r2" b2 2000::2/64
ip -n "$r1" -6 addr add fe80::1/64 dev b1 nodad
ip -n "$r2" -6 addr add fe80::2/64 dev b2 nodad
pause_client "$r3" b3

write_ra "$out/b-r1.conf" b1 2000::/64 medium 64 1800 0 0
write_ra "$out/b-r2-medium.conf" b2 2000::/64 medium 64 1800 0 0
write_ra "$out/b-r2-high.conf" b2 2000::/64 high 64 1800 0 0
start_capture b-single "$r3" b3
start_ra "$out/b-r1.conf" "$r1" r1_daemon
start_client "$r3" b3
await_routes "$r3" b3 2000: fe80::1 || true
record b-single "$r3" b3 2000::1
finish_capture b-single

start_capture b-medium "$r3" b3
start_ra "$out/b-r2-medium.conf" "$r2" r2_daemon
await_routes "$r3" b3 2000: fe80::1 fe80::2 || true
sleep 5
record b-medium "$r3" b3 2000::1
finish_capture b-medium

stop_ra "$r2_daemon"; r2_daemon=""
start_capture b-high "$r3" b3
start_ra "$out/b-r2-high.conf" "$r2" r2_daemon
await_routes "$r3" b3 2000: fe80::1 fe80::2 || true
sleep 5
record b-high "$r3" b3 2000::1
finish_capture b-high
printf '\n运行结束。实测证据：%s\n' "$out"
