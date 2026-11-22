#!/usr/bin/env python3
"""Create and operate the Lab 06 GNS3 topology on the local controller."""

import argparse
import base64
import configparser
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

NODE_LAYOUT = {
    "R1": ("qemu", 0, -120),
    "SWA": ("ethernet_switch", -160, 0),
    "PC1": ("vpcs", -320, 0),
    "SWB": ("ethernet_switch", 160, 0),
    "R2": ("qemu", 320, -120),
    "R3": ("qemu", 320, 120),
}
LINK_LAYOUT = {
    "r1-swa": (("R1", 2), ("SWA", 0)),
    "pc1-swa": (("PC1", 0), ("SWA", 1)),
    "r1-swb": (("R1", 1), ("SWB", 0)),
    "r2-swb": (("R2", 1), ("SWB", 1)),
    "r3-swb": (("R3", 1), ("SWB", 2)),
}
BASELINE_NODES = ("R1", "SWA", "PC1")
BASELINE_LINKS = ("r1-swa", "pc1-swa")
CAPTURE_LINKS = ("pc1-swa", "r1-swa", "r3-swb")


class LabError(Exception):
    pass


class Controller:
    def __init__(self, port, config_path):
        self.base = f"http://127.0.0.1:{port}/v2"
        self.opener = build_opener(ProxyHandler({}))
        self.headers = {"Content-Type": "application/json"}
        config = configparser.ConfigParser(interpolation=None)
        config.read(config_path, encoding="utf-8")
        username = config.get("Server", "user", fallback="")
        password = config.get("Server", "password", fallback="")
        if username and password:
            credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
            self.headers["Authorization"] = f"Basic {credentials}"

    def call(self, route, data=None):
        method = "GET" if data is None else "POST"
        body = None if data is None else json.dumps(data).encode()
        request = Request(f"{self.base}/{route}", body, self.headers, method=method)
        try:
            with self.opener.open(request, timeout=8 if method == "GET" else 35) as response:
                payload = response.read()
        except HTTPError as error:
            hint = "，请核对本机 GNS3 配置的认证设置" if error.code == 401 else ""
            raise LabError(f"{method} {route}: HTTP {error.code}{hint}") from None
        except (URLError, TimeoutError) as error:
            reason = getattr(error, "reason", error)
            raise LabError(f"{method} {route}: {reason}") from None
        return json.loads(payload) if payload else {}


def router_template(api, requested):
    templates = [
        item for item in api.call("templates")
        if item["template_type"] == "qemu" and item.get("compute_id") == "local"
    ]
    if requested:
        matches = [item for item in templates if item["name"] == requested]
    else:
        matches = [
            item for item in templates
            if re.search(r"ar[-_ ]?1kv|v300r021",
                         f"{item['name']} {item.get('hda_disk_image') or ''}", re.I)
        ]
    if len(matches) == 1:
        return matches[0]
    inventory = "、".join(item["name"] for item in templates) or "无"
    raise LabError(
        f"可用的目标 AR1kV 模板匹配到 {len(matches)} 个。本机 QEMU 模板：{inventory}。"
        "若已导入 AR1kV，请用 --router-template 指定确切模板名。"
    )


def project_path(api, name, create=False):
    matches = [item for item in api.call("projects") if item["name"] == name]
    if len(matches) > 1:
        raise LabError(f"发现多个同名项目 {name}，请用 --project 指定唯一项目名。")
    if matches:
        project = matches[0]
    elif create:
        project = api.call("projects", {"name": name})
    else:
        raise LabError(f"找不到项目 {name}，先执行 build-a。")
    path = f"projects/{project['project_id']}"
    if project.get("status") != "opened":
        api.call(f"{path}/open", {})
    return path


def get_nodes(api, path):
    nodes = {}
    for node in api.call(f"{path}/nodes"):
        name = node["name"]
        if name not in NODE_LAYOUT:
            continue
        if name in nodes or node["node_type"] != NODE_LAYOUT[name][0]:
            raise LabError(f"项目中节点 {name} 的名称或类型冲突。")
        nodes[name] = node
    return nodes


def ensure_node(api, path, template, nodes, name):
    kind, x, y = NODE_LAYOUT[name]
    if name in nodes:
        node = nodes[name]
        if kind == "qemu":
            actual = (node.get("properties") or {}).get("hda_disk_image")
            expected = template.get("hda_disk_image")
            if node.get("template_id") != template["template_id"] and (
                not actual or not expected or Path(actual).name != Path(expected).name
            ):
                raise LabError(f"{name} 已存在，无法确认使用了所选 AR1kV 模板。")
        return
    data = {"name": name, "compute_id": "local", "x": x, "y": y}
    if kind == "qemu":
        route = f"{path}/templates/{template['template_id']}"
    else:
        route = f"{path}/nodes"
        data["node_type"] = kind
        if kind == "ethernet_switch":
            data["properties"] = {
                "ports_mapping": [
                    {"name": f"Ethernet{port}", "port_number": port,
                     "type": "access", "vlan": 1}
                    for port in range(4)
                ]
            }
    nodes[name] = api.call(route, data)


def endpoint(node, index):
    adapter, port = (index, 0) if node["node_type"] == "qemu" else (0, index)
    if not any(
        (item["adapter_number"], item["port_number"]) == (adapter, port)
        for item in node.get("ports", [])
    ):
        raise LabError(f"{node['name']} 缺少预期端口 adapter={adapter}, port={port}。")
    return {"node_id": node["node_id"], "adapter_number": adapter, "port_number": port}


def endpoint_key(item):
    return item["node_id"], item["adapter_number"], item["port_number"]


def matching_link(links, endpoints):
    keys = {endpoint_key(item) for item in endpoints}
    for link in links:
        attached = {endpoint_key(item) for item in link["nodes"]}
        if keys == attached:
            return link
        if keys & attached:
            raise LabError("课件指定的端口已有其他接线，请核对拓扑。")
    return None


def build(api, options):
    template = router_template(api, options.router_template)
    phase_a = options.action == "build-a"
    path = project_path(api, options.project, create=phase_a)
    nodes = get_nodes(api, path)
    for name in BASELINE_NODES if phase_a else NODE_LAYOUT:
        ensure_node(api, path, template, nodes, name)
    links = api.call(f"{path}/links")
    for name in BASELINE_LINKS if phase_a else LINK_LAYOUT:
        endpoints = [endpoint(nodes[node], index) for node, index in LINK_LAYOUT[name]]
        if matching_link(links, endpoints) is None:
            links.append(api.call(f"{path}/links", {"nodes": endpoints}))
    print(f"拓扑已准备：{options.project}。模板：{template['name']}。")


def start(api, path, nodes):
    if not all(name in nodes for name in BASELINE_NODES):
        raise LabError("第一阶段节点不齐，先执行 build-a。")
    for name, node in nodes.items():
        if node.get("status") == "stopped":
            api.call(f"{path}/nodes/{node['node_id']}/start", {})
    for name, node in get_nodes(api, path).items():
        port = node.get("console")
        print(f"{name}: {node.get('status')}  " + (f"telnet 127.0.0.1 {port}" if port else ""))


def capture(api, path, nodes, options):
    layout = LINK_LAYOUT[options.link]
    if any(node not in nodes for node, _ in layout):
        raise LabError(f"{options.link} 对应的节点尚未创建。")
    endpoints = [endpoint(nodes[node], index) for node, index in layout]
    link = matching_link(api.call(f"{path}/links"), endpoints)
    if link is None:
        raise LabError(f"{options.link} 尚未接线。")
    route = f"{path}/links/{link['link_id']}"
    state = api.call(route)
    if options.action == "capture-start" and not state.get("capturing"):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        state = api.call(f"{route}/start_capture", {
            "data_link_type": "DLT_EN10MB",
            "capture_file_name": f"Lab06-{options.link}-{stamp}.pcap",
        })
    elif options.action == "capture-stop" and state.get("capturing"):
        api.call(f"{route}/stop_capture", {})
    file_path = state.get("capture_file_path") or state.get("capture_file_name")
    print(f"{options.link}: {options.action}  {file_path or '请在 GNS3 项目目录查看 captures'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=3080)
    parser.add_argument("--config", type=Path,
                        default=Path.home() / ".config/GNS3/2.2/gns3_server.conf")
    parser.add_argument("--project", default="Lab06_IPv6_SLAAC")
    parser.add_argument("--router-template", help="已安装到本机 GNS3 的 AR1kV 模板名称")
    parser.add_argument("--link", choices=CAPTURE_LINKS, default="pc1-swa")
    parser.add_argument("action", choices=[
        "check", "build-a", "build-b", "start", "capture-start", "capture-stop",
    ])
    options = parser.parse_args()
    try:
        api = Controller(options.port, options.config)
        version = api.call("version")["version"]
        if not version.startswith("2.2."):
            raise LabError(f"本流程面向 GNS3 2.2，当前服务版本为 {version}。")
        print(f"GNS3 {version}")
        if options.action == "check":
            print(f"AR1kV 模板：{router_template(api, options.router_template)['name']}")
        elif options.action in {"build-a", "build-b"}:
            build(api, options)
        else:
            path = project_path(api, options.project)
            nodes = get_nodes(api, path)
            if options.action == "start":
                start(api, path, nodes)
            else:
                capture(api, path, nodes, options)
    except (LabError, OSError, ValueError, configparser.Error) as error:
        print(f"Lab06: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
