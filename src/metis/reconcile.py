from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Callable

import yaml

from . import __version__
from .models import Recipe


class ReconciliationError(ValueError):
    """Raised when a capability cannot be safely applied."""


RAG_SOURCE = '''"""Minimal RAG integration point for the generated project."""


def retrieve(query: str) -> list[str]:
    """Return retrieved documents once a provider-specific pipeline is added."""
    return []
'''


def _read_yaml(path: Path) -> dict:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ReconciliationError(f"could not read {path}: {error}") from error
    if not isinstance(value, dict):
        raise ReconciliationError(f"{path} must contain a YAML object")
    return value


def _choice(
    prompt: Callable[..., str],
    message: str,
    default: str,
    options: tuple[str, ...],
) -> str:
    answer = prompt(message, default=default).strip().lower()
    if answer not in options:
        raise ReconciliationError(f"unsupported {message.lower()}: {answer}")
    return answer


def _package_name(dependency: str) -> str:
    return re.split(r"[<>=!~;\[]", dependency, maxsplit=1)[0].strip().lower()


def _merge_compose(text: str, vector_db: str) -> str:
    try:
        compose = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ReconciliationError(f"docker-compose.yml is invalid: {error}") from error
    if not isinstance(compose, dict) or not isinstance(compose.get("services"), dict):
        raise ReconciliationError("docker-compose.yml must define services")

    services = compose["services"]
    if "app" not in services or not isinstance(services["app"], dict):
        raise ReconciliationError("docker-compose.yml must define an app service")

    vector_service = {
        "qdrant": {
            "image": "qdrant/qdrant:latest",
            "ports": ["6333:6333"],
        },
        "chroma": {
            "image": "chromadb/chroma:latest",
            "ports": ["8001:8000"],
        },
    }[vector_db]
    if vector_db not in services:
        services[vector_db] = vector_service

    app_service = services["app"]
    depends_on = app_service.get("depends_on")
    if depends_on is None:
        app_service["depends_on"] = [vector_db]
    elif isinstance(depends_on, list):
        if vector_db not in depends_on:
            depends_on.append(vector_db)
    elif isinstance(depends_on, dict):
        depends_on.setdefault(vector_db, {"condition": "service_started"})
    else:
        raise ReconciliationError("app.depends_on has an unsupported format")

    result = yaml.safe_dump(compose, sort_keys=False)
    try:
        yaml.safe_load(result)
    except yaml.YAMLError as error:
        raise ReconciliationError(f"merged docker-compose.yml is invalid: {error}") from error
    return result


def _merge_env(text: str, embedding: str) -> str:
    required = "OPENAI_API_KEY" if embedding == "openai" else "HUGGINGFACE_API_KEY"
    existing_keys = {
        line.split("=", 1)[0].strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#") and "=" in line
    }
    if required not in existing_keys:
        text = text.rstrip("\n") + f"\n{required}=\n"
    elif not text.endswith("\n"):
        text += "\n"
    return text


def _merge_pyproject(text: str, embedding: str, vector_db: str) -> str:
    try:
        project = tomllib.loads(text).get("project")
    except tomllib.TOMLDecodeError as error:
        raise ReconciliationError(f"pyproject.toml is invalid: {error}") from error
    if not isinstance(project, dict) or not isinstance(project.get("dependencies"), list):
        raise ReconciliationError("pyproject.toml must define project.dependencies")

    required = [
        "sentence-transformers>=3.0" if embedding == "huggingface" else "openai>=1.0",
        "qdrant-client>=1.0" if vector_db == "qdrant" else "chromadb>=0.5",
    ]
    existing_names = {_package_name(str(dependency)) for dependency in project["dependencies"]}
    missing = [dependency for dependency in required if _package_name(dependency) not in existing_names]
    if not missing:
        return text

    project_start = text.find("[project]")
    dependencies_start = text.find("dependencies = [", project_start)
    if project_start < 0 or dependencies_start < 0:
        raise ReconciliationError("pyproject.toml must define project.dependencies")
    closing_bracket = text.find("\n]", dependencies_start)
    if closing_bracket < 0:
        raise ReconciliationError("project.dependencies must be a multiline array")
    additions = "".join(f'    "{dependency}",\n' for dependency in missing)
    return text[: closing_bracket + 1] + additions + text[closing_bracket + 1 :]


def _updated_metadata(
    metadata: dict,
    selections: dict[str, str],
) -> str:
    updated = dict(metadata)
    updated.setdefault("schemaVersion", 1)
    updated.setdefault("metisVersion", __version__)
    current_selections = dict(updated.get("selections") or {})
    current_selections.update(selections)
    updated["selections"] = current_selections
    current_capabilities = list(dict.fromkeys(updated.get("capabilities") or []))
    for capability in ("embeddings", "vector-db"):
        if capability not in current_capabilities:
            current_capabilities.append(capability)
    updated["capabilities"] = current_capabilities
    return yaml.safe_dump(updated, sort_keys=False)


def reconcile_rag_project(
    destination: Path,
    rag_recipe: Recipe,
    prompt: Callable[..., str],
) -> bool:
    metadata_path = destination / ".metis" / "project.yaml"
    if not metadata_path.exists():
        raise ReconciliationError("project is not initialized by Metis")
    metadata = _read_yaml(metadata_path)
    project = metadata.get("project")
    if not isinstance(project, dict) or project.get("recipe") != "agent":
        raise ReconciliationError("rag can only be added to an initialized agent project")

    compose_path = destination / "docker-compose.yml"
    env_path = destination / ".env.example"
    pyproject_path = destination / "pyproject.toml"
    for path in (compose_path, env_path, pyproject_path):
        if not path.exists():
            raise ReconciliationError(f"required project file is missing: {path.name}")

    compose_text = compose_path.read_text(encoding="utf-8")
    compose = _read_yaml(compose_path)
    services = compose.get("services", {})
    if not isinstance(services, dict):
        raise ReconciliationError("docker-compose.yml must define services")
    existing_vectors = [name for name in ("qdrant", "chroma") if name in services]
    if len(existing_vectors) > 1:
        raise ReconciliationError("compose defines conflicting vector database services")
    existing_vector = existing_vectors[0] if existing_vectors else None
    selections = metadata.get("selections") or {}
    selected_vector = selections.get("vector_db")
    if selected_vector and existing_vector and selected_vector != existing_vector:
        raise ReconciliationError(
            f"metadata selects {selected_vector}, but compose already defines {existing_vector}"
        )
    vector_db = selected_vector or existing_vector
    if vector_db is None:
        vector_db = _choice(prompt, "Choose vector database", "qdrant", ("qdrant", "chroma"))
    elif vector_db not in ("qdrant", "chroma"):
        raise ReconciliationError(f"unsupported vector database in metadata: {vector_db}")

    embedding = selections.get("embedding")
    if embedding is None:
        embedding = _choice(prompt, "Choose embedding provider", "openai", ("openai", "huggingface"))

    pyproject_text = pyproject_path.read_text(encoding="utf-8")
    required_package = "sentence-transformers" if embedding == "huggingface" else "openai"
    vector_package = "qdrant-client" if vector_db == "qdrant" else "chromadb"
    try:
        dependencies = tomllib.loads(pyproject_text)["project"]["dependencies"]
    except (KeyError, TypeError, tomllib.TOMLDecodeError) as error:
        raise ReconciliationError("pyproject.toml must define project.dependencies") from error
    source_path = destination / "app" / "rag.py"
    already_satisfied = (
        existing_vector == vector_db
        and any(_package_name(str(value)) == required_package for value in dependencies)
        and any(_package_name(str(value)) == vector_package for value in dependencies)
        and source_path.exists()
    )
    if already_satisfied:
        return False

    merged_compose = _merge_compose(compose_text, vector_db)
    merged_env = _merge_env(env_path.read_text(encoding="utf-8"), embedding)
    merged_pyproject = _merge_pyproject(pyproject_text, embedding, vector_db)
    metadata_text = _updated_metadata(metadata, {"embedding": embedding, "vector_db": vector_db})

    compose_path.write_text(merged_compose, encoding="utf-8")
    env_path.write_text(merged_env, encoding="utf-8")
    pyproject_path.write_text(merged_pyproject, encoding="utf-8")
    if not source_path.exists():
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(RAG_SOURCE, encoding="utf-8")
    metadata_path.write_text(metadata_text, encoding="utf-8")
    return True