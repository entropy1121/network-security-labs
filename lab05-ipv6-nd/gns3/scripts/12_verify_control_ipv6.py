#!/usr/bin/env python3
"""Recheck IPv6 on the EXISTING Lab05_L2_Control_Check project.

No project creation, no Huawei actions, no host-network configuration changes.
Adjusts IPv6 addresses only if missing on the two disposable control VPCS.
Starts/stops GNS3 capture only on control-project links.
"""
from __future__ import annotations
import configparser
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)
import telnetlib
import requests

ROOT=Path.home()/'network-security/Lab05_GNS3_Huawei_AutoKit'
EVID=ROOT/'evidence'
STATE=ROOT/'lab05_gns3_state.json'
CFG=Path.home()/'.config/GNS3/2.2/gns3_server.conf'
BASE='http://127.0.0.1:3080/v2'
CONTROL_NAME='Lab05_L2_Control_Check'
STAMP=datetime.now().strftime('%Y%m%d_%H%M%S')
TRANSCRIPT=EVID/f'12_control_ipv6_{STAMP}.log'


def log(s):
    print(s, flush=True)
    with TRANSCRIPT.open('a',encoding='utf-8') as f: f.write(s+'\n')


def api(sess, method, route, data=None):
    res=sess.request(method,f'{BASE}/{route.lstrip("/")}',json=data,timeout=25)
    if not res.ok: raise RuntimeError(f'GNS3 {method} {route}: HTTP {res.status_code} {res.text[:500]}')
    return res.json() if res.content else {}


class PC:
    def __init__(self,name,port):
        self.name=name; self.tn=telnetlib.Telnet('127.0.0.1',int(port),timeout=10)
        self._drain(0.3)
        self.tn.write(b'\r\n')
        startup=self._read_to_prompt(10,require_echo=False)
        if 'VPCS>' not in startup: raise RuntimeError(f'{name}: not a VPCS console, got {startup[-300:]!r}')
        self._drain(0.35)

    def _drain(self,span):
        limit=time.monotonic()+span
        while time.monotonic()<limit:
            try: self.tn.read_very_eager()
            except EOFError: break
            time.sleep(0.05)

    def _read_to_prompt(self,timeout,require_echo=True,cmd=''):
        buf=bytearray(); start=time.monotonic(); prompt_at=None
        while time.monotonic()-start<timeout:
            try: frag=self.tn.read_very_eager()
            except EOFError: raise RuntimeError(f'{self.name}: console disconnected')
            if frag:
                buf.extend(frag); prompt_at=None
                out=buf.decode('utf8','replace').replace('\r','')
                # Allow LF before prompt, but demand echoed command to defeat stale prompts.
                echoed=(not require_echo or cmd in out)
                if echoed and re.search(r'(?m)^VPCS>\s*$',out.rstrip()): prompt_at=time.monotonic()
            elif prompt_at is not None and time.monotonic()-prompt_at>0.20:
                return buf.decode('utf8','replace').replace('\r','')
            time.sleep(0.04)
        out=buf.decode('utf8','replace').replace('\r','')
        raise RuntimeError(f'{self.name}: incomplete result for {cmd!r}: {out[-600:]!r}')

    def cmd(self,command,timeout=15):
        self._drain(0.15)
        self.tn.write(command.encode('ascii')+b'\r\n')
        out=self._read_to_prompt(timeout,True,command)
        log(f'[{self.name} CMD] {command}\n{out.strip()}')
        return out

    def close(self): self.tn.close()


def is_up(output,addr):
    return bool(re.search(r'GLOBAL\s+SCOPE\s*:\s*'+re.escape(addr)+r'/64\b',output,re.I))


def ping_replies(output,dest):
    return len(re.findall(r'(?m)^\s*\d+ bytes from\s+'+re.escape(dest)+r'\b',output,re.I))


def main():
    if not STATE.is_file(): raise RuntimeError('Lab05 original state missing; refusing')
    saved=json.loads(STATE.read_text())
    original_id=saved.get('project_id')
    EVID.mkdir(parents=True,exist_ok=True)
    s=requests.Session();s.trust_env=False
    cfg=configparser.ConfigParser(interpolation=None);cfg.read(CFG)
    if cfg.has_option('Server','user') and cfg.has_option('Server','password'):
        s.auth=(cfg.get('Server','user'),cfg.get('Server','password'))
    original=api(s,'GET',f'projects/{original_id}')
    if original.get('name')!='Lab05_NDP_Huawei_Auto':
        raise RuntimeError('Original project does not match saved Lab05; refusing')
    projects=[p for p in api(s,'GET','projects') if p.get('name')==CONTROL_NAME]
    if len(projects)!=1: raise RuntimeError(f'Expected exactly one control project; got {len(projects)}')
    pid=projects[0]['project_id']
    log(f'[PRESERVE] Huawei={original_id}, CONTROL={pid}; no project creation')
    nodes={n['name']:n for n in api(s,'GET',f'projects/{pid}/nodes')}
    for name in ('Control-PC-A','Control-PC-B'):
        if name not in nodes or nodes[name].get('status')!='started':
            raise RuntimeError(f'{name} missing/not running; no automatic project restart')
    pcs={name:PC(name,nodes[name]['console']) for name in ('Control-PC-A','Control-PC-B')}
    captures=[]
    try:
        a=pcs['Control-PC-A']; b=pcs['Control-PC-B']
        for pc,addr in [(a,'2000::11'),(b,'2000::12')]:
            before=pc.cmd('show ipv6')
            if not is_up(before,addr):
                log(f'[REPAIR CONTROL ONLY] {pc.name}: expected {addr}/64 not seen')
                pc.cmd(f'ip {addr}/64')
                after=pc.cmd('show ipv6')
                if not is_up(after,addr): raise RuntimeError(f'{pc.name}: failed to set {addr}/64')
            else:
                log(f'[ADDRESS CONFIRMED] {pc.name} {addr}/64')
        links=api(s,'GET',f'projects/{pid}/links')
        for name in ('Control-PC-A','Control-PC-B'):
            nid=nodes[name]['node_id']
            candidates=[link for link in links if any(item['node_id']==nid for item in link.get('nodes',[]))]
            if len(candidates)!=1: raise RuntimeError(f'{name}: expected one link, got {len(candidates)}')
            link_id=candidates[0]['link_id']
            info=api(s,'GET',f'projects/{pid}/links/{link_id}')
            if info.get('capturing'):
                raise RuntimeError(f'{name}: capture already running on link; will not override')
            filename=f'Lab05_control_ipv6_{STAMP}_{name[-1].lower()}.pcap'
            capture=api(s,'POST',f'projects/{pid}/links/{link_id}/start_capture',
                        {'data_link_type':'DLT_EN10MB','capture_file_name':filename})
            captures.append((name,link_id,capture.get('capture_file_path')))
            log(f'[CAPTURE START] {name}: {capture.get("capture_file_path")}')
        log('===== IPV6 A -> B =====')
        out_ab=a.cmd('ping 2000::12 -c 3',timeout=25)
        log('===== IPV6 B -> A =====')
        out_ba=b.cmd('ping 2000::11 -c 3',timeout=25)
        # Confirm IPv4 result still valid without changing settings.
        log('===== IPV4 A -> B =====')
        out_v4=a.cmd('ping 192.0.2.12 -c 3',timeout=25)
        # A later show catches whether v6 config silently disappeared or changed.
        a.cmd('show ipv6');b.cmd('show ipv6')
        for pc in (a,b):
            pc.cmd('show neighbor')
        counts={'IPv6 A->B':ping_replies(out_ab,'2000::12'),
                'IPv6 B->A':ping_replies(out_ba,'2000::11'),
                'IPv4 A->B':ping_replies(out_v4,'192.0.2.12')}
        log('===== VERIFIED REPLIES (of 3) =====')
        for title,n in counts.items(): log(f'{title}: {n}/3')
    finally:
        for name,lid,path in captures:
            try:
                stopped=api(s,'POST',f'projects/{pid}/links/{lid}/stop_capture',{})
                path=stopped.get('capture_file_path') or path
                log(f'[CAPTURE STOP] {name}: {path}')
                if path and Path(path).is_file():
                    proc=subprocess.run(['tcpdump','-nn','-e','-r',path,'icmp6 or arp'],
                                        capture_output=True,text=True,timeout=30)
                    lines=proc.stdout.splitlines()
                    log(f'[PCAP DECODE] {name}: {len(lines)} matching frames')
                    for line in lines[:45]: log(line)
            except Exception as exc:
                log(f'[CAPTURE WARNING] {name}: {exc}')
        for pc in pcs.values():pc.close()
        log(f'[TRANSCRIPT] {TRANSCRIPT}')
        log('[PRESERVED] Original Huawei project was never modified')


if __name__=='__main__':
    try: main()
    except Exception as e:
        print(f'[STOP] {type(e).__name__}: {e}',file=sys.stderr)
        sys.exit(1)