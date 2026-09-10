from __future__ import annotations

import json
import os
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence
from urllib.error import URLError
from urllib.request import urlopen

import yaml


class DoctorError(ValueError):
    """Raised when a project cannot be evaluated by doctor."""


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class DoctorReport:
    checks: tuple[DoctorCheck, ...]

    @property
    def failures(self) -> tuple[DoctorCheck, ...]:
        return tuple(check for check in self.checks if not check.passed)


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
HttpChecker = Callable[[str], tuple[bool, str]]
RedisChecker = Callable[[str, int], tuple[bool, str]]


def _run_command(
    command: Sequence[str],
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        return subprocess.CompletedProcess(command, 127, "", str(error))


def _http_check(url: str) -> tuple[bool, str]:
    try:
        with urlopen(url, timeout=2) as response:
            body = response.read()
        if url.endswith("/health"):
            payload = json.loads(body)
            if payload != {"status": "ok"}:
                return False, "unexpected health response"
        return True, "reachable"
    except (OSError, URLError, json.JSONDecodeError, ValueError) as error:
        return False, str(error)


def _redis_check(host: str, port: int) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=2) as connection:
            connection.sendall(b"*1\r\n$4\r\nPING\r\n")
            response = connection.recv(32)
        if b"PONG" not in response:
            return False, "unexpected PING response"
        return True, "reachable"
    except OSError as error:
        return False, str(error)


def _read_metadata(project_path: Path) -> dict:
    metadata_path = project_path / ".metis" / "project.yaml"
    if not metadata_path.exists():
        raise DoctorError("project is not initialized by Metis")
    try:
        metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise DoctorError(f"could not read project metadata: {error}") from error
    if not isinstance(metadata, dict):
        raise DoctorError("project metadata must contain a YAML object")
    return metadata


def _read_services(project_path: Path) -> dict:
    compose_path = project_path / "docker-compose.yml"
    if not compose_path.exists():
        return {}
    try:
        compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise DoctorError(f"could not read docker-compose.yml: {error}") from error
    if not isinstance(compose, dict) or not isinstance(compose.get("services"), dict):
        return {}
    return compose["services"]


def _published_port(service: dict, container_port: int) -> int | None:
    ports = service.get("ports", [])
    if not isinstance(ports, list):
        return None
    for mapping in ports:
        if isinstance(mapping, str):
            host_and_container = mapping.rsplit(":", 1)
            if len(host_and_container) == 2 and host_and_container[1].split("/", 1)[0] == str(container_port):
                host_port = host_and_container[0].rsplit(":", 1)[-1]
                if host_port.isdigit():
                    return int(host_port)
        elif isinstance(mapping, dict) and str(mapping.get("target")) == str(container_port):
            published = mapping.get("published")
            if published is not None and str(published).isdigit():
                return int(published)
    return None


def _read_env_file(project_path: Path) -> dict[str, str]:
    env_path = project_path / ".env"
    if not env_path.exists():
        return {}
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise DoctorError(f"could not read .env: {error}") from error
    values: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        values[name.strip()] = value.strip().strip("'\"")
    return values


def _required_environment(selections: dict[str, str]) -> tuple[str, ...]:
    names: list[str] = []
    providers = {
        "openai": ("OPENAI_API_KEY",),
        "anthropic": ("ANTHROPIC_API_KEY",),
        "huggingface": ("HUGGINGFACE_API_KEY",),
    }
    for key in ("llm", "embedding"):
        provider = selections.get(key)
        for name in providers.get(provider, ()):
            if name not in names:
                names.append(name)
    if selections.get("state") == "redis":
        names.append("REDIS_URL")
    return tuple(dict.fromkeys(names))


def _environment_checks(project_path: Path, selections: dict[str, str]) -> tuple[DoctorCheck, ...]:
    file_values = _read_env_file(project_path)
    required = _required_environment(selections)
    checks = []
    for name in required:
        value = os.environ.get(name) or file_values.get(name)
        checks.append(DoctorCheck(name, bool(value), "configured" if value else "missing"))
    return tuple(checks)


def run_doctor(
    project_path: Path,
    command_runner: CommandRunner = _run_command,
    http_checker: HttpChecker = _http_check,
    redis_checker: RedisChecker = _redis_check,
) -> DoctorReport:
    metadata = _read_metadata(project_path)
    selections_data = metadata.get("selections") or {}
    if not isinstance(selections_data, dict):
        raise DoctorError("project metadata selections must be a YAML object")
    selections = {str(key): str(value) for key, value in selections_data.items()}
    services = _read_services(project_path)
    checks: list[DoctorCheck] = []

    docker = command_runner(["docker", "--version"], cwd=project_path)
    checks.append(DoctorCheck("Docker available", docker.returncode == 0, "available" if docker.returncode == 0 else "not available"))
    compose = command_runner(["docker", "compose", "version"], cwd=project_path)
    checks.append(DoctorCheck("Docker Compose available", compose.returncode == 0, "available" if compose.returncode == 0 else "not available"))

    if compose.returncode == 0:
        config = command_runner(["docker", "compose", "config"], cwd=project_path)
        checks.append(DoctorCheck("Compose configuration valid", config.returncode == 0, "valid" if config.returncode == 0 else "invalid"))
    else:
        checks.append(DoctorCheck("Compose configuration valid", False, "Docker Compose unavailable"))

    if "app" in services:
        passed, detail = http_checker("http://localhost:8000/health")
        checks.append(DoctorCheck("Application reachable", passed, detail))

    service_probes = {
        "qdrant": ("Qdrant reachable", "http://localhost:6333/"),
    }
    for service, (name, url) in service_probes.items():
        if service in services:
            passed, detail = http_checker(url)
            checks.append(DoctorCheck(name, passed, detail))
    if "chroma" in services:
        chroma_port = _published_port(services["chroma"], 8000)
        if chroma_port is None:
            checks.append(DoctorCheck("Chroma reachable", False, "published port is not configured"))
        else:
            passed, detail = http_checker(f"http://localhost:{chroma_port}/api/v2/heartbeat")
            checks.append(DoctorCheck("Chroma reachable", passed, detail))
    if "redis" in services:
        passed, detail = redis_checker("localhost", 6379)
        checks.append(DoctorCheck("Redis reachable", passed, detail))

    checks.extend(_environment_checks(project_path, selections))
    return DoctorReport(tuple(checks))


def format_doctor(report: DoctorReport) -> str:
    lines = ["Metis Doctor", ""]
    for check in report.checks:
        marker = "✓" if check.passed else "✗"
        detail = f" ({check.detail})" if check.detail and check.name not in _SECRET_CHECK_NAMES else ""
        lines.append(f"{marker} {check.name}{detail}")
    lines.extend(["", f"{len(report.failures)} issue(s) found."])
    return "\n".join(lines)


_SECRET_CHECK_NAMES = {
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "HUGGINGFACE_API_KEY",
    "REDIS_URL",
}