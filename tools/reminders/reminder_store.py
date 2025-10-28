import os
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class ReminderStore:
    def __init__(self, user_id: str = "test_user", filepath: str = "reminders.json"):
        self.filepath = filepath
        self.user_id = user_id
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)

    # --- helpers ---
    @staticmethod
    def _short_title(text: str, max_len: int = 50) -> str:
        t = (text or "").strip()
        if not t:
            return "Напоминание"
        return t if len(t) <= max_len else t[:max_len - 1] + "…"

    @staticmethod
    def _normalize_dt(dt_str: str) -> str:
        """
        Принимает 'YYYY-MM-DD HH:MM' или ISO, возвращает ISO 'YYYY-MM-DDTHH:MM:SS'
        (без таймзоны; при желании можно добавить 'Z' или хранить локальную зону отдельно).
        """
        if not dt_str:
            # если времени нет — ставим через 5 минут
            return (datetime.now() + timedelta(minutes=5)).isoformat()
        try:
            # ISO-путь
            return datetime.fromisoformat(dt_str).isoformat()
        except ValueError:
            # старый формат без 'T'
            return datetime.strptime(dt_str, "%Y-%m-%d %H:%M").isoformat()

    def _load_all(self) -> List[Dict]:
        with open(self.filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_all(self, reminders: List[Dict]) -> None:
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(reminders, f, ensure_ascii=False, indent=2)

    # --- public API ---
    def save(self, reminder: Dict) -> Dict:
        """
        Принимает минимум: {"datetime": "...", "text": "..."}.
        Остальные поля достраивает сама.
        Можно передать user_id явно (например, из текущей сессии).
        """
        all_reminders = self._load_all()

        text = reminder.get("text", "")
        dt_iso = self._normalize_dt(reminder.get("datetime"))

        new_reminder = {
            "id": reminder.get("id") or str(uuid.uuid4()),
            "user_id": self.user_id,
            "title": reminder.get("title") or self._short_title(text, max_len=50),
            "text": text,
            "datetime": dt_iso,
            "created_at": reminder.get("created_at") or datetime.now().isoformat(),
            "repeat_weekly": reminder.get("repeat_weekly") or False,
            "done": bool(reminder.get("done", False)),
        }

        all_reminders.append(new_reminder)
        self._save_all(all_reminders)
        return new_reminder

    def get_due_reminders(self, now: Optional[datetime] = None) -> List[Dict]:
        now = now or datetime.now()
        out = []
        for r in self._load_all():
            if r.get("done"):
                continue
            try:
                dt = datetime.fromisoformat(r["datetime"])
            except Exception:
                # fallback на старый формат, если вдруг встретится
                dt = datetime.strptime(r["datetime"], "%Y-%m-%d %H:%M")
            if dt <= now:
                out.append(r)
        return out

    def mark_done(self, reminder_id: str) -> None:
        items = self._load_all()
        for r in items:
            if r["id"] == reminder_id:
                r["done"] = True
                break
        self._save_all(items)

    def delay_one_hour(self, reminder_id: str) -> None:
        items = self._load_all()
        for r in items:
            if r["id"] == reminder_id:
                try:
                    dt = datetime.fromisoformat(r["datetime"])
                except Exception:
                    dt = datetime.strptime(r["datetime"], "%Y-%m-%d %H:%M")
                r["datetime"] = (dt + timedelta(hours=1)).isoformat()
                r["done"] = False
                break
        self._save_all(items)


