import re
from pathlib import Path

import yaml

from . import __version__
from .models import Recipe


_SENSITIVE_KEY = re.compile(r"(?:secret|password|token|api[-_]?key|credential)", re.IGNORECASE)


def write_project_metadata(
    destination: Path,
    recipe: Recipe,
    project_name: str,
    answers: dict[str, str],
) -> None:
    selections = {
        question.id: answers[question.id]
        for question in recipe.questions
        if question.id in answers and not _SENSITIVE_KEY.search(question.id)
    }
    capabilities = list(dict.fromkeys(recipe.capabilities))
    if recipe.name == "mcp-server" and answers.get("transport") != "streamable-http":
        capabilities = [capability for capability in capabilities if capability != "fastapi"]
    metadata = {
        "schemaVersion": 1,
        "metisVersion": __version__,
        "project": {
            "name": project_name,
            "recipe": recipe.name,
        },
        "selections": selections,
        "capabilities": capabilities,
    }

    metadata_path = destination / ".metis" / "project.yaml"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        yaml.safe_dump(metadata, sort_keys=False),
        encoding="utf-8",
    )