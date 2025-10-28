import yaml
from pathlib import Path
from datetime import datetime, timedelta, timezone
from .session_context_schema import SessionContext, from_yaml_dict, to_serializable
from sqlalchemy.orm import Session

from ..database.repositories import save_session_context_as_history
from ..logging.logger import setup_logger

logger = setup_logger("session_context_store")

class SessionContextStore:
    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, account_id: str) -> Path:
        return self.storage_path / f"{account_id}.yaml"

    def load(self, account_id: str, db_session: Session) -> SessionContext:
        file_path = self._get_file_path(account_id)
        logger.info(f"[session_context_store] file_path: {file_path}")

        if not file_path.exists():
            logger.info(f"[session_context_store] file not found: {file_path}")
            return self._create_default_context(account_id, db_session=db_session)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_data = yaml.safe_load(f)

            if raw_data is None:
                logger.warning(f"[session_context_store] YAML-файл {file_path} пуст, создаётся новый контекст.")
                return self._create_default_context(account_id, db_session=db_session)


            # Преобразуем в сериализуемый словарь
            parsed_data = from_yaml_dict(raw_data)

            # Проверим, все ли критичные поля присутствуют
            required_fields = ["gender", "relationship_level", "trust_level", "is_creator", "model"]
            if not all(field in parsed_data for field in required_fields):
                logger.warning(
                    "[session_context_store] YAML context не содержит всех полей user_profile, достраиваем из БД.")
                return SessionContext.empty(
                    account_id=parsed_data.get("account_id", account_id),
                    last_update=parsed_data.get("last_update", datetime.utcnow()),
                    db_session=db_session,
                    **parsed_data
                )

            return SessionContext(**parsed_data)

        except Exception as e:
            logger.error(f"[session_context_store] Ошибка при загрузке YAML-контекста: {e}", exc_info=True)
            return self._create_default_context(account_id, db_session=db_session)


    def save(self, context: SessionContext):
        """Сохраняет контекст в YAML."""
        file_path = self._get_file_path(context.account_id)
        file_path.parent.mkdir(parents=True, exist_ok=True)  # чтобы не падал
        context.last_update = datetime.now()
        logger.info(f"Saving {context.account_id} to {file_path}")

        with open(file_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(to_serializable(context), f, allow_unicode=True)
            logger.info(f"Saved {context.account_id} to {file_path}")

    def _create_default_context(self, account_id: str, db_session: Session) -> SessionContext:
        logger.info(f"Creating default context for {account_id} using DB fallback")
        return SessionContext.empty(
            account_id=account_id,
            last_update=datetime.utcnow(),
            db_session=db_session,
        )

def is_session_stale(context_dict: dict, hours: int = 6) -> bool:
    """
    Проверяет, сколько прошло времени с last_update.
    Возвращает True, если сессия устарела (по умолчанию > 6 часов).
    """
    try:
        raw = context_dict.get("last_update")
        if not raw:
            return True

        last_update = datetime.fromisoformat(raw)

        # Приводим оба к одному виду (timezone-aware UTC)
        if last_update.tzinfo is None:
            last_update = last_update.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)

        return (now - last_update) > timedelta(hours=hours)

    except Exception as e:
        print(f"[ERROR] Не удалось распарсить last_update: {e}")
        return True

