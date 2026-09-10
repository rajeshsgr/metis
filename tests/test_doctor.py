from pathlib import Path
import subprocess

from typer.testing import CliRunner

from metis.cli import app
from metis.doctor import DoctorCheck, DoctorReport, format_doctor, run_doctor
from metis.generator import generate_project
from metis.recipe import load_recipe


ROOT = Path(__file__).parents[1]
SCHEMA = ROOT / "schema/recipe.schema.json"
RAG_RECIPE = load_recipe(ROOT / "recipes/rag/recipe.yaml", SCHEMA)
AGENT_RECIPE = load_recipe(ROOT / "recipes/agent/recipe.yaml", SCHEMA)


def command_runner(command, cwd):
    return subprocess.CompletedProcess(command, 0, "ok", "")


def healthy_http(url: str) -> tuple[bool, str]:
    return True, "reachable"


def healthy_redis(host: str, port: int) -> tuple[bool, str]:
    return True, "reachable"


def test_doctor_uses_chroma_published_port_and_v2_heartbeat(
    tmp_path: Path,
) -> None:
    destination = generate_project(
        RAG_RECIPE,
        "chroma-doctor",
        tmp_path,
        {"vector_db": "chroma", "llm": "openai", "embedding": "openai", "framework": "fastapi"},
    )
    urls: list[str] = []

    def recording_http(url: str) -> tuple[bool, str]:
        urls.append(url)
        return True, "reachable"

    report = run_doctor(destination, command_runner, recording_http, healthy_redis)

    assert next(check for check in report.checks if check.name == "Chroma reachable").passed
    assert "http://localhost:8001/api/v2/heartbeat" in urls
    assert "http://localhost:8001/api/v1/heartbeat" not in urls


def test_doctor_reports_unreachable_chroma(tmp_path: Path) -> None:
    destination = generate_project(
        RAG_RECIPE,
        "unreachable-chroma",
        tmp_path,
        {"vector_db": "chroma", "llm": "openai", "embedding": "openai", "framework": "fastapi"},
    )

    def unreachable_http(url: str) -> tuple[bool, str]:
        if url == "http://localhost:8001/api/v2/heartbeat":
            return False, "connection refused"
        return True, "reachable"

    report = run_doctor(destination, command_runner, unreachable_http, healthy_redis)

    assert any(
        check.name == "Chroma reachable" and not check.passed
        for check in report.checks
    )


def test_doctor_reports_healthy_rag_and_selected_checks(
    tmp_path: Path, monkeypatch
) -> None:
    destination = generate_project(
        RAG_RECIPE,
        "doctor-rag",
        tmp_path,
        {"vector_db": "qdrant", "llm": "openai", "embedding": "openai", "framework": "fastapi"},
    )
    monkeypatch.setenv("OPENAI_API_KEY", "secret-openai-value")

    report = run_doctor(destination, command_runner, healthy_http, healthy_redis)
    output = format_doctor(report)
    names = [check.name for check in report.checks]

    assert not report.failures
    assert "Docker available" in names
    assert "Docker Compose available" in names
    assert "Compose configuration valid" in names
    assert "Application reachable" in names
    assert "Qdrant reachable" in names
    assert "Chroma reachable" not in names
    assert "Redis reachable" not in names
    assert "OPENAI_API_KEY" in output
    assert "secret-openai-value" not in output


def test_doctor_reports_healthy_agent_and_preserves_capability_awareness(
    tmp_path: Path, monkeypatch
) -> None:
    destination = generate_project(
        AGENT_RECIPE,
        "doctor-agent",
        tmp_path,
        {
            "llm": "anthropic",
            "agent_runtime": "langgraph",
            "state": "redis",
            "framework": "fastapi",
        },
    )
    for name in ("ANTHROPIC_API_KEY", "REDIS_URL"):
        monkeypatch.setenv(name, f"secret-{name.lower()}")

    report = run_doctor(destination, command_runner, healthy_http, healthy_redis)
    names = [check.name for check in report.checks]

    assert not report.failures
    assert "Redis reachable" in names
    assert "Qdrant reachable" not in names
    assert "Chroma reachable" not in names
    assert "OPENAI_API_KEY" not in names
    assert "HUGGINGFACE_API_KEY" not in names


def test_doctor_reports_services_not_running_and_returns_failure(tmp_path: Path, monkeypatch) -> None:
    destination = generate_project(
        RAG_RECIPE,
        "stopped-rag",
        tmp_path,
        {"vector_db": "chroma", "llm": "openai", "embedding": "huggingface", "framework": "fastapi"},
    )
    monkeypatch.setenv("OPENAI_API_KEY", "configured")
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "configured")

    def unreachable_http(url: str) -> tuple[bool, str]:
        return False, "connection refused"

    def unreachable_redis(host: str, port: int) -> tuple[bool, str]:
        return False, "connection refused"

    report = run_doctor(destination, command_runner, unreachable_http, unreachable_redis)

    assert report.failures
    assert any(check.name == "Application reachable" for check in report.failures)
    assert any(check.name == "Chroma reachable" for check in report.failures)


def test_doctor_checks_only_selected_environment_variables(tmp_path: Path, monkeypatch) -> None:
    destination = generate_project(
        RAG_RECIPE,
        "missing-env-rag",
        tmp_path,
        {"vector_db": "qdrant", "llm": "anthropic", "embedding": "huggingface", "framework": "fastapi"},
    )
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "unselected-secret")

    report = run_doctor(destination, command_runner, healthy_http, healthy_redis)
    output = format_doctor(report)

    assert {check.name for check in report.failures} == {"ANTHROPIC_API_KEY", "HUGGINGFACE_API_KEY"}
    assert "OPENAI_API_KEY" not in output
    assert "unselected-secret" not in output


def test_doctor_cli_returns_nonzero_and_does_not_mutate_project(
    tmp_path: Path, monkeypatch
) -> None:
    destination = generate_project(
        RAG_RECIPE,
        "readonly-rag",
        tmp_path,
        {"vector_db": "qdrant", "llm": "openai", "embedding": "openai", "framework": "fastapi"},
    )
    before = {
        path.relative_to(destination): path.read_bytes()
        for path in destination.rglob("*")
        if path.is_file()
    }
    monkeypatch.chdir(destination)
    report = DoctorReport((DoctorCheck("OPENAI_API_KEY", False, "missing"),))
    monkeypatch.setattr("metis.cli.run_doctor", lambda _path: report)

    result = CliRunner().invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "OPENAI_API_KEY" in result.output
    assert {path.relative_to(destination): path.read_bytes() for path in destination.rglob("*") if path.is_file()} == before