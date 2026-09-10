from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from metis.cli import app
from metis.generator import generate_project
from metis.recipe import load_recipe


ROOT = Path(__file__).parents[1]
SCHEMA = ROOT / "schema/recipe.schema.json"
RECIPE = load_recipe(ROOT / "recipes/agent/recipe.yaml", SCHEMA)


def answers(
    llm: str = "openai",
    agent_runtime: str = "plain-sdk",
    state: str = "none",
) -> dict[str, str]:
    return {
        "llm": llm,
        "agent_runtime": agent_runtime,
        "state": state,
        "framework": "fastapi",
    }


def test_init_agent_generates_project(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        app,
        ["init", "agent", "--name", "demo-agent"],
        input="\n\n\n\n",
    )

    assert result.exit_code == 0, result.output
    assert "Observability" not in result.output
    assert (tmp_path / "demo-agent/app/agent.py").exists()
    assert (tmp_path / "demo-agent/tests/test_agent.py").exists()

    metadata = yaml.safe_load((tmp_path / "demo-agent/.metis/project.yaml").read_text())
    assert metadata["schemaVersion"] == 1
    assert metadata["project"] == {"name": "demo-agent", "recipe": "agent"}
    assert metadata["selections"] == {
        "llm": "openai",
        "agent_runtime": "plain-sdk",
        "state": "none",
        "framework": "fastapi",
    }
    assert metadata["capabilities"] == [
        "python",
        "fastapi",
        "llm",
        "agent-runtime",
        "state",
    ]

    compose = yaml.safe_load((tmp_path / "demo-agent/docker-compose.yml").read_text())
    assert set(compose["services"]) == {"app"}
    env = (tmp_path / "demo-agent/.env.example").read_text()
    assert "OPENAI_API_KEY=" in env
    assert "LANGFUSE_" not in env
    assert "langfuse" not in (tmp_path / "demo-agent/pyproject.toml").read_text()


@pytest.mark.parametrize(
    ("agent_runtime", "state", "expected_services", "expected_depends_on"),
    [
        ("plain-sdk", "none", {"app"}, None),
        ("plain-sdk", "redis", {"app", "redis"}, ["redis"]),
        ("langgraph", "none", {"app"}, None),
        ("langgraph", "redis", {"app", "redis"}, ["redis"]),
    ],
)
def test_agent_compose_config_is_valid_for_supported_combinations(
    tmp_path: Path,
    agent_runtime: str,
    state: str,
    expected_services: set[str],
    expected_depends_on: list[str] | None,
) -> None:
    destination = generate_project(
        RECIPE,
        "agent-compose-check",
        tmp_path,
        answers(llm="openai", agent_runtime=agent_runtime, state=state),
    )

    compose = yaml.safe_load((destination / "docker-compose.yml").read_text())
    assert set(compose["services"]) == expected_services
    assert "services" in compose
    assert "app" in compose["services"]
    app_service = compose["services"]["app"]
    if expected_depends_on is None:
        assert "depends_on" not in app_service
    else:
        assert app_service["depends_on"] == expected_depends_on

    result = __import__("subprocess").run(
        ["docker", "compose", "config", "--quiet"],
        cwd=destination,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_agent_recipe_supports_selected_runtime_and_redis_state(tmp_path: Path) -> None:
    destination = generate_project(
        RECIPE,
        "agent-config",
        tmp_path,
        answers(llm="anthropic", agent_runtime="langgraph", state="redis"),
    )

    compose = yaml.safe_load((destination / "docker-compose.yml").read_text())
    assert set(compose["services"]) == {"app", "redis"}
    assert compose["services"]["app"]["depends_on"] == ["redis"]

    pyproject = (destination / "pyproject.toml").read_text()
    assert "anthropic>=0.30" in pyproject
    assert "langgraph>=0.3" in pyproject
    assert "redis>=5.0" in pyproject

    env = (destination / ".env.example").read_text()
    assert "ANTHROPIC_API_KEY=" in env
    assert "REDIS_URL=" in env
