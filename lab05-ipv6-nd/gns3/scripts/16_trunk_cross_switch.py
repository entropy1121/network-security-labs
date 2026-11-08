#!/usr/bin/env python3
"""Lab05: genuine cross-switch 802.1Q verification in EXISTING GNS3 stable project.

Uses the existing tested 13_build_stable.py API/auth/VPCS helper and exact project UUID.
Adds only two VPCS on unused access ports: PC5 -> SWB Eth3 VLAN100,
PC6 -> SWA Eth3 VLAN200. Does not alter CE12800 project or PC1-PC4 config.
Safe to rerun; never deletes nodes/links. New nodes intentionally remain as evidence.
"""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime

ROOT=Path.home()/'network-security/Lab05_GNS3_Huawei_AutoKit'
LIB=ROOT/'scripts/13_build_stable.py'
EVID=ROOT/'evidence'
PID='5c3ba01a-e12d-4bd7-bd31-276ca31dacbb'
HUAW='79e4f583-9057-4401-a743-20e52462585c'
NAME='Lab05_NDP_Stable_L2'
STAMP=datetime.now().strftime('%Y%m%d_%H%M%S')
REPORT=EVID/f'16_trunk_{STAMP}.json'

if not LIB.is_file():
    raise SystemExit('Missing scripts/13_build_stable.py, cannot safely reuse authenticated API')
spec=importlib.util.spec_from_file_location('lab05_existing_lib',LIB)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.STAMP='trunk_'+STAMP
m.TRANSCRIPT=EVID/f'16_trunk_{STAMP}.txt'

SW_A='SWA-L2-VLAN100-200'
SW_B='SWB-L2-VLAN100-200'
C1='PC5-TrunkVLAN100'
C2='PC6-TrunkVLAN200'
EXPECTED={
    'PC1':('vpcs',None), 'PC2':('vpcs',None),
    'PC3':('vpcs',None), 'PC4':('vpcs',None),
    SW_A:('ethernet_switch',None), SW_B:('ethernet_switch',None),
}
TRIAL={C1: ('vpcs', 610, 300), C2: ('vpcs', -610, 300)}
BASE_LINKS=[
    (('PC1',0),(SW_A,1)), (('PC2',0),(SW_A,2)),
    (('PC3',0),(SW_B,1)), (('PC4',0),(SW_B,2)),
    ((SW_A,0),(SW_B,0)),
]
ADD_LINKS=[((C1,0),(SW_B,3)),((C2,0),(SW_A,3))]


def stop(message):
    raise RuntimeError(message)


def norm_link(link,by_id):
    pair=[]
    for endpoint in link.get('nodes',[]):
        nid=endpoint['node_id']
        if nid not in by_id: stop('Existing link contains unknown node ID '+nid)
        if int(endpoint['adapter_number'])!=0: stop('Unexpected adapter on existing link')
        pair.append((by_id[nid]['name'],int(endpoint['port_number'])))
    if len(pair)!=2: stop('Unexpected link with !=2 endpoints')
    return frozenset(pair)


def audit_switch(sess,node,pid,expected):
    obj=m.api(sess,'GET',f'projects/{pid}/nodes/{node["node_id"]}')
    entries={int(p['port_number']):p for p in obj.get('properties',{}).get('ports_mapping',[])}
    for port,mode,vlan in expected:
        entry=entries.get(port)
        if not entry or entry.get('type')!=mode or int(entry.get('vlan',-1))!=vlan:
            stop(f'{node["name"]} Eth{port} mismatch: got {entry}, expected {mode} VLAN{vlan}')
    m.log(f'[SWITCH VERIFIED] {node["name"]}: {[(p,t,v) for p,t,v in expected]}')


def start_cap(sess,pid,link_id,filename):
    d=m.api(sess,'GET',f'projects/{pid}/links/{link_id}')
    if d.get('capturing'):
        m.log(f'[CAPTURE SKIP] link already capturing {link_id}; will not interrupt')
        return None
    result=m.api(sess,'POST',f'projects/{pid}/links/{link_id}/start_capture',
        {'data_link_type':'DLT_EN10MB','capture_file_name':filename})
    path=result.get('capture_file_path')
    m.log(f'[CAPTURE START] {path}')
    return link_id,path


def pcap_info(path):
    out={'path':path,'vlan100':0,'vlan200':0,'lines':[], 'icmp6':{}}
    if not path or not Path(path).is_file():
        out['error']='Capture file missing'
        return out
    cmd=['tcpdump','-n','-e','-r',path]
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=25)
    if p.returncode:
        out['error']=p.stderr[-500:]
        return out
    lines=p.stdout.splitlines()
    out['frame_count']=len(lines)
    out['vlan100']=sum(bool(re.search(r'\bvlan\s+100\b',line,re.I)) for line in lines)
    out['vlan200']=sum(bool(re.search(r'\bvlan\s+200\b',line,re.I)) for line in lines)
    out['lines']=[line[:300] for line in lines[:15]]
    out['icmp6']=m.decode_pcap(path)
    return out


def main():
    EVID.mkdir(parents=True,exist_ok=True)
    state=ROOT/'lab05_gns3_state.json'
    if not state.is_file() or json.loads(state.read_text()).get('project_id')!=HUAW:
        stop('Existing Huawei project state not matching expected: no changes made')
    s=m.session()
    original=m.api(s,'GET',f'projects/{HUAW}')
    if original.get('name')!='Lab05_NDP_Huawei_Auto':stop('Huawei project identity mismatch')
    project=m.api(s,'GET',f'projects/{PID}')
    if project.get('name')!=NAME:stop('Stable project identity mismatch')
    m.log(f'[REUSE PROJECT] {NAME} UUID={PID}; original Huawei UUID={HUAW} protected')

    nodes=m.api(s,'GET',f'projects/{PID}/nodes')
    names={n['name']:n for n in nodes}
    if len(names)!=len(nodes):stop('Duplicate node names, refusing')
    if set(names)-set(EXPECTED)-set(TRIAL):stop('Unexpected nodes present; refusing to change existing project')
    if set(EXPECTED)-set(names):stop('Missing baseline node(s), refusing')
    for name in names:
        typ=EXPECTED[name][0] if name in EXPECTED else TRIAL[name][0]
        if names[name]['node_type']!=typ:stop(f'Node type changed on {name}')
    audit_switch(s,names[SW_A],PID,[(0,'dot1q',1),(1,'access',100),(2,'access',100),(3,'access',200)])
    audit_switch(s,names[SW_B],PID,[(0,'dot1q',1),(1,'access',200),(2,'access',200),(3,'access',100)])

    existing=m.api(s,'GET',f'projects/{PID}/links')
    by_id={n['node_id']:n for n in nodes}
    signatures={norm_link(l,by_id):l for l in existing}
    if len(signatures)!=len(existing):stop('Duplicate links, refusing')
    base={frozenset(edge) for edge in BASE_LINKS}
    trial={frozenset(edge) for edge in ADD_LINKS}
    if not base.issubset(signatures):stop('Baseline topology link missing, refusing')
    extras=set(signatures)-base-trial
    if extras:stop(f'Unexpected links {extras}; refusing')
    for n1,p1,n2,p2 in [(*a,*b) for a,b in ADD_LINKS]:
        if frozenset({(n1,p1),(n2,p2)}) not in signatures:
            for endpoint in [(n1,p1),(n2,p2)]:
                if any(endpoint in k for k in signatures):stop(f'Expected free port already occupied: {endpoint}')
    m.log('[PREFLIGHT] Existing 5-link topology intact; extra switch ports checked')

    for name,(kind,x,y) in TRIAL.items():
        if name not in names:
            names[name]=m.create_node(s,PID,name,kind,x,y)
        else:m.log(f'[NODE REUSE] {name}')
    for a,b in ADD_LINKS:
        edge=frozenset((a,b))
        if edge not in signatures:
            m.link(s,PID,names[a[0]],a[1],names[b[0]],b[1])
        else:m.log(f'[LINK REUSE] {a} <-> {b}')

    check_links=m.api(s,'GET',f'projects/{PID}/links')
    current={n['node_id']:n for n in m.api(s,'GET',f'projects/{PID}/nodes')}
    byname={n['name']:n for n in current.values()}
    edge_to_link={norm_link(l,current):l for l in check_links}
    if set(edge_to_link)!=(base|trial):stop('Postcheck link layout differs from the expected 7 links')
    for name in ['PC1','PC3',C1,C2]:
        node=byname[name]
        if node['status']!='started':
            m.api(s,'POST',f'projects/{PID}/nodes/{node["node_id"]}/start',{})
            m.log(f'[NODE START] {name}')
    time.sleep(1.0)
    byname={n['name']:n for n in m.api(s,'GET',f'projects/{PID}/nodes')}
    clients={};captures=[];capture_details=[];pings={}
    try:
        for name in ['PC1','PC3',C1,C2]:
            node=byname[name]
            if node['status']!='started' or not node.get('console'):
                stop(f'Cannot open VPCS console: {name} {node.get("status")}')
            clients[name]=m.VPCS(name,node['console'])
        addr={'PC1':'2000::1','PC3':'3000::3',C1:'2000::5',C2:'3000::6'}
        for name,ip in addr.items():
            content=clients[name].cmd('show ipv6')
            if not m.configured_ipv6(content,ip):
                if name in {'PC1','PC3'}:stop(f'Existing {name} has changed IPv6; refusing to modify baseline')
                clients[name].cmd(f'ip {ip}/64')
                if not m.configured_ipv6(clients[name].cmd('show ipv6'),ip):
                    stop(f'Failed to configure new {name} address')
            m.log(f'[ADDR VERIFIED] {name}: {ip}/64')
        # Capture on physical inter-switch link; legitimate VLAN tags should be visible.
        capture_targets=[('TRUNK',frozenset(BASE_LINKS[-1])),
                         (C1, frozenset(ADD_LINKS[0])),
                         (C2, frozenset(ADD_LINKS[1]))]
        for label,edge in capture_targets:
            try:
                link=edge_to_link[edge]
                cap=start_cap(s,PID,link['link_id'],f'Lab05_trunk_{STAMP}_{label}.pcap')
                if cap:captures.append((label,*cap))
            except Exception as ex:
                m.log(f'[CAPTURE WARN] {label}: {type(ex).__name__} {ex}')
        for who,target,label in [
             ('PC1','2000::5','VLAN100_SWA_to_SWB'),(C1,'2000::1','VLAN100_SWB_to_SWA'),
             ('PC3','3000::6','VLAN200_SWB_to_SWA'),(C2,'3000::3','VLAN200_SWA_to_SWB')]:
            txt=clients[who].cmd(f'ping {target} -c 3',timeout=30)
            count=m.count_vpcs_replies(txt,target)
            m.log(f'[PING {"PASS" if count==3 else "FAIL"}] {label}: {count}/3')
            pings[label]={'received':count,'sent':3,'pass':count==3}
    finally:
        for label,link_id,path in captures:
            try:
                reply=m.api(s,'POST',f'projects/{PID}/links/{link_id}/stop_capture',{})
                finalpath=reply.get('capture_file_path') or path
                info=pcap_info(finalpath)
                capture_details.append((label,info))
                m.log(f'[PCAP] {label}: frames={info.get("frame_count",0)} '
                      f'vlan100={info["vlan100"]} vlan200={info["vlan200"]} {finalpath}')
            except Exception as ex:
                m.log(f'[CAPTURE WARN] stopping {label}: {type(ex).__name__} {ex}')
        for client in clients.values():client.close()
    data={k:v for k,v in capture_details}
    pings_pass=(len(pings)==4 and all(v['pass'] for v in pings.values()))
    tagged=(data.get('TRUNK',{}).get('vlan100',0)>0 and data.get('TRUNK',{}).get('vlan200',0)>0)
    if pings_pass and tagged:status='GNS3_TRUNK_VLAN100_200_PASS'
    elif pings_pass:status='GNS3_TRUNK_PING_PASS_TAG_NOT_CONFIRMED'
    else:status='GNS3_TRUNK_NOT_YET_PASS'
    REPORT.write_text(json.dumps({'project_id':PID,'project_name':NAME,
        'platform':'GNS3 built-in Ethernet Switch; not Huawei CE12800 dataplane',
        'nodes_added':[C1,C2],
        'new_links':['PC5-TrunkVLAN100->SWB Eth3 VLAN100','PC6-TrunkVLAN200->SWA Eth3 VLAN200'],
        'ping':pings,'capture':data,
        'trunk_tagged_both_vlans':tagged,
        'result':status,'original_huawei_untouched':HUAW,
        'note':'PC1-PC4 unchanged. New test VPCS nodes remain in project to preserve evidence.'},
        ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    m.log(f'[REPORT] {REPORT}')
    m.log(f'RESULT={status}')
    if not pings_pass:sys.exit(2)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        m.log(f'[STOP] {type(exc).__name__}: {exc}')
        m.log('[SAFETY] No deletion or overwrite of original Huawei project')
        sys.exit(1)