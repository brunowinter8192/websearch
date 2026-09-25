# INFRASTRUCTURE
from src.news.platform import Platform
from src.news.platforms.coindesk import CoinDeskPlatform
from src.news.platforms.theblock import TheBlockPlatform

PLATFORM_CLASSES = (CoinDeskPlatform, TheBlockPlatform)


# FUNCTIONS

def get(name: str) -> Platform:
    for platform_class in PLATFORM_CLASSES:
        if platform_class.name == name:
            return platform_class()
    available = ", ".join(sorted(cls.name for cls in PLATFORM_CLASSES)) or "(none registered)"
    raise ValueError(f"Unknown platform {name!r}. Available: {available}")
