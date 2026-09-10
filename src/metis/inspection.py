from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

import yaml


class InspectionError(ValueError):
    """Raised when a Metis project cannot be inspected."""


@dataclass(frozen=True)
class InspectionReport:
    project_name: str
    recipe: str
    selections: dict[str, str]
    capabilities: tuple[str, ...]
    infrastructure: tuple[str, ...]
    warnings: tuple[str, ...]


def _dependency_name(value: str) -> str:
    return re.split(r"[<>=!~;\[]", value, maxsplit=1)[0].strip().lower()


def _read_yaml(path: Path) -> dict:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise InspectionError(f"could not read {path}: {error}") from error
    if not isinstance(value, dict):
        raise InspectionError(f"{path} must contain a YAML object")
    return value


def _read_dependencies(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise InspectionError(f"could not read {path}: {error}") from error
    project = document.get("project", {})
    dependencies = project.get("dependencies", []) if isinstance(project, dict) else []
    return {_dependency_name(str(value)) for value in dependencies}


def _read_services(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise InspectionError(f"could not read {path}: {error}") from error
    if not isinstance(document, dict):
        return {}
    services = document.get("services", {})
    return services if isinstance(services, dict) else {}


def _has_env_variable(path: Path, name: str) -> bool:
    if not path.exists():
        return False
    try:
        return any(
            line.split("=", 1)[0].strip() == name
            for line in path.read_text(encoding="utf-8").splitlines()
            if "=" in line and not line.lstrip().startswith("#")
        )
    except OSError as error:
        raise InspectionError(f"could not read {path}: {error}") from error


def _selection_evidence(
    selection: str,
    selections: dict[str, str],
    dependencies: set[str],
    services: dict,
    project_path: Path,
) -> bool:
    if selection == "openai":
        return "openai" in dependencies
    if selection == "anthropic":
        return "anthropic" in dependencies
    if selection == "huggingface":
        return "sentence-transformers" in dependencies
    if selection == "qdrant":
        return "qdrant" in services and "qdrant-client" in dependencies
    if selection == "chroma":
        return "chroma" in services and "chromadb" in dependencies
    if selection == "redis":
        return "redis" in services and "redis" in dependencies
    if selection == "none":
        return (project_path / "app/config.py").exists()
    if selection in {"plain-sdk", "langgraph"}:
        return (project_path / "app/agent.py").exists()
    return True


def _capability_evidence(
    capability: str,
    selections: dict[str, str],
    dependencies: set[str],
    services: dict,
    project_path: Path,
) -> bool | None:
    if capability == "python":
        return (project_path / "pyproject.toml").exists()
    if capability == "fastapi":
        return "fastapi" in dependencies
    if capability == "llm":
        provider = selections.get("llm")
        return _selection_evidence(provider, selections, dependencies, services, project_path) if provider else bool(
            {"openai", "anthropic"} & dependencies
        )
    if capability == "agent-runtime":
        return (project_path / "app/agent.py").exists()
    if capability == "state":
        state = selections.get("state", "none")
        return _selection_evidence(state, selections, dependencies, services, project_path)
    if capability == "embeddings":
        embedding = selections.get("embedding")
        return (
            _selection_evidence(embedding, selections, dependencies, services, project_path)
            and (project_path / "app/rag.py").exists()
            if embedding
            else (project_path / "app/rag.py").exists()
        )
    if capability == "vector-db":
        vector_db = selections.get("vector_db")
        return _selection_evidence(vector_db, selections, dependencies, services, project_path) if vector_db else bool(
            {"qdrant", "chroma"} & services.keys()
        )
    if capability == "rag":
        return (project_path / "app/rag.py").exists()
    return None


def inspect_project(project_path: Path) -> InspectionReport | None:
    metadata_path = project_path / ".metis" / "project.yaml"
    if not metadata_path.exists():
        return None

    metadata = _read_yaml(metadata_path)
    project = metadata.get("project")
    if not isinstance(project, dict) or not project.get("name") or not project.get("recipe"):
        raise InspectionError("metadata project.name and project.recipe are required")
    selections = metadata.get("selections") or {}
    if not isinstance(selections, dict):
        raise InspectionError("metadata selections must be a YAML object")
    capabilities = metadata.get("capabilities") or []
    if not isinstance(capabilities, list):
        raise InspectionError("metadata capabilities must be a YAML list")

    pyproject_path = project_path / "pyproject.toml"
    dependencies = _read_dependencies(pyproject_path)
    compose_services = _read_services(project_path / "docker-compose.yml")
    infrastructure = []
    if pyproject_path.exists():
        infrastructure.append("Python project")
    if (project_path / "docker-compose.yml").exists():
        infrastructure.append("Docker Compose")
        if compose_services:
            infrastructure.append("Services: " + ", ".join(sorted(compose_services)))
    if (project_path / ".env.example").exists():
        infrastructure.append("Environment template")

    warnings: list[str] = []
    for capability in dict.fromkeys(str(value) for value in capabilities):
        evidence = _capability_evidence(
            capability,
            {str(key): str(value) for key, value in selections.items()},
            dependencies,
            compose_services,
            project_path,
        )
        if evidence is False:
            warnings.append(f"capability '{capability}' is recorded but supporting evidence is missing")

    normalized_selections = {str(key): str(value) for key, value in selections.items()}
    for key, value in normalized_selections.items():
        if key in {"llm", "embedding", "vector_db", "state"} and not _selection_evidence(
            value, normalized_selections, dependencies, compose_services, project_path
        ):
            warnings.append(f"selection '{key}: {value}' is not supported by project files")

    pyproject_project = {}
    if pyproject_path.exists():
        try:
            pyproject_project = tomllib.loads(pyproject_path.read_text(encoding="utf-8")).get("project", {})
        except (OSError, tomllib.TOMLDecodeError) as error:
            raise InspectionError(f"could not read {pyproject_path}: {error}") from error
    if isinstance(pyproject_project, dict) and pyproject_project.get("name") != project["name"]:
        warnings.append(
            f"metadata project name '{project['name']}' differs from pyproject project name '{pyproject_project.get('name', 'missing')}'"
        )

    return InspectionReport(
        project_name=str(project["name"]),
        recipe=str(project["recipe"]),
        selections=normalized_selections,
        capabilities=tuple(dict.fromkeys(str(value) for value in capabilities)),
        infrastructure=tuple(infrastructure),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def format_inspection(report: InspectionReport | None) -> str:
    if report is None:
        return "Metis Project Inspection\n\nThis project is not initialized by Metis."

    lines = [
        "Metis Project Inspection",
        "",
        "Project",
        f"  Name: {report.project_name}",
        f"  Recipe: {report.recipe}",
        "",
        "Selections",
    ]
    if report.selections:
        lines.extend(f"  {_label(key)}: {report.selections[key]}" for key in sorted(report.selections))
    else:
        lines.append("  None")
    lines.extend(["", "Capabilities"])
    lines.extend(f"  {'✓' if not _capability_warning(capability, report.warnings) else '!'} {capability}" for capability in report.capabilities)
    lines.extend(["", "Infrastructure"])
    lines.extend(f"  {item}" for item in report.infrastructure or ("None detected",))
    if report.warnings:
        lines.extend(["", "Warnings"])
        lines.extend(f"  WARNING: {warning}" for warning in report.warnings)
    return "\n".join(lines)


def _label(value: str) -> str:
    labels = {"llm": "LLM", "vector_db": "Vector DB", "agent_runtime": "Agent Runtime"}
    return labels.get(value, value.replace("_", " ").title())


def _capability_warning(capability: str, warnings: tuple[str, ...]) -> bool:
    return any(f"capability '{capability}'" in warning for warning in warnings)