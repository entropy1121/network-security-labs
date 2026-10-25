#!/usr/bin/env python3
"""Bounded, isolated MAC source-address variation for SW2 RouterOS bridge testing."""
import argparse
import socket
import subprocess
import sys
import time

p = argparse.ArgumentParser()
p.add_argument('--phase', choices=['before','after'], required=True)
a = p.parse_args()
ips = subprocess.check_output(['ip','-4','-o','addr','show','dev','eth0'],text=True)
mac = open('/sys/class/net/eth0/address', encoding='ascii').read().strip()
if '192.168.241.139/24' not in ips or mac != '02:33:03:00:00:39':
    sys.exit('STOP: wrong namespace or MAC: refusing to transmit')

# Phase-specific OUI avoids treating previously learned MACs as newly learned.
prefix = '02ac0300' if a.phase == 'before' else '02ac0400'
dest = b'\xff' * 6
ether_type = bytes.fromhex('88b5')
payload = b'GNS3-LAB03-ONLY'.ljust(46,b'\0')
s = socket.socket(socket.AF_PACKET,socket.SOCK_RAW,socket.htons(0x0003))
s.bind(('eth0',0))
t0 = time.monotonic()
for i in range(256):
    src = bytes.fromhex(prefix)+i.to_bytes(2,'big')
    s.send(dest + src + ether_type + payload)
    time.sleep(.004)
s.close()
print(f'PHASE={a.phase} FRAMES_SENT=256 PREFIX={prefix} '
      f'ELAPSED={time.monotonic()-t0:.3f}s')
