#!/usr/bin/env python3
"""Count received IPv6 Neighbor Discovery messages in existing capture files."""

import argparse
import json
import sys
from collections import Counter

import ipaddress
import struct

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

    with open(path, "rb") as capture:
        header = capture.read(24)
        endian = PCAP_ENDIAN.get(header[:4])
        if len(header) != 24 or endian is None:
            raise ValueError("Expected a classic PCAP file")
        snaplen, linktype = struct.unpack_from(endian + "II", header, 16)
        if linktype & 0xFFFF != 1:
            raise ValueError("Expected an Ethernet capture")

        while packet_header := capture.read(16):
            if len(packet_header) != 16:
                raise ValueError("Truncated PCAP packet header")
            captured_size = struct.unpack_from(endian + "I", packet_header, 8)[0]
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

    return {**counts, "ra_sources": dict(ra_sources)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pcap", nargs="+")
    args = parser.parse_args()

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
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
