from pathlib import Path
import shutil
import subprocess

import pytest
import yaml

from metis.generator import GenerationError, generate_project
from metis.models import Recipe
from metis.questions import resolve_questions
from metis.recipe import load_recipe


ROOT = Path(__file__).parents[1]
RECIPE = load_recipe(ROOT / "recipes/rag/recipe.yaml", ROOT / "schema/recipe.schema.json")


def answers(vector_db: str = "qdrant", llm: str = "openai", embedding: str = "openai") -> dict[str, str]:
    return {
        "vector_db": vector_db,
        "llm": llm,
        "embedding": embedding,
        "framework": "fastapi",
    }


def test_question_answers_are_exposed_to_templates() -> None:
    prompts = iter(["chroma", "anthropic", "huggingface", "fastapi"])
    resolved = resolve_questions(RECIPE.questions, lambda *_args, **_kwargs: next(prompts))
    assert resolved == answers("chroma", "anthropic", "huggingface")


def test_generates_rag_project_with_selected_options(tmp_path: Path) -> None:
    destination = generate_project(RECIPE, "demo", tmp_path, answers("chroma", "anthropic", "huggingface"))

    template_files = [path for path in RECIPE.template_path.rglob("*") if path.is_file()]
    assert all(path.suffix == ".j2" for path in template_files)
    assert (destination / "app/main.py").exists()
    assert (destination / "tests/test_health.py").exists()
    compose = (destination / "docker-compose.yml").read_text()
    assert not (destination / "docker-compose.yml.j2").exists()
    assert "chroma:" in compose
    compose_data = yaml.safe_load(compose)
    assert set(compose_data["services"]) == {"app", "chroma"}
    assert compose_data["services"]["chroma"]["image"] == "chromadb/chroma:latest"
    assert compose_data["services"]["app"]["build"] == "."
    assert compose_data["services"]["app"]["ports"] == ["8000:8000"]
    assert compose_data["services"]["app"]["env_file"][0]["path"] == ".env"
    assert compose_data["services"]["app"]["depends_on"] == ["chroma"]
    assert "EXPOSE 8000" in (destination / "Dockerfile").read_text()
    assert "uvicorn" in (destination / "Dockerfile").read_text()
    assert "anthropic>=0.30" in (destination / "pyproject.toml").read_text()
    env = (destination / ".env.example").read_text()
    assert "ANTHROPIC_API_KEY=" in env
    assert "HUGGINGFACE_API_KEY=" in env
    assert "my-rag-app" not in (destination / "README.md").read_text()
    generated_files = [path for path in destination.rglob("*") if path.is_file()]
    assert all(path.suffix != ".j2" for path in generated_files)
    assert all(
        "{{" not in path.read_text(encoding="utf-8")
        and "{%" not in path.read_text(encoding="utf-8")
        for path in generated_files
    )

    metadata = yaml.safe_load((destination / ".metis/project.yaml").read_text())
    assert metadata == {
        "schemaVersion": 1,
        "metisVersion": "0.1.0",
        "project": {"name": "demo", "recipe": "rag"},
        "selections": {
            "vector_db": "chroma",
            "llm": "anthropic",
            "embedding": "huggingface",
            "framework": "fastapi",
        },
        "capabilities": ["python", "fastapi", "llm", "embeddings", "vector-db"],
    }


def test_metadata_deduplicates_capabilities_and_excludes_sensitive_answers(tmp_path: Path) -> None:
    recipe = Recipe(
        api_version=RECIPE.api_version,
        kind=RECIPE.kind,
        name=RECIPE.name,
        version=RECIPE.version,
        description=RECIPE.description,
        template_path=RECIPE.template_path,
        questions=RECIPE.questions,
        capabilities=("python", "python", "fastapi"),
    )
    destination = generate_project(
        recipe,
        "metadata-check",
        tmp_path,
        {**answers(), "OPENAI_API_KEY": "do-not-write"},
    )

    metadata = yaml.safe_load((destination / ".metis/project.yaml").read_text())
    assert metadata["capabilities"] == ["python", "fastapi"]
    assert "OPENAI_API_KEY" not in metadata["selections"]


@pytest.mark.parametrize("vector_db", ["qdrant", "chroma"])
def test_docker_compose_config_succeeds_for_selected_vector_db(
    tmp_path: Path, vector_db: str
) -> None:
    if shutil.which("docker") is None:
        pytest.skip("Docker is not installed")

    destination = generate_project(RECIPE, "compose-check", tmp_path, answers(vector_db))
    result = subprocess.run(
        ["docker", "compose", "config", "--quiet"],
        cwd=destination,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_does_not_overwrite_non_empty_directory(tmp_path: Path) -> None:
    destination = tmp_path / "demo"
    destination.mkdir()
    existing = destination / "keep.txt"
    existing.write_text("user content", encoding="utf-8")

    with pytest.raises(GenerationError, match="non-empty"):
        generate_project(RECIPE, "demo", tmp_path, answers())
    assert existing.read_text(encoding="utf-8") == "user content"


def test_invalid_recipe_fails_before_generation(tmp_path: Path) -> None:
    invalid_recipe = tmp_path / "recipe.yaml"
    invalid_recipe.write_text("kind: invalid\n", encoding="utf-8")
    with pytest.raises(Exception):
        load_recipe(invalid_recipe, ROOT / "schema/recipe.schema.json")
    assert not (tmp_path / "created").exists()