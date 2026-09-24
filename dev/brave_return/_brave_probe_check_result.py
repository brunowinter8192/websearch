# FUNCTIONS

def check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise AssertionError(f"{name} {detail}".strip())
