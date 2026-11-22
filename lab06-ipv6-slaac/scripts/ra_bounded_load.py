#!/usr/bin/env python3
"""Bounded RA processing measurement in an isolated Linux namespace."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

# Hard caps keep this a short protocol-processing measurement.
MAX_PPS = 10
MAX_SECONDS = 3
PREFIX = "l6load"
BRIDGE = "l6ldbr"
ROLES = {"router": ("ld-rh", "r0"), "client": ("ld-ch", "c0"), "sender": ("ld-sh", "s0")}


def cmd(*args, check=True, capture=False):
    return subprocess.run(args, check=check, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.STDOUT if capture else None)


def ip(*args, **kw):
    return cmd("ip", *args, **kw)


def cleanup():
    for role in ROLES:
        ip("netns", "del", f"{PREFIX}-{role}", check=False)
    ip("link", "del", BRIDGE, check=False)
    for host, _ in ROLES.values():
        ip("link", "del", host, check=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default=str(Path.home() / "lab06-ra-bounded"))
    p.add_argument("--pps", type=int, default=5)
    p.add_argument("--seconds", type=int, default=2)
    p.add_argument("--cleanup", action="store_true")
    a = p.parse_args()
    if a.cleanup:
        cleanup()
        return
    if not (sys.platform.startswith("linux") and __import__("os").geteuid() == 0):
        raise SystemExit("Run from WSL/Linux with sudo.")
    if not 1 <= a.pps <= MAX_PPS or not 1 <= a.seconds <= MAX_SECONDS:
        raise SystemExit(f"Bounds: 1-{MAX_PPS} packets/s and 1-{MAX_SECONDS} seconds.")
    try:
        import scapy.all as sc
    except ImportError:
        raise SystemExit("Install Scapy with: sudo apt install python3-scapy")
    cleanup()
    ip("link", "add", BRIDGE, "type", "bridge"); ip("link", "set", BRIDGE, "up")
    for role in ROLES:
        ip("netns", "add", f"{PREFIX}-{role}")
        ip("-n", f"{PREFIX}-{role}", "link", "set", "lo", "up")
    for role, (host, inside) in ROLES.items():
        ip("link", "add", host, "type", "veth", "peer", "name", inside)
        ip("link", "set", inside, "netns", f"{PREFIX}-{role}")
        ip("link", "set", host, "master", BRIDGE); ip("link", "set", host, "up")
        ip("-n", f"{PREFIX}-{role}", "link", "set", inside, "up")
    ip("-n", f"{PREFIX}-router", "-6", "addr", "add", "2001:db8:6::1/64", "dev", "r0")
    ip("-n", f"{PREFIX}-sender", "-6", "addr", "add", "fe80::dead:beef/64", "dev", "s0", "nodad")
    ip("netns", "exec", f"{PREFIX}-client", "sysctl", "-qw", "net.ipv6.conf.c0.accept_ra=2")
    out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    cap=subprocess.Popen(["tcpdump","-U","-i","ch","-w",str(out/"ra-bounded.pcap"),"icmp6"])
    time.sleep(.5)
    packet=sc.Ether(src="02:aa:bb:cc:dd:ef",dst="33:33:00:00:00:01")/sc.IPv6(
        src="fe80::dead:beef",dst="ff02::1",hlim=255)/sc.ICMPv6ND_RA(routerlifetime=60)
    count=a.pps*a.seconds; delay=1/a.pps; start=time.monotonic()
    for _ in range(count):
        sc.sendp(packet,iface="ld-sh",verbose=False);time.sleep(delay)
    elapsed=time.monotonic()-start
    cap.terminate();cap.wait()
    result={"configured_pps":a.pps,"duration_limit_seconds":a.seconds,
            "frames_sent":count,"elapsed_seconds":round(elapsed,3),
            "claim":"bounded packet-processing observation only; no service-exhaustion claim"}
    (out/"measurement.json").write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2));print(f"PCAP: {out/'ra-bounded.pcap'}")
    print("Cleanup: sudo python3 ra_bounded_load.py --cleanup")


if __name__=="__main__":main()
