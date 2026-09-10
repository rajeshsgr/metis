from pathlib import Path
import subprocess
import tomllib

import pytest
import yaml
from typer.testing import CliRunner

from metis.capabilities import load_capabilities, resolve_recipe_capabilities
from metis.cli import app
from metis.recipe import load_recipe


ROOT = Path(__file__).parents[1]
SCHEMA = ROOT / "schema/recipe.schema.json"
RECIPE_PATH = ROOT / "recipes/mcp-server/recipe.yaml"


def test_mcp_recipe_loads_and_composes_capabilities() -> None:
    recipe = load_recipe(RECIPE_PATH, SCHEMA)
    definitions = load_capabilities(ROOT / "capabilities")

    assert recipe.name == "mcp-server"
    assert [question.id for question in recipe.questions] == ["transport", "language"]
    assert resolve_recipe_capabilities(recipe, definitions) == (
        "python",
        "mcp-runtime",
        "fastapi",
    )


@pytest.mark.parametrize(
    ("transport", "prompt_input"),
    [("stdio", "\n\n"), ("streamable-http", "streamable-http\n\n")],
)
def test_init_mcp_server_generates_expected_project(
    tmp_path: Path, monkeypatch, transport: str, prompt_input: str
) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        app,
        ["init", "mcp-server", "--name", f"demo-{transport}", "--output", str(tmp_path / "output")],
        input=prompt_input,
    )

    assert result.exit_code == 0, result.output
    destination = tmp_path / "output" / f"demo-{transport}"
    expected_files = (
        "app/__init__.py",
        "app/server.py",
        "app/tools.py",
        "tests/test_server.py",
        "Dockerfile",
        "docker-compose.yml",
        ".env.example",
        "pyproject.toml",
        "README.md",
        ".metis/project.yaml",
    )
    assert all((destination / path).exists() for path in expected_files)

    metadata = yaml.safe_load((destination / ".metis/project.yaml").read_text())
    assert metadata["project"] == {"name": f"demo-{transport}", "recipe": "mcp-server"}
    assert metadata["selections"] == {"transport": transport, "language": "python"}
    assert "mcp-runtime" in metadata["capabilities"]
    assert ("fastapi" in metadata["capabilities"]) is (transport == "streamable-http")

    pyproject = tomllib.loads((destination / "pyproject.toml").read_text())
    dependencies = pyproject["project"]["dependencies"]
    assert any(str(value).startswith("mcp>=1.0,<2.0") for value in dependencies)
    compose = yaml.safe_load((destination / "docker-compose.yml").read_text())
    assert set(compose["services"]) == {"app"}
    if transport == "streamable-http":
        assert compose["services"]["app"]["ports"] == ["8000:8000"]
        assert "/mcp" in (destination / "README.md").read_text()
    else:
        assert "ports" not in compose["services"]["app"]
        assert "connect using stdio" in (destination / "README.md").read_text()
    assert "echo" in (destination / "app/server.py").read_text()


def test_mcp_http_compose_is_valid_when_docker_is_available(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        app,
        ["init", "mcp-server", "--name", "compose-mcp"],
        input="streamable-http\n\n",
    )
    assert result.exit_code == 0, result.output
    destination = tmp_path / "compose-mcp"
    if subprocess.run(["docker", "--version"], capture_output=True, check=False).returncode != 0:
        pytest.skip("Docker is not installed")
    check = subprocess.run(
        ["docker", "compose", "config", "--quiet"],
        cwd=destination,
        capture_output=True,
        text=True,
        check=False,
    )
    assert check.returncode == 0, check.stderr


def test_mcp_init_protects_existing_non_empty_target(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    destination = tmp_path / "existing"
    destination.mkdir()
    keep = destination / "keep.txt"
    keep.write_text("keep", encoding="utf-8")

    result = CliRunner().invoke(app, ["init", "mcp-server", "--name", "existing"], input="\n\n")

    assert result.exit_code == 1
    assert "non-empty" in result.output
    assert keep.read_text() == "keep"