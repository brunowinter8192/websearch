# INFRASTRUCTURE
import sys
from collections import Counter

REJECTIONS = Counter()


# FUNCTIONS

def record_rejection(exc: Exception) -> None:
    REJECTIONS[type(exc).__name__] += 1


def print_rejections() -> None:
    print(f"proxy check rejections: {dict(REJECTIONS)}", file=sys.stderr)
