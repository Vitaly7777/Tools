import logging
from pathlib import Path
from core.config import AppConfig


def setup_logging(config: AppConfig) -> None:
    handlers = []
    if config.LOG_FILE:
        handlers.append(logging.FileHandler(config.LOG_FILE, encoding="utf-8"))
    handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers
    )

    logging.getLogger("openpyxl").setLevel(logging.WARNING)
    
