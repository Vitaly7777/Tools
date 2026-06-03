import json
from pathlib import Path
from core.config import AppConfig

def test_default_config():
    config = AppConfig()
    assert config.PREVIEW_ROWS == 100
    assert config.LOAD_LIMIT == 0

def test_from_file(tmp_path):
    data = {"PREVIEW_ROWS": 50, "LOG_LEVEL": "DEBUG"}
    p = tmp_path / "config.json"
    p.write_text(json.dumps(data))
    config = AppConfig.from_file(p)
    assert config.PREVIEW_ROWS == 50
    assert config.LOG_LEVEL == "DEBUG"
    assert config.LOAD_LIMIT == 0  # дефолт

def test_from_missing_file(tmp_path):
    config = AppConfig.from_file(tmp_path / "nonexistent.json")
    assert config.PREVIEW_ROWS == 100
