"""Run configured challenge Compose projects without changing their source files."""

import json
import os
import re
import subprocess
from pathlib import Path


DATA_DIR = Path(os.environ.get("TINY_CONTAINERS_DATA", "/var/tiny-containers"))
REPO_DIR = Path(os.environ.get("TINY_CONTAINERS_REPO", "/challs"))
DOMAIN = os.environ.get("TINY_CONTAINERS_DOMAIN", "").strip(".")
PROXY_NETWORK = os.environ.get("TINY_CONTAINERS_PROXY_NETWORK", "tiny-containers-proxy")


def _docker(*args, timeout=300):
    result = subprocess.run(
        ["docker", *map(str, args)], capture_output=True, text=True, timeout=timeout, check=False
    )
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip()[-2000:])
    return result.stdout


def compose_files():
    if not REPO_DIR.is_dir():
        return []
    return sorted(
        str(path.relative_to(REPO_DIR))
        for path in REPO_DIR.rglob("*")
        if path.is_file()
        and path.name in {"compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml"}
        and not any(part in {"node_modules", ".git"} for part in path.relative_to(REPO_DIR).parts)
    )


def _source_file(relative_path):
    if relative_path not in compose_files():
        raise ValueError("Select a Compose file from the challenge repository")
    return REPO_DIR / relative_path


def source_config(relative_path):
    return json.loads(_docker("compose", "-f", _source_file(relative_path), "config", "--format", "json"))


def public_target_from_config(config):
    published = []
    exposed = []
    for name, service in config.get("services", {}).items():
        for port in service.get("ports") or []:
            published.append((name, port))
        for port in service.get("expose") or []:
            exposed.append((name, {"target": port, "protocol": "tcp"}))
    candidates = published or exposed
    if len(candidates) != 1:
        raise ValueError("Compose must declare exactly one public port across its services")
    service, port = candidates[0]
    if port.get("protocol", "tcp") != "tcp":
        raise ValueError("Only TCP challenge ports are supported")
    target = int(str(port["target"]).split("/", 1)[0])
    if not 1 <= target <= 65535:
        raise ValueError("The Compose target port is invalid")
    published_port = port.get("published")
    return {"service": service, "container_port": target,
            "port": int(published_port) if published_port else None}


def public_target(relative_path):
    return public_target_from_config(source_config(relative_path))


def hostname(subdomain):
    if not DOMAIN:
        raise ValueError("TINY_CONTAINERS_DOMAIN is not configured")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", subdomain):
        raise ValueError("Subdomain must be a DNS label")
    return f"{subdomain}.{DOMAIN}"


def endpoint(record):
    if record.protocol == "tcp":
        if not DOMAIN:
            raise ValueError("TINY_CONTAINERS_DOMAIN is not configured")
        return f"nc {DOMAIN} {record.host_port}"
    return f"http://{hostname(record.subdomain)}"


def project(challenge_id):
    return f"tiny-containers-{challenge_id}"


def runtime_file(challenge_id):
    return DATA_DIR / f"{challenge_id}.json"


def prepare(record, flag):
    config = source_config(record.compose_file)
    target_info = public_target_from_config(config)
    container_port = target_info["container_port"]
    if not 1 <= record.host_port <= 65535:
        raise ValueError("Ports must be between 1 and 65535")
    router = f"tc-{record.challenge_id}"
    config.pop("name", None)
    for network in config.get("networks", {}).values():
        if not network.get("external"):
            network.pop("name", None)
    for volume in config.get("volumes", {}).values():
        if not volume.get("external"):
            volume.pop("name", None)
    for service_name, service in config["services"].items():
        # The managed project's public port is controlled by the admin panel.
        service.pop("ports", None)
        service.pop("container_name", None)
        service.setdefault("environment", {})["FLAG"] = flag
        if "build" in service:
            service["image"] = f"tiny-containers/challenge-{record.challenge_id}-{service_name}:latest"
    target = config["services"][target_info["service"]]
    target["ports"] = [f"0.0.0.0:{record.host_port}:{container_port}"]
    labels = target.setdefault("labels", {})
    if isinstance(labels, list):
        labels = dict(label.split("=", 1) for label in labels)
        target["labels"] = labels
    labels.update({
        "io.tiny-containers.managed_by": "tiny-containers",
        "io.tiny-containers.challenge_id": str(record.challenge_id),
    })
    if record.protocol == "http":
        host = hostname(record.subdomain)
        labels.update({
            "traefik.enable": "true",
            "traefik.docker.network": PROXY_NETWORK,
            f"traefik.http.routers.{router}.rule": f"Host(`{host}`)",
            f"traefik.http.routers.{router}.entrypoints": "web",
            f"traefik.http.routers.{router}.service": router,
            f"traefik.http.services.{router}.loadbalancer.server.port": str(container_port),
        })
        networks = target.setdefault("networks", {"default": None})
        if isinstance(networks, list):
            networks = {name: None for name in networks}
            target["networks"] = networks
        networks[PROXY_NETWORK] = None
        if "default" in networks:
            config.setdefault("networks", {}).setdefault("default", {})
        config.setdefault("networks", {})[PROXY_NETWORK] = {
            "name": PROXY_NETWORK,
            "external": True,
        }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = runtime_file(record.challenge_id)
    path.write_text(json.dumps(config))
    path.chmod(0o600)
    return path


def up(record, flag, recreate=False):
    path = prepare(record, flag)
    args = ["compose", "-p", project(record.challenge_id), "-f", path, "up", "-d"]
    if recreate:
        args.append("--force-recreate")
    return _docker(*args)


def build(record, flag):
    path = prepare(record, flag)
    return _docker("compose", "-p", project(record.challenge_id), "-f", path,
                   "build", timeout=1800)


def down(challenge_id):
    path = runtime_file(challenge_id)
    if path.exists():
        output = _docker("compose", "-p", project(challenge_id), "-f", path, "down")
        path.unlink()
        return output
    return ""


def discard(challenge_id):
    runtime_file(challenge_id).unlink(missing_ok=True)


def containers(challenge_id):
    output = _docker(
        "ps", "-a", "--filter", f"label=com.docker.compose.project={project(challenge_id)}",
        "--format", "{{json .}}",
    )
    return [json.loads(line) for line in output.splitlines() if line]


def snapshot():
    output = _docker("ps", "-a", "--filter", "label=com.docker.compose.project",
                     "--format", "{{json .}}")
    groups = {}
    running_ids = []
    for line in output.splitlines():
        entry = json.loads(line)
        match = re.search(r"(?:^|,)com\.docker\.compose\.project=tiny-containers-(\d+)(?:,|$)",
                          entry.get("Labels", ""))
        if match:
            groups.setdefault(int(match.group(1)), []).append(entry)
            if entry.get("State") == "running":
                running_ids.append(entry["ID"])
    metrics = {}
    if running_ids:
        output = _docker("stats", "--no-stream", "--format", "{{json .}}", *running_ids)
        metrics = {item["ID"][:12]: item for item in
                   (json.loads(line) for line in output.splitlines())}
    result = {}
    for challenge_id, entries in groups.items():
        active = [metrics.get(entry["ID"][:12], {}) for entry in entries
                  if entry.get("State") == "running"]
        result[challenge_id] = {
            "status": ", ".join(entry.get("State", "unknown") for entry in entries),
            "cpu": ", ".join(item.get("CPUPerc", "—") for item in active) or "—",
            "memory": ", ".join(item.get("MemUsage", "—") for item in active) or "—",
            "running": any(entry.get("State") == "running" for entry in entries),
            "services": [{
                "name": next((part.split("=", 1)[1] for part in entry.get("Labels", "").split(",")
                              if part.startswith("com.docker.compose.service=")), entry.get("Names", "")),
                "container": entry.get("Names", ""),
                "state": entry.get("State", "unknown"),
                "health": entry.get("HealthStatus", "none"),
            } for entry in entries],
        }
    return result


def logs(challenge_id, lines=200):
    path = runtime_file(challenge_id)
    if not path.exists():
        return ""
    return _docker("compose", "-p", project(challenge_id), "-f", path,
                   "logs", "--no-color", "--tail", min(lines, 1000))
