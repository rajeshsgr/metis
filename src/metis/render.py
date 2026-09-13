from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined


def iter_template_files(template_root: Path):
    for source in sorted(path for path in template_root.rglob("*") if path.is_file()):
        relative_path = source.relative_to(template_root)
        output_path = (
            relative_path.with_suffix("")
            if relative_path.suffix == ".j2"
            else relative_path
        )
        yield relative_path, output_path


def render_template_tree(template_root: Path, destination: Path, context: dict[str, str]) -> None:
    environment = Environment(
        loader=FileSystemLoader(template_root),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=False,
    )
    for relative_path, output_path in iter_template_files(template_root):
        target = destination / output_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            environment.get_template(relative_path.as_posix()).render(**context),
            encoding="utf-8",
        )