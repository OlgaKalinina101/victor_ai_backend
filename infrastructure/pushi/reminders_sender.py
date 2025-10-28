from datetime import datetime

import requests
import os
from dotenv import load_dotenv

from infrastructure.firebase.reminders_sender import _load_reminders, REMINDERS_FILE, _save_reminders
from infrastructure.firebase.tokens import get_user_tokens
from infrastructure.logging.logger import setup_logger
from infrastructure.pushi.push_notifications import send_pushy_notification

logger = setup_logger("reminders_sender")

def check_and_send_reminders_pushi():
    items = _load_reminders()
    now = datetime.now()

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
                    # ✅ Заменили send_push на send_pushy_notification
                    msg_id = send_pushy_notification(
                        token=token,
                        title=r.get("title") or "Напоминание",
                        body=r.get("text") or "",
                        data={
                            "reminder_id": r["id"],
                            "title": "Напоминалка 🕊",  # ← дублируешь
                            "text": r.get("text")# ← дублируешь
                        }
                    )
                    logger.info(f"sent msg_id={msg_id} to token={token[:12]}…, text={r.get('text')}")
                except Exception as e:
                    logger.error(f"send error pushi token={token[:12]}… err={e}")

            r["done"] = True
            changed = True

    if changed:
        _save_reminders(items)
        logger.info("[reminders] saved updates")