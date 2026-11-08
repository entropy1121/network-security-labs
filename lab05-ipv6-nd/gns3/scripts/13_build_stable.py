#!/usr/bin/env python3
"""Build and verify a functional GNS3 IPv6 L2 VLAN baseline in a NEW project.

Matches the user-confirmed WSL2/GNS3 2.2.61 environment. Does NOT modify the
Huawei project, prior control project, Windows/WSL host networking, or disk images.
This is not a Huawei CE12800 simulation. The built-in GNS3 Ethernet Switch is L2.
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
warnings.filterwarnings("ignore", category=DeprecationWarning)
import telnetlib
import requests

ROOT = Path.home() / 'network-security/Lab05_GNS3_Huawei_AutoKit'
EVID = ROOT / 'evidence'
GNS3_CFG = Path.home() / '.config/GNS3/2.2/gns3_server.conf'
ORIGINAL = ROOT / 'lab05_gns3_state.json'
BASE = 'http://127.0.0.1:3080/v2'
NAME = 'Lab05_NDP_Stable_L2'
STAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
REPORT = EVID / f'13_stable_gns3_{STAMP}.json'
TRANSCRIPT = EVID / f'13_stable_gns3_{STAMP}.txt'


def log(message):
    message = str(message)
    print(message, flush=True)
    with TRANSCRIPT.open('a', encoding='utf8') as f:
        f.write(message + '\n')


def api(sess, method, route, data=None):
    res = sess.request(method, f'{BASE}/{route.lstrip("/")}', json=data, timeout=35)
    if not res.ok:
        raise RuntimeError(f'{method} {route}: HTTP {res.status_code} {res.text[:500]}')
    return res.json() if res.content else {}


def session():
    sess = requests.Session()
    sess.trust_env = False
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(GNS3_CFG)
    if cfg.has_option('Server', 'user') and cfg.has_option('Server', 'password'):
        sess.auth = (cfg.get('Server','user'),cfg.get('Server','password'))
    ver = api(sess, 'GET', 'version').get('version','')
    if not ver.startswith('2.2.'):
        raise RuntimeError(f'GNS3 Server 2.2 expected, got {ver}')
    log(f'GNS3={ver}')
    return sess


class VPCS:
    def __init__(self, name, port):
        self.name=name
        self.tn=telnetlib.Telnet('127.0.0.1', int(port), timeout=10)
        self.drain(0.3)
        self.tn.write(b'\r\n')
        self.read_prompt(8, require_echo=False)
        self.drain(0.2)

    def drain(self, t):
        until=time.monotonic()+t
        while time.monotonic()<until:
            try: self.tn.read_very_eager()
            except EOFError: break
            time.sleep(0.04)

    def read_prompt(self, timeout, require_echo=True, cmd=''):
        buf=bytearray(); start=time.monotonic(); ready_at=None
        while time.monotonic()-start<timeout:
            try: part=self.tn.read_very_eager()
            except EOFError as e: raise RuntimeError(f'{self.name} console closed') from e
            if part:
                buf.extend(part); ready_at=None
                out=buf.decode('utf8','replace').replace('\r','')
                if (not require_echo or cmd in out) and re.search(r'(?m)^VPCS>\s*$',out.rstrip()):
                    ready_at=time.monotonic()
            elif ready_at is not None and time.monotonic()-ready_at>=0.18:
                return buf.decode('utf8','replace').replace('\r','')
            time.sleep(0.04)
        raise RuntimeError(f'{self.name}: console timeout after {cmd!r}: {buf[-700:]!r}')

    def cmd(self, cmd, timeout=18):
        self.drain(0.12)
        self.tn.write(cmd.encode('ascii')+b'\r\n')
        out=self.read_prompt(timeout, require_echo=True, cmd=cmd)
        log(f'[{self.name}] $ {cmd}\n{out.strip()}')
        return out

    def close(self): self.tn.close()


def pc_port(n, mode, vlan):
    return {'name':f'Ethernet{n}','port_number':n,'type':mode,'vlan':vlan}


def create_node(sess, pid, name, kind, x, y, properties=None):
    payload={'name':name,'node_type':kind,'compute_id':'local','x':x,'y':y}
    if properties is not None: payload['properties']=properties
    node=api(sess,'POST',f'projects/{pid}/nodes',payload)
    log(f'[NODE] {name}: {node["node_id"]}')
    return node


def link(sess, pid, a, pa, b, pb):
    result=api(sess,'POST',f'projects/{pid}/links',{'nodes':[
        {'node_id':a['node_id'],'adapter_number':0,'port_number':pa},
        {'node_id':b['node_id'],'adapter_number':0,'port_number':pb},
    ]})
    log(f'[LINK] {a["name"]}:Eth{pa} -- {b["name"]}:Eth{pb}')
    return result


def count_vpcs_replies(txt, dest):
    # VPCS prints IPv6 as '2000::2 icmp6_seq=1 ttl=64 ...' (no 'bytes from').
    # IPv4 prints '84 bytes from 192.0.2.12 icmp_seq=1 ttl=64 ...'.
    regex=re.compile(r'^\s*'+re.escape(dest)+r'\s+icmp6_seq=\d+\s+ttl=\d+\b',re.I)
    return len([line for line in txt.splitlines() if regex.search(line)])


def configured_ipv6(txt, address):
    return bool(re.search(r'GLOBAL\s+SCOPE\s*:\s*'+re.escape(address)+r'/64\b',txt,re.I))


def run_capture(sess,pid,node_id):
    links=api(sess,'GET',f'projects/{pid}/links')
    candidates=[l for l in links if any(n.get('node_id')==node_id for n in l.get('nodes',[]))]
    if len(candidates)!=1: raise RuntimeError(f'{node_id}: expected one attached link, got {len(candidates)}')
    lid=candidates[0]['link_id']
    info=api(sess,'GET',f'projects/{pid}/links/{lid}')
    if info.get('capturing'): raise RuntimeError(f'Link {lid} capture already running')
    target=f'Lab05_stable_{STAMP}_{node_id[:8]}.pcap'
    result=api(sess,'POST',f'projects/{pid}/links/{lid}/start_capture',
               {'data_link_type':'DLT_EN10MB','capture_file_name':target})
    path=result.get('capture_file_path')
    log(f'[CAPTURE START] {path}')
    return lid,path


def decode_pcap(path):
    if not path or not Path(path).is_file(): return {'path':path,'error':'PCAP file not found'}
    proc=subprocess.run(['tcpdump','-nn','-r',str(path),'icmp6'],capture_output=True,text=True,timeout=30)
    lines=proc.stdout.splitlines()
    return {'path':str(path),'icmp6_frames':len(lines),
            'ns':sum('neighbor solicitation' in x for x in lines),
            'na':sum('neighbor advertisement' in x for x in lines),
            'echo_reply':sum('echo reply' in x for x in lines),
            'sample':lines[:14], 'tcpdump_error':proc.stderr[-250:] if proc.returncode else ''}


def main():
    if not ORIGINAL.is_file(): raise RuntimeError('Original Lab05 Huawei state file absent: refusing to guess project')
    old=json.loads(ORIGINAL.read_text())
    if old.get('project_id')!='79e4f583-9057-4401-a743-20e52462585c':
        raise RuntimeError('Huawei project ID mismatch: stop to preserve original experiments')
    EVID.mkdir(parents=True,exist_ok=True)
    sess=session()
    original=api(sess,'GET',f'projects/{old["project_id"]}')
    if original.get('name')!='Lab05_NDP_Huawei_Auto':
        raise RuntimeError('Huawei project name does not match expected: refusing')
    log(f'[PRESERVE] Huawei CE12800 project {original["project_id"]}')
    if any(p['name']==NAME for p in api(sess,'GET','projects')):
        raise RuntimeError(f'{NAME} already exists: refusing to create duplicate or edit it')
    project=api(sess,'POST','projects',{'name':NAME,'auto_close':False})
    pid=project['project_id']
    log(f'[CREATE] {NAME} {pid}')

    # SWA: trunk Eth0; PC1+PC2 access VLAN 100; available Eth3 access VLAN 200.
    # SWB: trunk Eth0; PC3+PC4 access VLAN 200; available Eth3 access VLAN 100.
    aports=[pc_port(0,'dot1q',1),pc_port(1,'access',100),pc_port(2,'access',100),pc_port(3,'access',200)]
    bports=[pc_port(0,'dot1q',1),pc_port(1,'access',200),pc_port(2,'access',200),pc_port(3,'access',100)]
    a=create_node(sess,pid,'SWA-L2-VLAN100-200','ethernet_switch',-210,-20,{'ports_mapping':aports})
    b=create_node(sess,pid,'SWB-L2-VLAN100-200','ethernet_switch',210,-20,{'ports_mapping':bports})
    pcs={
        'PC1':create_node(sess,pid,'PC1','vpcs',-430,210),
        'PC2':create_node(sess,pid,'PC2','vpcs',-170,220),
        'PC3':create_node(sess,pid,'PC3','vpcs',170,220),
        'PC4':create_node(sess,pid,'PC4','vpcs',430,210),
    }
    link(sess,pid,a,0,b,0)
    link(sess,pid,pcs['PC1'],0,a,1)
    link(sess,pid,pcs['PC2'],0,a,2)
    link(sess,pid,pcs['PC3'],0,b,1)
    link(sess,pid,pcs['PC4'],0,b,2)
    for n in pcs.values():
        api(sess,'POST',f'projects/{pid}/nodes/{n["node_id"]}/start',{})
    time.sleep(1.2)
    latest={n['name']:n for n in api(sess,'GET',f'projects/{pid}/nodes')}
    clients={}
    captures=[]
    results={}
    decode=[]
    try:
        for name in ('PC1','PC2','PC3','PC4'):
            n=latest[name]
            if n.get('status')!='started' or not n.get('console'):
                raise RuntimeError(f'{name} missing console/running: {n.get("status")} {n.get("console")}')
            clients[name]=VPCS(name,n['console'])
        addresses={'PC1':'2000::1','PC2':'2000::2','PC3':'3000::3','PC4':'3000::4'}
        for name,addr in addresses.items():
            pc=clients[name]
            pc.cmd(f'ip {addr}/64')
            current=pc.cmd('show ipv6')
            if not configured_ipv6(current,addr):
                raise RuntimeError(f'{name} IPv6 config not accepted: {addr}')
        for name in ('PC1','PC3'):
            lid,path=run_capture(sess,pid,pcs[name]['node_id'])
            captures.append((lid,path))
        for src,dst,addr in [('PC1','PC2','2000::2'),('PC2','PC1','2000::1'),
                             ('PC3','PC4','3000::4'),('PC4','PC3','3000::3')]:
            out=clients[src].cmd(f'ping {addr} -c 3',timeout=26)
            count=count_vpcs_replies(out,addr)
            results[f'{src}->{dst}']={'replies':count,'sent':3,'pass':count==3}
            log(f'[PING {"PASS" if count==3 else "FAIL"}] {src}->{dst} {count}/3')
    finally:
        for lid,path in captures:
            try:
                stopped=api(sess,'POST',f'projects/{pid}/links/{lid}/stop_capture',{})
                final=stopped.get('capture_file_path') or path
                data=decode_pcap(final)
                decode.append(data)
                log(f'[PCAP] NS={data.get("ns")} NA={data.get("na")} Reply={data.get("echo_reply")} file={final}')
                for line in data.get('sample',[]): log(f'  {line}')
            except Exception as e: log(f'[CAPTURE WARN] {type(e).__name__}: {e}')
        for client in clients.values(): client.close()
    report={'project_id':pid,'name':NAME,'huawei_original_project':original['project_id'],
            'platform':'GNS3 built-in Ethernet Switch L2, not Huawei CE12800 dataplane',
            'config':{'SWA_Eth0':'dot1q native VLAN1','SWA_Eth1-2':'access VLAN100',
                      'SWB_Eth0':'dot1q native VLAN1','SWB_Eth1-2':'access VLAN200',
                      'PC1':'2000::1/64','PC2':'2000::2/64','PC3':'3000::3/64','PC4':'3000::4/64'},
            'results':results, 'pcaps':decode,'complete':len(results)==4 and all(v['pass'] for v in results.values()),
            'limitations':'This verifies host NDP and per-VLAN L2 paths; with current four PCs no inter-switch VLAN user-traffic test is included. The built-in switches have no Huawei VLANIF or IPv6 neighbor CLI.'}
    REPORT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    log(f'[REPORT] {REPORT}')
    log(f'[PROJECT] {NAME} id={pid}')
    log('[PRESERVED] Huawei and control projects untouched')
    log('RESULT='+('GNS3_L2_BASELINE_PASS' if report['complete'] else 'GNS3_L2_BASELINE_INCOMPLETE'))
    if not report['complete']: sys.exit(2)


if __name__=='__main__':
    try: main()
    except Exception as exc:
        log(f'[STOP] {type(exc).__name__}: {exc}')
        log('[NOTE] An incomplete new L2 project may remain for inspection. No auto-delete.')
        sys.exit(1)