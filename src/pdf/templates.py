# INFRASTRUCTURE
from pathlib import Path

from src.pdf.report import WorkflowError

PROMPT_DIR = Path(__file__).parent / "prompts"


# FUNCTIONS
def read_template(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def substitute(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def require_filled(text: str) -> str:
    if "{{" in text:
        raise WorkflowError("prompt_placeholder", "prompt template has an unfilled placeholder")
    return text


def page_range(first: int, last: int) -> str:
    return str(first) if first == last else f"{first}-{last}"
