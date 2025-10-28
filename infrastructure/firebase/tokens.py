# core/firebase/tokens.py
import json
import logging
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger("pushi")

# Корень проекта = два уровня вверх от этого файла
PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOKENS_FILE = (PROJECT_ROOT / "tokens.json").resolve()

def _ensure_file():
    TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not TOKENS_FILE.exists():
        TOKENS_FILE.write_text("{}", encoding="utf-8")
        logger.info(f"Created tokens file at {TOKENS_FILE}")

def _load_tokens() -> Dict[str, List[str]]:
    _ensure_file()
    try:
        return json.loads(TOKENS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.exception(f"Failed to read {TOKENS_FILE}: {e}")
        return {}

def _save_tokens(tokens: Dict[str, List[str]]):
    try:
        TOKENS_FILE.write_text(json.dumps(tokens, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Saved tokens to {TOKENS_FILE}")
    except Exception as e:
        logger.exception(f"Failed to write {TOKENS_FILE}: {e}")

def save_device_token(user_id: str, token: str):
    tokens = _load_tokens()
    tokens.setdefault(user_id, [])
    if token not in tokens[user_id]:
        tokens[user_id].append(token)
        _save_tokens(tokens)
    else:
        logger.info("Token already exists; skipping")

def get_user_tokens(user_id: str):
    tokens = _load_tokens()
    return tokens.get(user_id, [])


