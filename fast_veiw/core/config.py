import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppConfig:
    PREVIEW_ROWS: int = 100
    LOAD_LIMIT: int = 0
    STABLE_THRESHOLD: int = 10
    CACHE_MEMORY_LIMIT_MB: int = 2048
    SPARSITY_WARNING_RATIO: float = 0.5
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "app.log"

    @classmethod
    def from_file(cls, path: Path) -> "AppConfig":
        if not path.exists():
            return cls()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})
