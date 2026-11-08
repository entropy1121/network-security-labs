#!/usr/bin/env python3
"""Lab05 GNS3 CE12800: temporary IPv4 ARP/unicast discriminator.

Only PC1/PC2 in existing Lab05 project. Preserves the GNS3 topology, Huawei
configuration, and all IPv6 addresses. Requires existing 05_fix_verify.py.
Never overwrites a preexisting IPv4 address. Uses clear ip in finally.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path.home() / 'network-security/Lab05_GNS3_Huawei_AutoKit'
EVIDENCE = ROOT / 'evidence'
LIB = ROOT / 'scripts/05_fix_verify.py'
if not LIB.is_file():
    sys.exit(f'[STOP] Missing existing script: {LIB}')
spec = importlib.util.spec_from_file_location('lab05_existing_console', LIB)
lib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lib)
if not str(lib.state.get('project_name','')).startswith('Lab05_NDP_Huawei_Auto'):
    sys.exit('[STOP] Wrong GNS3 project')
from datetime import datetime
stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
lib.STAMP = 'ipv4check_' + stamp
lib.TRANSCRIPT = EVIDENCE / f'10_ipv4_console_{stamp}.log'
CAP = EVIDENCE / f'10_ipv4_capture_{stamp}.log'
CURRENT = {}
MODIFIED = []
CAP_STARTED = []
CAP_FILES = []


def log(s):
    print(s, flush=True)


def vpcs(name, cmd, seconds=15):
    with lib.console(name) as con:
        return con.cmd(cmd,timeout=seconds,check=False)


def get_ipv4(name):
    out = vpcs(name, 'show ip')
    m = re.search(r'IP/MASK\s*:\s*(\d{1,3}(?:\.\d{1,3}){3}/\d+)',out,re.I)
    if not m:
        raise RuntimeError(f'Cannot parse {name} show ip; no changes made; output: {out[-400:]}')
    return m.group(1)


def clear_modified():
    for name in reversed(MODIFIED):
        try:
            output = vpcs(name,'clear ip')
            now = get_ipv4(name)
            if not now.startswith('0.0.0.0/'):
                log(f'[RESTORE WARNING] {name}: expected no IPv4 but got {now}; output={output[-120:]}')
            else:
                log(f'[RESTORED] {name} IPv4 cleared, original IPv4 was {CURRENT[name]}')
            ipv6 = vpcs(name,'show ipv6')
            expected = '2000::1' if name=='PC1' else '2000::2'
            log(f'[IPV6 {"PRESERVED" if expected in ipv6.lower() else "VERIFY"}] {name}: {expected}')
        except Exception as e:
            log(f'[RESTORE ERROR] {name}: {e}; run VPCS "clear ip" on that PC manually if necessary')


def summarize_capture(path, label):
    if not path:
        log(f'[PCAP] {label}: missing capture path')
        return ''
    p = Path(path)
    if not p.is_file():
        log(f'[PCAP] {label}: file not found: {p}')
        return ''
    result = subprocess.run(['tcpdump','-nn','-e','-r',str(p),'arp or (icmp and ip)'],
            text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=25)
    with CAP.open('a',encoding='utf8') as f:
        f.write(f'\n===== {label}: {p} =====\n{result.stdout}\n')
    lines=[l for l in result.stdout.splitlines() if 'ARP,' in l or 'ICMP' in l]
    log(f'[PCAP] {label}: {len(lines)} ARP/IPv4-ICMP packets')
    for ln in lines[:28]:
        log('  '+ln)
    return result.stdout


def main():
    log('===== LAB05 IPv4 DIAGNOSTIC ONLY: EXISTING PROJECT =====')
    log(f'PROJECT={lib.state["project_name"]} ({lib.state["project_id"]})')
    for name in ('PC1','PC2'):
        CURRENT[name] = get_ipv4(name)
        log(f'[BASELINE] {name} IPv4={CURRENT[name]}')
        if not CURRENT[name].startswith('0.0.0.0/'):
            raise RuntimeError('Nonempty IPv4 config detected; refusing to overwrite any PC address')
    session = None
    try:
        for name, ip in [('PC1','192.0.2.1/24'),('PC2','192.0.2.2/24')]:
            MODIFIED.append(name)
            out = vpcs(name,f'ip {ip}',seconds=20)
            if any(x in out.lower() for x in ('invalid','not changed','error')):
                raise RuntimeError(f'{name} IPv4 assignment error: {out[-600:]}')
            got = get_ipv4(name)
            log(f'[TEMP] {name}: {got}')
            if got != ip:
                raise RuntimeError(f'{name} expected {ip} but got {got}')
        session = lib.api_session()
        for link in ('pc1','pc2'):
            try:
                info = lib.capture_api(session,link,'get')
                if info.get('capturing'):
                    log(f'[CAPTURE SKIP] {link} already being captured; will not stop it')
                    continue
                info = lib.capture_api(session,link,'start')
                CAP_STARTED.append(link)
                log(f'[CAPTURE START] {link}: {info.get("capture_file_path")}')
            except Exception as e:
                log(f'[CAPTURE WARN] {link}: {e}')
        time.sleep(.5)
        for name, target in [('PC1','192.0.2.2'),('PC2','192.0.2.1')]:
            try:
                out = vpcs(name,f'ping {target} -c 3',seconds=18)
                success = re.findall(r'\b\d+\s+bytes from\b|icmp_seq=\d+\s+ttl=',out,re.I)
                log(f'[IPV4 PING {"REPLY" if success else "NO_REPLY"}] {name} -> {target} ({len(success)} matching replies)')
                with CAP.open('a',encoding='utf8') as f:
                    f.write(f'\n===== {name} ping {target} =====\n{out}\n')
                for ln in out.splitlines():
                    if 'icmp_seq' in ln or 'reachable' in ln.lower() or 'timeout' in ln.lower():
                        log('  '+ln.strip())
            except Exception as e:
                log(f'[IPV4 PING ERROR] {name}: {e}')
        for name in ('SWA-Huawei',):
            try:
                with lib.console(name) as con:
                    con.cmd('screen-length 0 temporary',check=False)
                    for cmd in ['display mac-address vlan 100','display interface brief','display port vlan']:
                        out = con.cmd(cmd,timeout=15,check=False)
                        with CAP.open('a',encoding='utf8') as f:
                            f.write(f'\n===== {name}: {cmd} =====\n{out}\n')
                        if cmd=='display mac-address vlan 100':
                            for line in out.splitlines():
                                if '0050-7966-680' in line:
                                    log('[MAC] '+line.strip())
            except Exception as e:
                log(f'[SWITCH READONLY WARN] {e}')
    finally:
        if session:
            for link in CAP_STARTED:
                try:
                    info=lib.capture_api(session,link,'stop')
                    path=info.get('capture_file_path')
                    CAP_FILES.append((link,path))
                    log(f'[CAPTURE STOP] {link}: {path}')
                except Exception as e:
                    log(f'[CAPTURE STOP WARN] {link}: {e}')
        clear_modified()
        for link,path in CAP_FILES:
            try:
                summarize_capture(path,link)
            except Exception as e:
                log(f'[CAPTURE DECODE WARN] {link}: {e}')
    log(f'CONSOLE_LOG={lib.TRANSCRIPT}')
    log(f'CAPTURE_LOG={CAP}')
    log('DONE: No changes to GNS3 topology, Huawei VLANs or IPv6 addresses')

if __name__ == '__main__':
    try:
        main()
    except Exception as err:
        log(f'[STOP] {type(err).__name__}: {err}')
        sys.exit(1)