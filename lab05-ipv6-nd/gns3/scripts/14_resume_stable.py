#!/usr/bin/env python3
"""Idempotent recovery for Lab05_NDP_Stable_L2 (GNS3 2.2.x).

Loads the user's existing 13_build_stable.py library. Inspects existing project,
creates only missing known nodes/links, refuses unexpected structures, then
configures/validates VPCS. Does not touch the original Huawei or control project.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback

ROOT = Path.home() / 'network-security/Lab05_GNS3_Huawei_AutoKit'
SOURCE = ROOT / 'scripts/13_build_stable.py'
if not SOURCE.is_file():
    raise SystemExit('Missing scripts/13_build_stable.py. Do not recreate projects manually.')
spec = importlib.util.spec_from_file_location('lab05_stable_existing', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

SWITCHES = {
    'SWA-L2-VLAN100-200': [m.pc_port(0,'dot1q',1),m.pc_port(1,'access',100),m.pc_port(2,'access',100),m.pc_port(3,'access',200)],
    'SWB-L2-VLAN100-200': [m.pc_port(0,'dot1q',1),m.pc_port(1,'access',200),m.pc_port(2,'access',200),m.pc_port(3,'access',100)],
}
PC_LAYOUT = {'PC1':(-430,210),'PC2':(-170,220),'PC3':(170,220),'PC4':(430,210)}
EXPECTED_TYPES = {**{name:'ethernet_switch' for name in SWITCHES},**{name:'vpcs' for name in PC_LAYOUT}}
EXPECTED_LINKS = [
    (('SWA-L2-VLAN100-200',0),('SWB-L2-VLAN100-200',0)),
    (('PC1',0),('SWA-L2-VLAN100-200',1)),
    (('PC2',0),('SWA-L2-VLAN100-200',2)),
    (('PC3',0),('SWB-L2-VLAN100-200',1)),
    (('PC4',0),('SWB-L2-VLAN100-200',2)),
]

def endpoints(link, by_id):
    eps=[]
    for port in link.get('nodes',[]):
        node=by_id.get(port.get('node_id'))
        if node is None:
            raise RuntimeError('Project link references an unknown node')
        if int(port.get('adapter_number',-1))!=0:
            raise RuntimeError('Unexpected adapter number in existing project')
        eps.append((node['name'],int(port['port_number'])))
    if len(eps)!=2:
        raise RuntimeError('Unexpected non-point-to-point link')
    return frozenset(eps)

def check_switch_ports(session, pid, node, expected):
    detail=m.api(session,'GET',f'projects/{pid}/nodes/{node["node_id"]}')
    mapping=detail.get('properties',{}).get('ports_mapping')
    if not isinstance(mapping,list):
        raise RuntimeError(f'{node["name"]}: cannot read switch VLAN configuration; stop, no modification')
    ports={int(p['port_number']):p for p in mapping}
    for target in expected:
        p=ports.get(target['port_number'])
        if not p or str(p.get('type','')).lower()!=target['type'] or int(p.get('vlan',-1))!=target['vlan']:
            raise RuntimeError(f'{node["name"]}: unexpected port {target["port_number"]}: {p!r}, expected {target!r}; stop')
    m.log(f'[VLAN VERIFIED] {node["name"]}: {[(t["port_number"],t["type"],t["vlan"]) for t in expected]}')

def main():
    if not m.ORIGINAL.is_file():
        raise RuntimeError('Original Huawei state missing')
    original_state=json.loads(m.ORIGINAL.read_text())
    if original_state.get('project_id')!='79e4f583-9057-4401-a743-20e52462585c':
        raise RuntimeError('Original Huawei project identity changed; refusing')
    m.EVID.mkdir(parents=True,exist_ok=True)
    sess=m.session()
    orig=m.api(sess,'GET',f'projects/{original_state["project_id"]}')
    if orig.get('name')!='Lab05_NDP_Huawei_Auto':
        raise RuntimeError('Huawei project identity mismatch; refusing')
    projects=[p for p in m.api(sess,'GET','projects') if p.get('name')==m.NAME]
    if len(projects)>1:
        raise RuntimeError('Multiple same-name stable projects: refusing ambiguous reuse')
    if not projects:
        raise RuntimeError('Existing stable project not found. Refusing to create a new project')
    pid=projects[0]['project_id']
    expected_pid='5c3ba01a-e12d-4bd7-bd31-276ca31dacbb'
    if pid!=expected_pid:
        raise RuntimeError(f'Unexpected stable project ID {pid}; expected {expected_pid}. Refusing to edit')
    m.log(f'[REUSE EXISTING] {m.NAME} id={pid}; no duplicate created')
    if pid in {original_state['project_id'],'ba80f341-0ac3-482a-96e7-7f76e2f07bfe'}:
        raise RuntimeError('Project ID overlaps protected project')

    existing=m.api(sess,'GET',f'projects/{pid}/nodes')
    names=[n.get('name','') for n in existing]
    if len(names)!=len(set(names)):
        raise RuntimeError('Duplicate node names in stable project: refusing')
    for n in existing:
        if n.get('name') not in EXPECTED_TYPES or n.get('node_type')!=EXPECTED_TYPES[n['name']]:
            raise RuntimeError(f'Unexpected node {n.get("name")!r} ({n.get("node_type")}); refusing to modify project')
    node_map={n['name']:n for n in existing}
    m.log(f'[AUDIT] existing_nodes={names}')
    for idx,(name,ports) in enumerate(SWITCHES.items()):
        if name not in node_map:
            x=-210 if idx==0 else 210
            node_map[name]=m.create_node(sess,pid,name,'ethernet_switch',x,-20,{'ports_mapping':ports})
        else:
            check_switch_ports(sess,pid,node_map[name],ports)
    for name,(x,y) in PC_LAYOUT.items():
        if name not in node_map:
            node_map[name]=m.create_node(sess,pid,name,'vpcs',x,y)
    # Switches created in this run also get server-read verification.
    for name,ports in SWITCHES.items():
        check_switch_ports(sess,pid,node_map[name],ports)

    node_by_id={n['node_id']:n for n in node_map.values()}
    actual_links=m.api(sess,'GET',f'projects/{pid}/links')
    found={endpoints(l,node_by_id) for l in actual_links}
    if len(found)!=len(actual_links):
        raise RuntimeError('Duplicate existing links; refusing')
    allowed={frozenset(pair) for pair in EXPECTED_LINKS}
    extras=found-allowed
    if extras:
        raise RuntimeError(f'Unexpected pre-existing links: {extras}; refusing')
    for (a,pa),(b,pb) in EXPECTED_LINKS:
        sig=frozenset({(a,pa),(b,pb)})
        if sig not in found:
            m.link(sess,pid,node_map[a],pa,node_map[b],pb)
        else:
            m.log(f'[LINK REUSE] {a}:{pa} <-> {b}:{pb}')
    actual_links=m.api(sess,'GET',f'projects/{pid}/links')
    if {endpoints(l,node_by_id) for l in actual_links}!=allowed:
        raise RuntimeError('Topology link validation failed after repair')
    m.log('[TOPOLOGY VERIFIED] 2 switches + 4 VPCS + 5 links, VLAN100/200')

    latest={n['name']:n for n in m.api(sess,'GET',f'projects/{pid}/nodes')}
    for name in PC_LAYOUT:
        if latest[name].get('status')!='started':
            m.api(sess,'POST',f'projects/{pid}/nodes/{latest[name]["node_id"]}/start',{})
            m.log(f'[START] {name}')
    time.sleep(1.2)
    latest={n['name']:n for n in m.api(sess,'GET',f'projects/{pid}/nodes')}
    clients={}; captures=[]; decoded=[]; results={}
    try:
        for name in PC_LAYOUT:
            n=latest[name]
            if n.get('status')!='started' or not n.get('console'):
                raise RuntimeError(f'VPCS {name} not ready: {n.get("status")} console={n.get("console")}')
            clients[name]=m.VPCS(name,n['console'])
        addresses={'PC1':'2000::1','PC2':'2000::2','PC3':'3000::3','PC4':'3000::4'}
        for name,addr in addresses.items():
            txt=clients[name].cmd('show ipv6')
            if not m.configured_ipv6(txt,addr):
                clients[name].cmd(f'ip {addr}/64')
                if not m.configured_ipv6(clients[name].cmd('show ipv6'),addr):
                    raise RuntimeError(f'Failed setting IPv6 on {name}')
            m.log(f'[ADDRESS VERIFIED] {name}: {addr}/64')
        for name in ('PC1','PC3'):
            try:
                cap=m.run_capture(sess,pid,latest[name]['node_id'])
                captures.append(cap)
            except RuntimeError as ex:
                m.log(f'[CAPTURE SKIPPED] {name}: {ex}')
        for src,dst,addr in [('PC1','PC2','2000::2'),('PC2','PC1','2000::1'),('PC3','PC4','3000::4'),('PC4','PC3','3000::3')]:
            reply=clients[src].cmd(f'ping {addr} -c 3',timeout=28)
            cnt=m.count_vpcs_replies(reply,addr)
            results[f'{src}->{dst}']={'replies':cnt,'sent':3,'pass':cnt==3}
            m.log(f'[PING {"PASS" if cnt==3 else "FAIL"}] {src}->{dst}: {cnt}/3')
    finally:
        for lid,path in captures:
            try:
                stopped=m.api(sess,'POST',f'projects/{pid}/links/{lid}/stop_capture',{})
                final=stopped.get('capture_file_path') or path
                data=m.decode_pcap(final)
                decoded.append(data)
                m.log(f'[PCAP] NS={data.get("ns")} NA={data.get("na")} EchoReply={data.get("echo_reply")} {final}')
            except Exception as ex:
                m.log(f'[CAPTURE WARN] {ex}')
        for client in clients.values(): client.close()
    success=len(results)==4 and all(v['pass'] for v in results.values())
    out=m.EVID/'14_resume_stable_result.json'
    out.write_text(json.dumps({'project_id':pid,'huawei_project_preserved':original_state['project_id'],
                               'topology':'2 GNS3 Ethernet Switch nodes and 4 VPCS, access VLAN100/200, dot1q trunk',
                               'results':results,'captures':decoded,'pass':success,
                               'limit':'VLAN local-host communication, not proof of inter-switch trunk, nor Huawei CE12800 dataplane'},
                              ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    m.log(f'[REPORT] {out}')
    m.log('RESULT='+('GNS3_L2_BASELINE_PASS' if success else 'GNS3_L2_BASELINE_INCOMPLETE'))
    if not success: sys.exit(2)

if __name__=='__main__':
    try: main()
    except Exception as ex:
        m.log(f'[STOP] {type(ex).__name__}: {ex}')
        m.log('[SAFETY] No project deleted. Original Huawei/control projects unmodified.')
        sys.exit(1)