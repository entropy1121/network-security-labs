#!/usr/bin/env python3
"""Lab05 CE12800 existing-project repair / diagnostic.

Repairs only Lab05 project SWA/SWB access+trunk ports and PC3/PC4 addresses.
Does not create/delete GNS3 projects, change host network, or touch other labs.
Run under WSL Ubuntu system Python 3.12 from the existing AutoKit folder.
"""
from __future__ import annotations
import configparser
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)
try:
    import telnetlib
except ImportError as exc:
    raise SystemExit('Use /usr/bin/python3 on Ubuntu 24.04 (requires telnetlib).') from exc

ROOT = Path.home() / 'network-security/Lab05_GNS3_Huawei_AutoKit'
STATE = ROOT / 'lab05_gns3_state.json'
LOG = ROOT / 'evidence'
API = 'http://127.0.0.1:3080/v2'
CONFIG = Path.home() / '.config/GNS3/2.2/gns3_server.conf'
PROMPT = re.compile(r'(?m)^(?:<[^\r\n<>]{1,60}>|\[[^\r\n\[\]]{1,60}\]|VPCS>)\s*$')
ERROR = re.compile(r'(?i)(?:^|\n)\s*(?:Error:|%\s+(?:Invalid|Error|Unrecognized)|host .*not reachable)')

if not STATE.is_file():
    raise SystemExit('No saved Lab05 project state: ' + str(STATE))
state = json.loads(STATE.read_text())
if not str(state.get('project_name','')).startswith('Lab05_NDP_Huawei_Auto'):
    raise SystemExit('Project mismatch; refusing to operate')
NEEDED = ('SWA-Huawei','SWB-Huawei','PC1','PC2','PC3','PC4')
for n in NEEDED:
    if not isinstance(state.get('nodes',{}).get(n,{}).get('console'),int):
        raise SystemExit(f'Missing saved console for {n}; refusing to operate')
LOG.mkdir(parents=True,exist_ok=True)
STAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
TRANSCRIPT = LOG / f'08_huawei_fix_{STAMP}.log'
PCAP_LOG = LOG / f'08_huawei_capture_{STAMP}.log'
ACTIVITY = []
CAPTURED = []


def record(message):
    print(message,flush=True)
    ACTIVITY.append(message)


class Console:
    def __init__(self, name):
        self.name = name
        self.tn = telnetlib.Telnet('127.0.0.1', state['nodes'][name]['console'], timeout=8)
        self.records = []
        self._collect(timeout=.35, allow_empty=True)
        self.tn.write(b'\r\n')
        self._collect(timeout=6)

    def _collect(self, timeout=15, allow_empty=False):
        buf = bytearray()
        start = time.monotonic()
        seen_prompt = None
        more_last = -1
        while time.monotonic()-start < timeout:
            try:
                part = self.tn.read_very_eager()
            except EOFError as exc:
                raise RuntimeError(f'{self.name}: console closed') from exc
            if part:
                buf.extend(part)
                seen_prompt = None
                # Deal with Huawei paginated output if the pager setting was not accepted.
                last_idx = buf.rfind(b'---- More ----')
                if last_idx != -1 and last_idx != more_last:
                    self.tn.write(b' ')
                    more_last = last_idx
                txt = buf.decode('utf-8','replace').replace('\r','')
                if PROMPT.search(txt.rstrip()):
                    seen_prompt = time.monotonic()
            elif seen_prompt is not None and time.monotonic()-seen_prompt >= .25:
                return bytes(buf).decode('utf-8','replace').replace('\r','')
            time.sleep(.06)
        out = bytes(buf).decode('utf-8','replace').replace('\r','')
        if allow_empty:
            return out
        raise RuntimeError(f'{self.name}: command did not return to prompt within {timeout}s; tail={out[-500:]!r}')

    def cmd(self, command, timeout=12, check=True):
        self.tn.write((command+'\r\n').encode('ascii'))
        try:
            out = self._collect(timeout=timeout)
        except RuntimeError as e:
            self.records.append(f'>>> {command}\n{e}')
            raise
        self.records.append(f'>>> {command}\n{out}\n')
        if check and ERROR.search(out):
            raise RuntimeError(f'{self.name}: CLI error from {command!r}: {out[-440:]}')
        return out

    def close(self):
        try:
            self.tn.close()
        finally:
            with TRANSCRIPT.open('a',encoding='utf-8') as f:
                f.write('\n'+'='*16+' '+self.name+' '+'='*16+'\n')
                f.write('\n'.join(self.records))


@contextmanager
def console(name):
    c = Console(name)
    try:
        yield c
    finally:
        c.close()


def user_view(c):
    output=c.cmd('', check=False)
    if re.search(r'\[[^\]]+\]\s*$',output):
        c.cmd('return')
    # Only Huawei VRP uses this pagination command.
    if c.name.endswith('Huawei'):
        c.cmd('screen-length 0 temporary',check=False)


def config_switch(name, ports):
    record(f'===== REPAIR {name} =====')
    with console(name) as c:
        user_view(c)
        for cmd in ('display vlan 100','display vlan 200','display port vlan'):
            c.cmd(cmd,timeout=12,check=False)
        c.cmd('system-view immediately')
        c.cmd('vlan batch 100 200')
        # Change ONLY ports connected to this lab's nodes according to the original mapping hypothesis.
        c.cmd('interface GE1/0/0')
        for cmd in ('undo shutdown','port link-type trunk','port trunk allow-pass vlan 100 200','quit'):
            c.cmd(cmd)
        for port, vlan in ports:
            c.cmd(f'interface GE1/0/{port}')
            for cmd in ('undo shutdown','port link-type access',f'port default vlan {vlan}','quit'):
                c.cmd(cmd)
        c.cmd('return')
        for cmd in ('display port vlan','display ipv6 interface','display current-configuration interface Vlanif100','display current-configuration interface Vlanif200'):
            c.cmd(cmd,timeout=16,check=False)
        record(f'[CONFIG SENT] {name}; true output saved in {TRANSCRIPT.name}')


def config_pc(name,addr):
    with console(name) as c:
        user_view(c)
        out = c.cmd('show ipv6',timeout=8,check=False)
        if 'VPCS' not in out and 'LINK-LOCAL' not in out:
            raise RuntimeError(f'Cannot confirm VPCS console identity for {name}')
        c.cmd(f'ip {addr}',timeout=12)
        c.cmd('save',timeout=12,check=False)
        out = c.cmd('show ipv6',timeout=12)
        if addr.split('/')[0].lower() not in out.lower():
            raise RuntimeError(f'{name}: new address not confirmed by show ipv6')
    record(f'[PC VERIFIED] {name} -> {addr}')


# GNS3 capture is optional; failure never masks basic configuration outcome.
def api_session():
    import requests
    s=requests.Session()
    s.trust_env=False
    cfg=configparser.ConfigParser(interpolation=None)
    cfg.read(CONFIG)
    if cfg.has_option('Server','user') and cfg.has_option('Server','password'):
        s.auth=(cfg.get('Server','user'),cfg.get('Server','password'))
    return s


def capture_api(s, link_name, op):
    lid=state['links'][link_name]
    url=f"{API}/projects/{state['project_id']}/links/{lid}"
    if op == 'get':
        response=s.get(url,timeout=15)
    elif op == 'start':
        response=s.post(url+'/start_capture',json={'data_link_type':'DLT_EN10MB','capture_file_name':f'Lab05_patch_{STAMP}_{link_name}.pcap'},timeout=25)
    else:
        response=s.post(url+'/stop_capture',json={},timeout=25)
    response.raise_for_status()
    return response.json()


def run_pings():
    tests={
        'PC1': ['ping 2000::2', 'ping 2000::ffff'],
        'PC2': ['ping 2000::1'],
        'PC3': ['ping 3000::4', 'ping 3000::eeee'],
        'PC4': ['ping 3000::3'],
    }
    for name,cmds in tests.items():
        with console(name) as c:
            user_view(c)
            for cmd in cmds:
                try:
                    out = c.cmd(cmd,timeout=23,check=False)
                except Exception as exc:
                    record(f'[INCONCLUSIVE] {name} {cmd}: {exc}')
                    continue
                ok = bool(re.search(r'(?m)(?:\b\d+\s+bytes from\b|\b\d+\s+packets received\b|icmp_seq=\d+)',out,re.I)) and not ('not reachable' in out.lower())
                fail = 'not reachable' in out.lower() or ('100% packet loss' in out.lower())
                status = 'PASS' if ok else 'FAIL' if fail else 'CHECK_LOG'
                record(f'[PING {status}] {name}: {cmd}')


def collect_switch_readonly(name):
    with console(name) as c:
        user_view(c)
        for cmd in ('display interface brief','display port vlan','display vlan 100','display vlan 200',
                    'display ipv6 interface','display ipv6 neighbors','display mac-address'):
            try:
                c.cmd(cmd,timeout=18,check=False)
            except RuntimeError as exc:
                record(f'[VERIFY WARN] {name} {cmd}: {exc}')
                break
    record(f'[VERIFY] {name}: CLI display collected')


def pcap_summary(paths):
    with PCAP_LOG.open('a',encoding='utf-8') as log:
        for label,path in paths:
            p=Path(path)
            if not p.is_file():
                log.write(f'[{label}] capture path missing: {path}\n')
                continue
            args=['tcpdump','-nn','-r',str(p),'icmp6']
            res=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=30)
            log.write(f'\n===== {label}: {path} =====\n{res.stdout}\n')
            count_ns = res.stdout.lower().count('neighbor solicitation')
            count_na = res.stdout.lower().count('neighbor advertisement')
            record(f'[PCAP] {label}: NS={count_ns}, NA={count_na}; {p}')


def main():
    record(f'PROJECT_ID={state["project_id"]}  existing project only')
    record('Do not rerun run_all.sh. No new GNS3 project will be created.')
    record(f'CONSOLE_LOG={TRANSCRIPT}')
    cfg_errors=[]
    try:
        config_switch('SWA-Huawei',[(1,100),(2,100),(3,100)])
        config_switch('SWB-Huawei',[(1,200),(2,200)])
        config_pc('PC3','3000::3/64')
        config_pc('PC4','3000::4/64')
        # PC1 PC2 unchanged from original state, verify their addresses only.
        for name, expected in [('PC1','2000::1'),('PC2','2000::2')]:
            with console(name) as c:
                user_view(c)
                out=c.cmd('show ipv6',check=False)
                record(f'[PC {"OK" if expected in out.lower() else "CHECK"}] {name}: expected {expected}')
    except Exception as exc:
        cfg_errors.append(str(exc))
        record(f'[CONFIGURATION STOPPED] {exc}')

    if not cfg_errors:
        s=None
        try:
            s=api_session()
            for name in ('pc1','pc2','pc3','pc4'):
                info=capture_api(s,name,'get')
                if info.get('capturing'):
                    record(f'[CAPTURE SKIP] {name}: already capturing, leaving unchanged')
                    continue
                result=capture_api(s,name,'start')
                CAPTURED.append(name)
                record(f'[CAPTURE START] {name}: {result.get("capture_file_path")}')
        except Exception as exc:
            record(f'[CAPTURE WARNING] {exc} (pings still run)')

        try:
            run_pings()
        finally:
            found=[]
            if s:
                for name in CAPTURED:
                    try:
                        result=capture_api(s,name,'stop')
                        record(f'[CAPTURE STOP] {name}: {result.get("capture_file_path")}')
                        p=result.get('capture_file_path')
                        if p:
                            found.append((name,p))
                    except Exception as exc:
                        record(f'[CAPTURE STOP WARNING] {name}: {exc}')
            if found:
                try:
                    pcap_summary(found)
                except Exception as exc:
                    record(f'[PCAP DECODE WARNING] {exc}')
        for name in ('SWA-Huawei','SWB-Huawei'):
            try:
                collect_switch_readonly(name)
            except Exception as exc:
                record(f'[VERIFY WARN] {name}: {exc}')

    record(f'CONSOLE_LOG={TRANSCRIPT}')
    record(f'PCAP_LOG={PCAP_LOG}')
    if cfg_errors:
        record('RESULT=PARTIAL_CONFIG; inspect log; do not claim connectivity')
    else:
        record('RESULT=CONFIG_SENT_AND_DIAGNOSTICS_COLLECTED; rely on PING and PCAP evidence')
    # A summary file makes it easy to share a concise tail without printing huge device outputs.
    (LOG / '08_fix_summary.txt').write_text('\n'.join(ACTIVITY)+'\n',encoding='utf-8')
    if cfg_errors:
        sys.exit(2)


if __name__=='__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n[INTERRUPTED] Existing project preserved; check captured files')
        sys.exit(130)