# INFRASTRUCTURE
from src.news.platform import Platform

_REGISTRY: dict[str, Platform] = {}


# FUNCTIONS

def register(platform: Platform) -> None:
    _REGISTRY[platform.name] = platform


def get(name: str) -> Platform:
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY.keys())) or "(none registered)"
        raise ValueError(f"Unknown platform {name!r}. Available: {available}")
    return _REGISTRY[name]
