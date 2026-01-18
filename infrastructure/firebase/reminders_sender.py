# Victor AI - Personal AI Companion for Android
# Copyright (C) 2025-2026 Olga Kalinina

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.

from datetime import datetime
from pathlib import Path
import json
from infrastructure.firebase.tokens import get_user_tokens
from infrastructure.firebase.client import send_push  # ваш v1-отправитель
from infrastructure.logging.logger import setup_logger

logger=setup_logger("reminders")

REMINDERS_FILE = (Path(__file__).resolve().parents[2] / "reminders.json").resolve()

def _load_reminders() -> list:
    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"load error {REMINDERS_FILE}: {e}")
        return []

def _save_reminders(items: list):
    try:
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"save error {REMINDERS_FILE}: {e}")

def check_and_send_reminders():
    items = _load_reminders()
    now = datetime.now()  # сравниваем локально с локальным

    logger.debug(f"file={REMINDERS_FILE}")
    logger.debug(f"now={now.isoformat()} items={len(items)}")

    changed = False
    for r in items:
        if r.get("done"):
            logger.debug(f"skip done id={r.get('id')}")
            continue

        dt_str = r.get("datetime")
        if not dt_str:
            logger.debug(f"skip no-datetime id={r.get('id')}")
            continue

        try:
            try:
                due = datetime.fromisoformat(dt_str)
            except ValueError:
                due = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        except Exception as e:
            logger.error(f"bad datetime id={r.get('id')} val={dt_str} err={e}")
            continue

        logger.debug(f"id={r.get('id')} due={due.isoformat()} <= now? {due <= now}")

        if due <= now:
            user_id = r.get("user_id", "default_user")
            tokens = get_user_tokens(user_id)
            logger.info(f"DUE! user={user_id} tokens={tokens}")

            for token in tokens:
                try:
                    msg_id = send_push(
                        token=token,
                        title=r.get("title") or "Напоминание",
                        body=r.get("text") or "",
                        data={
                            "reminder_id": r["id"],
                            "title": r.get("title") or "Напоминание",
                            "text": r.get("text") or ""
                        }
                    )
                    logger.info(f"sent msg_id={msg_id} to token={token[:12]}…")
                except Exception as e:
                    logger.error(f"send error firebase token={token[:12]}… err={e}")

            r["done"] = True
            changed = True

    if changed:
        _save_reminders(items)
        logger.info("[reminders] saved updates")

