#!/usr/bin/env python3
"""Lab 05 isolated namespace batch: link-local, static ND, transient neighbor states.

Only touches l05pc1 IPv6 neighbor entries and two namespaced ND timers; always
restores timers, deletes test entries and relearns the real neighbor.
Does NOT modify GNS3 projects, host interfaces, routes, or other namespaces.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess as sp
import sys
import time
from datetime import datetime

PREFIX='l05'
HOME=Path(os.environ.get('SUDO_USER_HOME', str(Path.home())))
# root under sudo should save into the invoking user's real WSL home
if os.environ.get('SUDO_USER'):
    import pwd
    HOME=Path(pwd.getpwnam(os.environ['SUDO_USER']).pw_dir)
EVID=HOME/'network-security/lab05-ipv6-nd/evidence'
TAG=datetime.now().strftime('%Y%m%d_%H%M%S')
REPORT=EVID/f'15_neighbor_batch_{TAG}.json'
PCAP=EVID/f'15_static_neighbor_{TAG}.pcap'
RESULTS={}


def run(args, *, timeout=20, quiet=False):
    p=sp.run(args, text=True, stdout=sp.PIPE, stderr=sp.STDOUT, timeout=timeout)
    if not quiet:
        print('CMD:', ' '.join(args), '\n'+p.stdout.rstrip(), '\nEXIT=',p.returncode,flush=True)
    return p


def ip(*args, quiet=False):return run(['ip',*args],quiet=quiet)


def ping(ns,addr,c=2,iface=None):
    cmd=['ip','netns','exec',ns,'ping','-6','-c',str(c),'-W','1']
    if iface:cmd+=['-I',iface]
    cmd.append(addr)
    p=run(cmd,timeout=12)
    match=re.search(r'(\d+) packets transmitted, (\d+) received',p.stdout)
    ok= bool(match and int(match.group(2))==c and p.returncode==0)
    return ok


def neigh(addr='2000::2'):
    p=ip('-n','l05pc1','-6','neigh','show',addr,'dev','eth0',quiet=True)
    print('NEIGH:',p.stdout.strip() or '[no entry]',flush=True)
    return p.stdout.strip()


def check(ok,name):
    RESULTS[name]=bool(ok)
    print(f'[{"PASS" if ok else "NOT_CONFIRMED"}] {name}',flush=True)


def sysctl_get(k):
    p=run(['ip','netns','exec','l05pc1','sysctl','-n',k],quiet=True)
    if p.returncode: raise RuntimeError(f'Cannot read {k}: {p.stdout}')
    return p.stdout.strip()


def sysctl_set(k,v):
    p=run(['ip','netns','exec','l05pc1','sysctl','-w',f'{k}={v}'])
    if p.returncode: raise RuntimeError(f'Cannot set {k}: {p.stdout}')


def require_lab():
    if os.geteuid()!=0: raise SystemExit('Run using sudo /usr/bin/python3 (isolated namespace needs root)')
    for tool in ['ip','ping','tcpdump','sysctl']:
        if not shutil.which(tool): raise SystemExit(f'Missing command: {tool}')
    p=run(['ip','netns','list'],quiet=True)
    ns=set(x.split()[0] for x in p.stdout.splitlines() if x.strip())
    missing={'l05pc1','l05pc2','l05swa','l05swb'}-ns
    if missing:
        raise SystemExit('NAMESPACE_MISSING: '+','.join(sorted(missing))+'\nNo changes were made. Previous WSL namespace topology may have been cleared by a restart.')
    for ns,dev in [('l05pc1','eth0'),('l05pc2','eth0'),('l05swa','lan100'),('l05swb','lan100')]:
        if ip('-n',ns,'link','show',dev,quiet=True).returncode:
            raise SystemExit(f'MISSING_DEVICE: {ns}/{dev}, no changes made')
    EVID.mkdir(parents=True,exist_ok=True)


def main():
    require_lab()
    print('===== LAB05 ISOLATED NEIGHBOR BATCH =====',flush=True)
    print('[SAFETY] No GNS3 changes; no root namespace network interface changes',flush=True)
    pre_mac=ip('-n','l05pc2','link','show','eth0',quiet=True).stdout
    match=re.search(r'link/ether\s+([0-9a-f:]{17})',pre_mac,re.I)
    if not match:raise RuntimeError('Could not detect PC2 MAC; stopped safely')
    mac=match.group(1).lower()
    wrong='02:ff:ff:00:00:01'
    if wrong==mac: raise RuntimeError('Unexpected fake address collision')
    print('PC2_REAL_MAC=',mac,'TEMP_WRONG_MAC=',wrong,flush=True)
    originals={};cap=None
    ndkeys={'reachable_ms':'net.ipv6.neigh.eth0.base_reachable_time_ms',
            'delay_s':'net.ipv6.neigh.eth0.delay_first_probe_time'}
    try:
        print('\n===== 1. LINK-LOCAL AND SCOPE =====',flush=True)
        for ns,dev in [('l05swa','lan100'),('l05swa','lan200'),('l05swb','lan100')]:
            run(['ip','-n',ns,'-6','addr','show','dev',dev])
        out=ip('-n','l05swb','-6','addr','show','dev','lan100',quiet=True).stdout
        addrs=re.findall(r'inet6\s+(fe80::[0-9a-f:]+)/\d+',out,re.I)
        if addrs:
            check(ping('l05swa',addrs[0],iface='lan100'),'LINK_LOCAL_PING_WITH_INTERFACE')
        else:check(False,'SWB_LINK_LOCAL_DISCOVERY')

        print('\n===== 2. STATIC NEIGHBOR: correct -> incorrect -> restore =====',flush=True)
        baseline=ping('l05pc1','2000::2')
        check(baseline,'STATIC_BASELINE')
        if baseline:
            cap=sp.Popen(['tcpdump','-n','-i','l05p1','-U','-s','0','-w',str(PCAP),'icmp6'],
                        stdout=sp.DEVNULL,stderr=sp.PIPE,text=True)
            time.sleep(0.45)
            if cap.poll() is not None:
                print('[CAPTURE WARN] tcpdump exited:',cap.stderr.read(),flush=True)
                cap=None
            ip('-n','l05pc1','-6','neigh','replace','2000::2','lladdr',mac,'nud','permanent','dev','eth0')
            correct_neigh=neigh()
            check(mac in correct_neigh and 'PERMANENT' in correct_neigh.upper() and ping('l05pc1','2000::2'),
                  'STATIC_CORRECT_PASS')
            ip('-n','l05pc1','-6','neigh','replace','2000::2','lladdr',wrong,'nud','permanent','dev','eth0')
            wrong_neigh=neigh()
            wrong_failed=not ping('l05pc1','2000::2')
            check(wrong in wrong_neigh and wrong_failed,'STATIC_WRONG_FAILS_AS_EXPECTED')
            ip('-n','l05pc1','-6','neigh','del','2000::2','dev','eth0')
            check(ping('l05pc1','2000::2'),'STATIC_RESTORED')
            neigh()
        else:
            print('[SKIPPED] Baseline failed; no neighbor mappings modified',flush=True)

        print('\n===== 3. NEIGHBOR NUD STATES (observations, not forced labels) =====',flush=True)
        for k,v in ndkeys.items(): originals[k]=sysctl_get(v)
        sysctl_set(ndkeys['reachable_ms'],'1000')
        sysctl_set(ndkeys['delay_s'],'2')
        ip('-n','l05pc1','-6','neigh','del','2000::2','dev','eth0',quiet=True)
        check(ping('l05pc1','2000::2',c=1),'NUD_BASELINE_PING')
        first=neigh();check('REACHABLE' in first.upper(),'NUD_REACHABLE')
        observed=[first]
        for _ in range(20):
            time.sleep(0.22)
            s=neigh();observed.append(s)
            if 'STALE' in s.upper():break
        check(any('STALE' in s.upper() for s in observed),'NUD_STALE_OBSERVED')
        # Trigger use of a stale entry and poll closely for DELAY / PROBE.
        subprocess=sp.Popen(['ip','netns','exec','l05pc1','ping','-6','-c','1','-W','1','2000::2'],
                            stdout=sp.PIPE,stderr=sp.STDOUT,text=True)
        nud_trace=[]
        for _ in range(40):
            item=neigh();nud_trace.append(item)
            time.sleep(0.12)
        subprocess.communicate(timeout=5)
        check(any('DELAY' in s.upper() for s in nud_trace),'NUD_DELAY_OBSERVED')
        check(any('PROBE' in s.upper() for s in nud_trace),'NUD_PROBE_OBSERVED')
        # Nonexistent neighbor; capture before probe exhausts.
        probe=sp.Popen(['ip','netns','exec','l05pc1','ping','-6','-c','2','-W','1','2000::8888'],
                       stdout=sp.PIPE,stderr=sp.STDOUT,text=True)
        incomplete=[]
        for _ in range(12):
            incomplete.append(neigh('2000::8888'))
            time.sleep(0.12)
        probe.communicate(timeout=6)
        check(any('INCOMPLETE' in s.upper() for s in incomplete),'NUD_INCOMPLETE_OBSERVED')
        print('\nNOTE: PROBE may be too short to observe when the peer replies promptly. Do not claim success unless explicitly observed.',flush=True)
    finally:
        print('\n===== AUTOMATIC RESTORE =====',flush=True)
        for k,v in originals.items():
            try:sysctl_set(ndkeys[k],v)
            except Exception as e:print('[RESTORE WARN] sysctl',k,e,flush=True)
        # Remove only entries for the test destination, never flush entire neighbor tables.
        for addr in ['2000::2','2000::8888']:
            try:ip('-n','l05pc1','-6','neigh','del',addr,'dev','eth0',quiet=True)
            except Exception as e:print('[RESTORE WARN] neighbor',addr,e,flush=True)
        if cap is not None:
            cap.send_signal(signal.SIGINT)
            try:cap.communicate(timeout=3)
            except sp.TimeoutExpired:cap.kill();cap.communicate()
            print('PCAP=',PCAP,flush=True)
        try:
            good=ping('l05pc1','2000::2',c=1)
            check(good,'FINAL_CONNECTIVITY_RESTORED')
        except Exception as e:print('[RESTORE WARN] ping',e,flush=True)
        EVID.mkdir(parents=True,exist_ok=True)
        REPORT.write_text(json.dumps({'source':'Real namespace test; not Huawei CE12800',
                                      'results':RESULTS,'pcap':str(PCAP) if PCAP.exists() else None,
                                      'original_sysctls_restored':originals},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print('REPORT=',REPORT,flush=True)
    print('RESULT=LAB05_NEIGHBOR_BATCH_FINISHED',flush=True)

if __name__=='__main__':
    try:main()
    except Exception as ex:
        print('ERROR=',type(ex).__name__,str(ex),file=sys.stderr,flush=True)
        sys.exit(1)