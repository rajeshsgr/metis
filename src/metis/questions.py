from collections.abc import Callable

from .models import Question


def resolve_questions(
    questions: tuple[Question, ...],
    prompt: Callable[..., str],
) -> dict[str, str]:
    answers: dict[str, str] = {}
    for question in questions:
        if question.type != "select":
            raise ValueError(f"unsupported question type: {question.type}")
        default = question.default or question.options[0]
        while True:
            value = prompt(
                f"{question.message} ({'/'.join(question.options)})",
                default=default,
            )
            if value in question.options:
                answers[question.id] = value
                break
    return answers