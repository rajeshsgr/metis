from pathlib import Path
import tomllib

import yaml
from typer.testing import CliRunner

from metis.cli import app
from metis.generator import generate_project
from metis.recipe import load_recipe


ROOT = Path(__file__).parents[1]
SCHEMA = ROOT / "schema/recipe.schema.json"
AGENT_RECIPE = load_recipe(ROOT / "recipes/agent/recipe.yaml", SCHEMA)


def agent_answers(
    llm: str = "openai",
    state: str = "redis",
) -> dict[str, str]:
    return {
        "llm": llm,
        "agent_runtime": "langgraph",
        "state": state,
        "framework": "fastapi",
    }


def test_add_rag_merges_agent_project_without_losing_services_or_values(
    tmp_path: Path, monkeypatch
) -> None:
    destination = generate_project(AGENT_RECIPE, "agent-project", tmp_path, agent_answers())
    monkeypatch.chdir(destination)
    env_path = destination / ".env.example"
    env_path.write_text(
        env_path.read_text()
        + "OPENAI_API_KEY=existing-openai\n"
        + "REDIS_URL=redis://custom:6379\n"
        + "UNRELATED_VALUE=preserved\n",
        encoding="utf-8",
    )
    original_agent = (destination / "app/agent.py").read_bytes()
    original_main = (destination / "app/main.py").read_bytes()

    result = CliRunner().invoke(app, ["add", "rag"], input="chroma\nhuggingface\n")

    assert result.exit_code == 0, result.output
    compose = yaml.safe_load((destination / "docker-compose.yml").read_text())
    assert set(compose["services"]) == {"app", "redis", "chroma"}
    assert compose["services"]["app"]["depends_on"] == ["redis", "chroma"]
    assert (destination / "app/agent.py").read_bytes() == original_agent
    assert (destination / "app/main.py").read_bytes() == original_main

    dependencies = tomllib.loads((destination / "pyproject.toml").read_text())["project"]["dependencies"]
    assert sum(value.startswith("langgraph") for value in dependencies) == 1
    assert sum(value.startswith("redis") for value in dependencies) == 1
    assert sum(value.startswith("sentence-transformers") for value in dependencies) == 1
    assert sum(value.startswith("chromadb") for value in dependencies) == 1

    env = env_path.read_text()
    assert "OPENAI_API_KEY=existing-openai" in env
    assert "REDIS_URL=redis://custom:6379" in env
    assert "UNRELATED_VALUE=preserved" in env
    assert env.count("HUGGINGFACE_API_KEY=") == 1

    metadata = yaml.safe_load((destination / ".metis/project.yaml").read_text())
    assert metadata["selections"]["llm"] == "openai"
    assert metadata["selections"]["embedding"] == "huggingface"
    assert metadata["selections"]["vector_db"] == "chroma"
    assert metadata["capabilities"][-2:] == ["embeddings", "vector-db"]
    assert (destination / "app/rag.py").exists()


def test_add_rag_is_idempotent_and_reuses_existing_llm(
    tmp_path: Path, monkeypatch
) -> None:
    destination = generate_project(
        AGENT_RECIPE,
        "idempotent-agent",
        tmp_path,
        agent_answers(llm="anthropic", state="none"),
    )
    monkeypatch.chdir(destination)
    runner = CliRunner()

    first = runner.invoke(app, ["add", "rag"], input="qdrant\nopenai\n")
    assert first.exit_code == 0, first.output
    tracked = (
        "docker-compose.yml",
        ".env.example",
        "pyproject.toml",
        ".metis/project.yaml",
        "app/rag.py",
    )
    snapshot = {path: (destination / path).read_bytes() for path in tracked}

    second = runner.invoke(app, ["add", "rag"], input="")

    assert second.exit_code == 0, second.output
    assert "already satisfied" in second.output
    assert {path: (destination / path).read_bytes() for path in tracked} == snapshot
    dependencies = tomllib.loads((destination / "pyproject.toml").read_text())["project"]["dependencies"]
    assert sum(value.startswith("anthropic") for value in dependencies) == 1
    assert sum(value.startswith("openai") for value in dependencies) == 1


def test_add_rag_does_not_update_metadata_when_merge_fails(
    tmp_path: Path, monkeypatch
) -> None:
    destination = generate_project(AGENT_RECIPE, "failed-agent", tmp_path, agent_answers())
    monkeypatch.chdir(destination)
    metadata_path = destination / ".metis/project.yaml"
    original_metadata = metadata_path.read_bytes()
    pyproject_path = destination / "pyproject.toml"
    pyproject_path.write_text("[project]\ndependencies = [\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["add", "rag"], input="qdrant\nopenai\n")

    assert result.exit_code == 1
    assert "pyproject.toml" in result.output
    assert metadata_path.read_bytes() == original_metadata


def test_add_rag_fails_on_metadata_filesystem_conflict(
    tmp_path: Path, monkeypatch
) -> None:
    destination = generate_project(AGENT_RECIPE, "conflict-agent", tmp_path, agent_answers())
    monkeypatch.chdir(destination)
    compose_path = destination / "docker-compose.yml"
    compose = yaml.safe_load(compose_path.read_text())
    compose["services"]["chroma"] = {"image": "chromadb/chroma:latest"}
    compose_path.write_text(yaml.safe_dump(compose, sort_keys=False), encoding="utf-8")
    metadata_path = destination / ".metis/project.yaml"
    metadata = yaml.safe_load(metadata_path.read_text())
    metadata["selections"]["vector_db"] = "qdrant"
    metadata_path.write_text(yaml.safe_dump(metadata, sort_keys=False), encoding="utf-8")
    original_metadata = metadata_path.read_bytes()

    result = CliRunner().invoke(app, ["add", "rag"], input="")

    assert result.exit_code == 1
    assert "already defines chroma" in result.output
    assert metadata_path.read_bytes() == original_metadata