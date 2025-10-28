from logging import Logger
from pathlib import Path

import yaml

def yaml_safe_load(yaml_path: Path, logger: Logger) -> dict:
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Ошибка загрузки {yaml_path}: {e}")
        return {}
