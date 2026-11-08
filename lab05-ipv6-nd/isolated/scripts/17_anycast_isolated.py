#!/usr/bin/env python3
"""Lab05 isolated IPv6 anycast routing demonstration (Linux namespace only).

Two independent namespaces host the same IPv6 service address 3888::/128 on lo.
A third namespace chooses the preferred destination by IPv6 host route metric.
Capture both paths, withdraw the preferred route, and demonstrate failover.

This is a routing-level anycast MODEL, not Huawei CE12800 ipv6 ... anycast CLI.
The temporary network namespaces are deleted in finally. No existing namespace,
GNS3 project, host route/firewall, or physical interface is modified.

WSL: sudo /usr/bin/python3 scripts/17_anycast.py
"""
from __future__ import annotations
import getpass
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime

STAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
C, A, B = ('l05ac_client_' + STAMP, 'l05ac_swa_' + STAMP, 'l05ac_swb_' + STAMP)
ANYCAST = '3888::'
NEXT_A = '2001:db8:5:a::2'
NEXT_B = '2001:db8:5:b::2'
USER = os.environ.get('SUDO_USER')
if USER:
    import pwd
    HOME = Path(pwd.getpwnam(USER).pw_dir)
else:
    HOME = Path.home()
EVID = HOME/'network-security/Lab05_GNS3_Huawei_AutoKit/evidence'
PCAPA = EVID/f'17_anycast_{STAMP}_via_SWA.pcap'
PCAPB = EVID/f'17_anycast_{STAMP}_via_SWB.pcap'
REPORT = EVID/f'17_anycast_{STAMP}.json'
CREATED=[]
CAPS=[]
DATA={'experiment':'isolated_linux_routing_anycast_model',
      'disclaimer':'NOT Huawei CE12800 ipv6 anycast command; independent L3 routing model',
      'date_tag':STAMP, 'nodes':{}, 'stages':{}, 'captures':{}, 'cleanup':'not_run'}

def log(s=''):
    print(s,flush=True)

def cmd(*args, must=True, timeout=15):
    p=subprocess.run([str(a) for a in args],capture_output=True,text=True,timeout=timeout)
    line=' '.join(str(a) for a in args)
    if p.returncode!=0 and must:
        raise RuntimeError(f'CMD FAILED ({p.returncode}): {line}\n{p.stdout}\n{p.stderr}')
    return p

def ip(ns, *args):
    return cmd('ip','-n',ns,*args)

def check_ready():
    if os.geteuid()!=0:
        raise RuntimeError('需要 sudo /usr/bin/python3，才能创建隔离 Linux Namespace')
    for exe in ('ip','ping','tcpdump'):
        if not shutil.which(exe):
            raise RuntimeError(f'缺少系统命令 {exe}，未修改任何配置')
    p=cmd('ip','netns','list')
    used={x.split()[0] for x in p.stdout.splitlines() if x.strip()}
    if used.intersection({C,A,B}):
        raise RuntimeError('检测到同名隔离命名空间，拒绝修改或删除它们')
    EVID.mkdir(parents=True,exist_ok=True)

def create_network():
    for ns in (C,A,B):
        cmd('ip','netns','add',ns)
        CREATED.append(ns)
        ip(ns,'link','set','lo','up')
    ip(C,'link','add','ca','type','veth','peer','name','ac')
    ip(C,'link','set','ac','netns',A)
    ip(C,'link','add','cb','type','veth','peer','name','bc')
    ip(C,'link','set','bc','netns',B)
    for ns,dev in ((C,'ca'),(C,'cb'),(A,'ac'),(B,'bc')):
        ip(ns,'link','set',dev,'up')
    addr = ((C,'ca','2001:db8:5:a::1/64'),(A,'ac','2001:db8:5:a::2/64'),
            (C,'cb','2001:db8:5:b::1/64'),(B,'bc','2001:db8:5:b::2/64'),
            (A,'lo','3888::/128'),(B,'lo','3888::/128'))
    for ns,dev,cidr in addr:
        ip(ns,'-6','addr','add',cidr,'dev',dev)
    for ns in (A,B):
        o=ip(ns,'-6','addr','show','dev','lo').stdout
        if '3888::/128' not in o:
            raise RuntimeError(f'{ns} anycast host /128 not present')
        DATA['nodes'][ns]={'service':'3888::/128 on lo', 'address_output':o}
    # Two /128 routes select *one* of two identical service addresses.
    ip(C,'-6','route','add','3888::/128','via',NEXT_A,'dev','ca','metric','10')
    ip(C,'-6','route','add','3888::/128','via',NEXT_B,'dev','cb','metric','20')
    # Await DAD completion on all four point-to-point interface addresses.
    time.sleep(2.0)
    for dst in (NEXT_A,NEXT_B):
        p=cmd('ip','netns','exec',C,'ping','-6','-c','1','-W','2',dst,timeout=6)
        if not (p.returncode==0 and '1 received' in p.stdout):
            raise RuntimeError(f'Link neighbor unavailable for {dst}: {p.stdout}')
    log('[LINKS VERIFIED] both isolated L3 next hops are reachable')
    log('[SERVICE VERIFIED] SWA/SWB namespaces each have 3888::/128 on loopback')

def start_capture():
    for label,dev,output in [('SWA','ca',PCAPA),('SWB','cb',PCAPB)]:
        with open(os.devnull,'w') as null:
            p=subprocess.Popen(['ip','netns','exec',C,'tcpdump','-i',dev,'-U','-n','-s','0',
                                '-w',str(output),'icmp6'],stdout=null,stderr=subprocess.PIPE,text=True)
        CAPS.append((label,p,output))
    time.sleep(0.65)
    for label,p,_ in CAPS:
        if p.poll() is not None:
            raise RuntimeError(f'{label} tcpdump failed: {p.stderr.read()}')

def ping_service(stage, expected, iface):
    route=ip(C,'-6','route','get',ANYCAST).stdout.strip()
    log(f'[{stage} ROUTE] {route}')
    if f'via {expected}' not in route or f'dev {iface}' not in route:
        raise RuntimeError(f'{stage} wrong route: {route}')
    p=cmd('ip','netns','exec',C,'ping','-6','-c','3','-W','2',ANYCAST,timeout=10)
    log(f'[{stage} PING]\n{p.stdout.strip()}')
    m=re.search(r'(\d+) packets transmitted, (\d+) received',p.stdout)
    received=int(m.group(2)) if m else 0
    ok=bool(p.returncode==0 and m and int(m.group(1))==3 and received==3)
    log(f'[{'PASS' if ok else 'FAIL'}] {stage}: {received}/3 via {expected}')
    DATA['stages'][stage]={'route':route,'received':received,'sent':3,'pass':ok,
                           'selected_next_hop':expected,'outgoing_interface':iface}
    return ok

def end_capture():
    for label,p,_ in CAPS:
        if p.poll() is None:
            p.send_signal(signal.SIGINT)
            try:p.communicate(timeout=3)
            except subprocess.TimeoutExpired:p.kill();p.communicate(timeout=2)
        else:p.communicate(timeout=2)

def count_capture(label,path):
    if not path.is_file():
        return {'path':str(path),'error':'pcap missing'}
    p=cmd('tcpdump','-nn','-r',str(path),must=False,timeout=10)
    lines=p.stdout.splitlines()
    req=sum('echo request' in x.lower() and ANYCAST in x for x in lines)
    rep=sum('echo reply' in x.lower() and ANYCAST in x for x in lines)
    log(f'[CAPTURE] {label}: echo requests={req}, echo replies={rep}; {path}')
    return {'path':str(path),'echo_requests':req,'echo_replies':rep,'frames':len(lines),
            'decode_ok':p.returncode==0}

def cleanup():
    end_capture()
    for ns in reversed(CREATED):
        p=cmd('ip','netns','del',ns,must=False)
        if p.returncode:
            log(f'[CLEANUP WARN] failed to delete {ns}: {p.stderr.strip()}')
    p=cmd('ip','netns','list',must=False)
    remaining={line.split()[0] for line in p.stdout.splitlines() if line.strip()}
    DATA['cleanup']='complete' if not (remaining & set(CREATED)) else 'incomplete'
    log(f'[CLEANUP] {DATA["cleanup"]}; existing GNS3 and lab05 namespaces untouched')

def main():
    status='NOT_CONFIRMED'
    try:
        check_ready()
        log('===== LAB05 ISOLATED ROUTING-LEVEL ANYCAST DEMO =====')
        log('[PRESERVE] No GNS3 project, existing namespaces or host routing modifications')
        create_network()
        start_capture()
        first=ping_service('PREFERRED_SWA',NEXT_A,'ca')
        # Remove just the *newly created* primary test route. No host routes touched.
        ip(C,'-6','route','del','3888::/128','via',NEXT_A,'dev','ca','metric','10')
        second=ping_service('FAILOVER_SWB',NEXT_B,'cb')
        end_capture()
        DATA['captures']['SWA']=count_capture('SWA',PCAPA)
        DATA['captures']['SWB']=count_capture('SWB',PCAPB)
        both=all(DATA['captures'][x].get('echo_requests',0)>=3 and
                 DATA['captures'][x].get('echo_replies',0)>=3 for x in ('SWA','SWB'))
        status='ANYCAST_ROUTING_MODEL_PASS' if first and second and both else 'ANYCAST_NOT_CONFIRMED'
    finally:
        cleanup()
        DATA['result']=status
        EVID.mkdir(parents=True,exist_ok=True)
        REPORT.write_text(json.dumps(DATA,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        log(f'[REPORT] {REPORT}')
        log(f'RESULT={status}')

if __name__=='__main__':
    try:main()
    except Exception as e:
        print(f'[STOP] {type(e).__name__}: {e}',file=sys.stderr,flush=True)
        sys.exit(1)