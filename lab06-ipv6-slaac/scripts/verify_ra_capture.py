#!/usr/bin/env python3
"""Inspect existing IPv6 RA captures and compare saved client route snapshots."""

import argparse
import ipaddress
import json
import re
import struct
import sys
from collections import Counter
from pathlib import Path

ND_TYPES = {133: "RS", 134: "RA", 135: "NS"}
PCAP_ENDIAN = {
    bytes.fromhex(magic): endian
    for magic, endian in [
        ("a1b2c3d4", ">"), ("d4c3b2a1", "<"),
        ("a1b23c4d", ">"), ("4d3cb2a1", "<"),
    ]
}


def inspect_capture(path):
    counts = {"NS": 0, "RS": 0, "RA": 0}
    ra_sources = Counter()
    first_ra_ns = last_ra_ns = None

    with open(path, "rb") as capture:
        header = capture.read(24)
        endian = PCAP_ENDIAN.get(header[:4])
        if len(header) != 24 or endian is None:
            raise ValueError("Expected a classic PCAP file")
        snaplen, linktype = struct.unpack_from(endian + "II", header, 16)
        if linktype & 0xFFFF != 1:
            raise ValueError("Expected an Ethernet capture")
        fraction_to_ns = 1 if header[:4].hex() in {"a1b23c4d", "4d3cb2a1"} else 1000

        while packet_header := capture.read(16):
            if len(packet_header) != 16:
                raise ValueError("Truncated PCAP packet header")
            seconds, fraction, captured_size, _ = struct.unpack(endian + "IIII", packet_header)
            if not 0 < captured_size <= min(snaplen, 16 * 1024 * 1024):
                raise ValueError("Invalid captured packet length")
            frame = capture.read(captured_size)
            if len(frame) != captured_size:
                raise ValueError("Truncated PCAP packet")

            # The lab captures untagged Ethernet with ICMPv6 directly after IPv6.
            if len(frame) < 58 or frame[12:14] != b"\x86\xdd":
                continue
            if frame[14] >> 4 != 6 or frame[20] != 58:
                continue
            message = ND_TYPES.get(frame[54])
            if message is not None:
                counts[message] += 1
            if message == "RA":
                ra_sources[str(ipaddress.IPv6Address(frame[22:38]))] += 1
                timestamp_ns = seconds * 1_000_000_000 + fraction * fraction_to_ns
                if first_ra_ns is None:
                    first_ra_ns = last_ra_ns = timestamp_ns
                else:
                    first_ra_ns = min(first_ra_ns, timestamp_ns)
                    last_ra_ns = max(last_ra_ns, timestamp_ns)

    ra_span = (last_ra_ns - first_ra_ns) / 1e9 if first_ra_ns is not None else None
    return {
        **counts,
        "ra_sources": dict(ra_sources),
        "ra_first_to_last_seconds": ra_span,
        "ra_per_second_between_first_and_last": round((counts["RA"] - 1) / ra_span, 3)
        if ra_span else None,
    }


def read_routes(path):
    """Read the next hops recorded by ip -6 route show default and route get."""
    default_hops = {}
    selected_hops = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        default = re.match(r"^default via (\S+).*?\bpref (\S+)", line.strip())
        if default:
            hop, preference = default.groups()
            default_hops[hop] = preference
            continue
        default = re.match(r"^default via (\S+)", line.strip())
        if default:
            default_hops[default[1]] = None
            continue
        route_get = re.match(r"^(\S+) from \S+ via (\S+)", line.strip())
        if route_get:
            dest, hop = route_get.groups()
            selected_hops[dest] = hop
    return {"default_next_hops": default_hops, "selected_next_hop_by_destination": selected_hops}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pcap", nargs="+")
    parser.add_argument("--routes-before", type=Path, help="Saved client route output before the change")
    parser.add_argument("--routes-after", type=Path, help="Saved client route output after the change")
    args = parser.parse_args()
    if (args.routes_before is None) != (args.routes_after is None):
        parser.error("--routes-before and --routes-after must be supplied together")

    exit_code = 0
    for path in args.pcap:
        try:
            result = inspect_capture(path)
        except (OSError, ValueError) as exc:
            print(f"{path}: {exc}", file=sys.stderr)
            exit_code = 2
            continue
        print(json.dumps({"file": path, **result}))
        if result["RA"] == 0:
            exit_code = max(exit_code, 1)
    if args.routes_before is not None:
        try:
            before = read_routes(args.routes_before)
            after = read_routes(args.routes_after)
        except (OSError, UnicodeError) as exc:
            print(f"Route snapshot: {exc}", file=sys.stderr)
            return 2
        route_changes = {}
        before_selected = before["selected_next_hop_by_destination"]
        after_selected = after["selected_next_hop_by_destination"]
        for dest in sorted(before_selected.keys() & after_selected.keys()):
            if before_selected[dest] != after_selected[dest]:
                route_changes[dest] = {"before": before_selected[dest], "after": after_selected[dest]}
        print(json.dumps({"routes_before": before, "routes_after": after,
                          "observed_next_hop_changes": route_changes}))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
