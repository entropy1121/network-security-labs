#!/usr/bin/env python3
"""Controlled A/B test: two NEW VPCS through GNS3 built-in Ethernet Switch.

Do not edit or restart the existing Lab05 Huawei project. If this control passes
while Huawei L2 traffic fails, evidence narrows issue to Huawei-specific path.
Use Ubuntu 24.04 /usr/bin/python3 (telnetlib is still present in Python 3.12).
"""
from __future__ import annotations

import configparser
from datetime import datetime
import json
from pathlib import Path
import re
import sys
import time
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)
import telnetlib
import requests

ROOT = Path.home() / 'network-security' / 'Lab05_GNS3_Huawei_AutoKit'
EVID = ROOT / 'evidence'
STATE = ROOT / 'lab05_gns3_state.json'
CONFIG = Path.home() / '.config/GNS3/2.2/gns3_server.conf'
BASE = 'http://127.0.0.1:3080/v2'
PROJECT_NAME = 'Lab05_L2_Control_Check'
TIMEOUT = 20


def say(s):
    print(s, flush=True)


def req(s, method, route, data=None):
    r = s.request(method, f'{BASE}/{route.lstrip("/")}', json=data, timeout=TIMEOUT)
    if not r.ok:
        raise RuntimeError(f'{method} {route}: HTTP {r.status_code} {r.text[:700]}')
    return r.json() if r.content else {}


def console(port, cmd, wait=30):
    with telnetlib.Telnet('127.0.0.1', int(port), timeout=8) as tn:
        tn.write(b'\r\n')
        greeting = tn.read_until(b'VPCS>', timeout=8)
        if b'VPCS>' not in greeting:
            raise RuntimeError(f'Expected VPCS prompt on port {port}; got {greeting[-300:]!r}')
        tn.write(cmd.encode('ascii') + b'\r\n')
        reply = tn.read_until(b'VPCS>', timeout=wait)
        if b'VPCS>' not in reply:
            raise RuntimeError(f'VPCS command did not return prompt: {cmd!r}; last={reply[-500:]!r}')
        return reply.decode('utf8','replace').replace('\r','')


def create(s, pid, data):
    return req(s,'POST',f'projects/{pid}/nodes',data)


def link(s, pid, pc, sw, port):
    payload = {'nodes':[
        {'node_id':pc['node_id'],'adapter_number':0,'port_number':0},
        {'node_id':sw['node_id'],'adapter_number':0,'port_number':port},
    ]}
    return req(s,'POST',f'projects/{pid}/links',payload)


def main():
    if not STATE.is_file():
        raise RuntimeError('Missing original Lab05 state; refusing unrelated GNS3 environment')
    saved=json.loads(STATE.read_text())
    if saved.get('project_id')!='79e4f583-9057-4401-a743-20e52462585c':
        raise RuntimeError('Original Lab05 project ID does not match this session; refusing')
    EVID.mkdir(exist_ok=True)
    s=requests.Session(); s.trust_env=False
    cfg=configparser.ConfigParser(interpolation=None); cfg.read(CONFIG)
    if cfg.has_option('Server','user') and cfg.has_option('Server','password'):
        s.auth=(cfg.get('Server','user'),cfg.get('Server','password'))
    version=req(s,'GET','version')
    say(f'[GNS3] {version.get("version")}')
    original=req(s,'GET',f'projects/{saved["project_id"]}')
    say(f'[PRESERVE] Original project: {original.get("name")} {original.get("project_id")}')
    if any(p['name']==PROJECT_NAME for p in req(s,'GET','projects')):
        raise RuntimeError(f'{PROJECT_NAME} already exists. Refusing duplicate; original Lab05 untouched.')
    new=req(s,'POST','projects',{'name':PROJECT_NAME,'auto_close':False})
    pid=new['project_id']; say(f'[CONTROL PROJECT] {PROJECT_NAME} {pid}')
    # Only new project gets nodes; no modifications to original CE12800 nodes or links.
    pmap=[{'name':f'Ethernet{i}','port_number':i,'type':'access','vlan':100} for i in range(4)]
    sw=create(s,pid,{'name':'GNS3-L2-Control','node_type':'ethernet_switch','compute_id':'local',
                    'x':0,'y':-35,'properties':{'ports_mapping':pmap}})
    a=create(s,pid,{'name':'Control-PC-A','node_type':'vpcs','compute_id':'local','x':-250,'y':180})
    b=create(s,pid,{'name':'Control-PC-B','node_type':'vpcs','compute_id':'local','x':250,'y':180})
    la=link(s,pid,a,sw,0); lb=link(s,pid,b,sw,1)
    say('[LINKS] A -- GNS3 Ethernet Switch VLAN100 -- B')
    for obj in (a,b):
        req(s,'POST',f'projects/{pid}/nodes/{obj["node_id"]}/start',{})
    time.sleep(2)
    latest={n['name']:n for n in req(s,'GET',f'projects/{pid}/nodes')}
    for name in ('Control-PC-A','Control-PC-B'):
        if latest[name]['status']!='started':
            raise RuntimeError(f'{name} status={latest[name]["status"]}, expected started')
    pa=latest['Control-PC-A']['console']; pb=latest['Control-PC-B']['console']
    say('[CONFIG A] '+repr(console(pa,'ip 2000::11/64')[-170:]))
    say('[CONFIG B] '+repr(console(pb,'ip 2000::12/64')[-170:]))
    # IPv6 ping is the required comparable test; use PCAP to ground true ingress/egress.
    result=console(pa,'ping 2000::12 -c 3',wait=35)
    say('===== CONTROL IPv6 PING A -> B =====')
    say(result.strip())
    reverse=console(pb,'ping 2000::11 -c 3',wait=35)
    say('===== CONTROL IPv6 PING B -> A =====')
    say(reverse.strip())
    ping_ok=any('ttl=' in ln.lower() for ln in result.splitlines())
    reverse_ok=any('ttl=' in ln.lower() for ln in reverse.splitlines())
    # IPv4 gives a protocol-independent cross-check.
    console(pa,'ip 192.0.2.11/24')
    console(pb,'ip 192.0.2.12/24')
    result4=console(pa,'ping 192.0.2.12 -c 3',wait=35)
    say('===== CONTROL IPv4 PING A -> B =====')
    say(result4.strip())
    ping4_ok=any('ttl=' in ln.lower() for ln in result4.splitlines())
    flags={'ipv6_a_to_b':ping_ok,'ipv6_b_to_a':reverse_ok,'ipv4_a_to_b':ping4_ok}
    say('===== RESULTS =====')
    for k,v in flags.items(): say(f'{k}={"PASS" if v else "FAIL"}')
    record={'control_project_id':pid,'original_lab05_project_id':saved['project_id'],'results':flags,
            'meaning':'Same GNS3 local compute+VPCS; a different L2 device (built-in switch).'}
    (EVID/'11_l2_control_result.json').write_text(json.dumps(record,indent=2)+'\n')
    say('[SAVED] evidence/11_l2_control_result.json')
    say('Original Huawei project unchanged; separate test topology kept as evidence.')
    say('CONTROL='+('PASS' if all(flags.values()) else 'FAIL_OR_PARTIAL'))

if __name__=='__main__':
    try:
        main()
    except Exception as err:
        say(f'[STOP] {type(err).__name__}: {err}')
        say('Original Huawei project was not modified; any new control project is kept for inspection.')
        sys.exit(1)