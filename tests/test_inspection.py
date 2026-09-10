from pathlib import Path

import yaml
from typer.testing import CliRunner

from metis.cli import app
from metis.generator import generate_project
from metis.recipe import load_recipe


ROOT = Path(__file__).parents[1]
SCHEMA = ROOT / "schema/recipe.schema.json"
RAG_RECIPE = load_recipe(ROOT / "recipes/rag/recipe.yaml", SCHEMA)
AGENT_RECIPE = load_recipe(ROOT / "recipes/agent/recipe.yaml", SCHEMA)


def rag_answers() -> dict[str, str]:
    return {
        "vector_db": "qdrant",
        "llm": "openai",
        "embedding": "openai",
        "framework": "fastapi",
    }


def agent_answers() -> dict[str, str]:
    return {
        "llm": "anthropic",
        "agent_runtime": "langgraph",
        "state": "redis",
        "framework": "fastapi",
    }


def test_inspect_reports_rag_project_deterministically(tmp_path: Path, monkeypatch) -> None:
    destination = generate_project(RAG_RECIPE, "inspect-rag", tmp_path, rag_answers())
    monkeypatch.chdir(destination)

    first = CliRunner().invoke(app, ["inspect"])
    second = CliRunner().invoke(app, ["inspect"])

    assert first.exit_code == 0, first.output
    assert first.output == second.output
    assert "Name: inspect-rag" in first.output
    assert "Recipe: rag" in first.output
    assert "Vector DB: qdrant" in first.output
    assert "Capabilities" in first.output
    assert "✓ python" in first.output
    assert "Docker Compose" in first.output
    assert "Services: app, qdrant" in first.output
    assert "Warnings" not in first.output


def test_inspect_reports_agent_project_selections_and_infrastructure(
    tmp_path: Path, monkeypatch
) -> None:
    destination = generate_project(AGENT_RECIPE, "inspect-agent", tmp_path, agent_answers())
    monkeypatch.chdir(destination)

    result = CliRunner().invoke(app, ["inspect"])

    assert result.exit_code == 0, result.output
    assert "Recipe: agent" in result.output
    assert "LLM: anthropic" in result.output
    assert "Agent Runtime: langgraph" in result.output
    assert "State: redis" in result.output
    assert "Services: app, redis" in result.output
    assert "WARNING" not in result.output


def test_inspect_warns_on_metadata_filesystem_discrepancy_without_writing(
    tmp_path: Path, monkeypatch
) -> None:
    destination = generate_project(RAG_RECIPE, "discrepant-rag", tmp_path, rag_answers())
    compose_path = destination / "docker-compose.yml"
    compose = yaml.safe_load(compose_path.read_text())
    del compose["services"]["qdrant"]
    compose_path.write_text(yaml.safe_dump(compose, sort_keys=False), encoding="utf-8")
    before = {
        path.relative_to(destination): path.read_bytes()
        for path in destination.rglob("*")
        if path.is_file()
    }
    monkeypatch.chdir(destination)

    result = CliRunner().invoke(app, ["inspect"])

    assert result.exit_code == 0, result.output
    assert "WARNING" in result.output
    assert "vector-db" in result.output
    assert "selection 'vector_db: qdrant'" in result.output
    after = {
        path.relative_to(destination): path.read_bytes()
        for path in destination.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_inspect_handles_non_metis_project_cleanly(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "README.md").write_text("Existing project", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["inspect"])

    assert result.exit_code == 0, result.output
    assert "not initialized by Metis" in result.output
    assert (tmp_path / "README.md").read_text() == "Existing project"