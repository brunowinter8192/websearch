# INFRASTRUCTURE
_failures: list[str] = []


# FUNCTIONS

def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"PASS {name}")
        return
    _failures.append(f"{name} {detail}".strip())
    print(f"FAIL {name} {detail}".strip())


def report_outcome() -> int:
    print("")
    if _failures:
        print(f"{len(_failures)} CHECK(S) FAILED")
        for failure in _failures:
            print(f"  - {failure}")
        return 1
    print("ALL CHECKS PASSED")
    return 0
