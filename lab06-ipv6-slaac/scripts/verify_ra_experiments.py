#!/usr/bin/env python3
"""Check client-side RA experiment evidence without sending network packets."""

import argparse
import json
import re
from pathlib import Path

from verify_ra_capture import inspect_capture, read_routes


def route_evidence(args):
    baseline = inspect_capture(args.before_pcap) if args.before_pcap is not None else None
    observed = inspect_capture(args.after_pcap)
    before = read_routes(args.before_routes)
    after = read_routes(args.after_routes)

    before_hops = before["default_next_hops"]
    after_hops = after["default_next_hops"]
    before_selected = before["selected_next_hop_by_destination"]
    after_selected = after["selected_next_hop_by_destination"]
    comparable_destinations = before_selected.keys() & after_selected.keys()
    missing = []
    if baseline is None:
        missing.append("No separate baseline capture provided")
    elif not baseline["RA"]:
        missing.append("No RA in baseline capture")
    if not before_hops:
        missing.append("No default route in baseline snapshot")
    if not observed["RA"]:
        missing.append("No RA in follow-up or combined capture")
    if not comparable_destinations:
        missing.append("No route lookup for the same destination in both snapshots")

    return {
        "baseline_capture": baseline,
        "follow_up_or_combined_capture": observed,
        "new_ra_sources": sorted(observed["ra_sources"].keys() - baseline["ra_sources"].keys())
        if baseline is not None else None,
        "default_routes_before": before_hops,
        "default_routes_after": after_hops,
        "next_hop_comparisons": {
            dest: {"before": before_selected[dest], "after": after_selected[dest]}
            for dest in sorted(comparable_destinations)
        },
        "missing_evidence": missing,
    }


def read_ping(path):
    text = path.read_text(encoding="utf-8")
    destination = re.search(r"^PING\s+(.+?)\s+\(", text, re.MULTILINE)
    summary = re.search(r"(\d+) packets transmitted,\s+(\d+) (?:packets )?received", text)
    latency = re.search(r"^rtt min/avg/max/mdev = [\d.]+/([\d.]+)/", text, re.MULTILINE)
    if summary is None:
        return None
    sent, received = map(int, summary.groups())
    return {
        "destination": destination[1] if destination else None,
        "sent": sent,
        "received": received,
        "mean_rtt_ms": float(latency[1]) if latency else None,
    }


def receive_evidence(args):
    capture = inspect_capture(args.pcap)
    missing = []
    if capture["RA"] == 0:
        missing.append("No RA in receiver capture")
    elif capture["ra_per_second_between_first_and_last"] is None:
        missing.append("Rate requires two RA packets with distinct timestamps")

    before_ping = after_ping = None
    if args.before_ping is not None:
        before_ping = read_ping(args.before_ping)
        after_ping = read_ping(args.after_ping)
    if (
        not before_ping or not after_ping or not before_ping["destination"]
        or before_ping["destination"] != after_ping["destination"]
    ):
        missing.append("No comparable before and after ping summaries for the same destination")

    return {
        "receiver_capture": capture,
        "baseline_ping": before_ping,
        "follow_up_ping": after_ping,
        "missing_evidence": missing,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    routes = commands.add_parser("routes", help="Compare RA captures and saved client routes")
    routes.add_argument("after_pcap", type=Path, help="Follow-up or combined client capture")
    routes.add_argument("before_routes", type=Path)
    routes.add_argument("after_routes", type=Path)
    routes.add_argument("--before-pcap", type=Path, help="Separate baseline capture if available")

    receive = commands.add_parser("receive", help="Measure captured RA arrivals and compare ping logs")
    receive.add_argument("pcap", type=Path)
    receive.add_argument("--before-ping", type=Path)
    receive.add_argument("--after-ping", type=Path)
    args = parser.parse_args()
    if args.mode == "receive" and (args.before_ping is None) != (args.after_ping is None):
        parser.error("--before-ping and --after-ping must be supplied together")

    try:
        result = route_evidence(args) if args.mode == "routes" else receive_evidence(args)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"{exc}\n")

    print(json.dumps(result, indent=2))
    return 1 if result["missing_evidence"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
