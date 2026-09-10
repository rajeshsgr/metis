from pathlib import Path

from metis.capabilities import (
    load_capabilities,
    reconcile_capabilities,
    resolve_recipe_capabilities,
)
from metis.recipe import load_recipe


ROOT = Path(__file__).parents[1]
SCHEMA = ROOT / "schema/recipe.schema.json"
RECIPE = load_recipe(ROOT / "recipes/rag/recipe.yaml", SCHEMA)


def test_resolve_recipe_capabilities_expands_dependencies_and_deduplicates() -> None:
    definitions = load_capabilities(ROOT / "capabilities")

    resolved = resolve_recipe_capabilities(RECIPE, definitions)

    assert resolved == ("python", "fastapi", "llm", "embeddings", "vector-db")


def test_reconcile_capabilities_is_idempotent_for_existing_project() -> None:
    definitions = load_capabilities(ROOT / "capabilities")

    first = reconcile_capabilities(["rag"], ["python", "fastapi", "llm"], definitions)
    second = reconcile_capabilities(["rag"], ["python", "fastapi", "llm", "embeddings", "vector-db"], definitions)

    assert first.keep == ("python", "fastapi", "llm")
    assert first.add == ("embeddings", "vector-db")
    assert second.keep == ("python", "fastapi", "llm", "embeddings", "vector-db")
    assert second.add == ()


def test_supported_capabilities_exclude_observability() -> None:
    definitions = load_capabilities(ROOT / "capabilities")

    assert "observability" not in definitions
    assert "langfuse" not in definitions
