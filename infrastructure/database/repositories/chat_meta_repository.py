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

"""Репозиторий для работы с ChatMeta."""

from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from infrastructure.database.models import ChatMeta, TrackUserDescription
from infrastructure.logging.logger import setup_logger

logger = setup_logger("chat_meta_repository")


class ChatMetaRepository:
    """Репозиторий для работы с метаданными чата."""
    
    def __init__(self, session: Session):
        self.session = session

    def _seed_track_descriptions_from_template(
        self,
        *,
        account_id: str,
        template_account_id: str = "test_user",
    ) -> int:
        """
        Создаёт дефолтные TrackUserDescription для нового account_id,
        копируя данные из template_account_id (по умолчанию: test_user).

        Возвращает количество созданных записей.
        """
        if account_id == template_account_id:
            return 0

        template_rows = (
            self.session.query(TrackUserDescription)
            .filter(TrackUserDescription.account_id == template_account_id)
            .all()
        )
        if not template_rows:
            logger.warning(
                f"Не удалось seed TrackUserDescription: нет шаблонных записей "
                f"для template_account_id={template_account_id}"
            )
            return 0

        existing_track_ids = {
            row[0]
            for row in (
                self.session.query(TrackUserDescription.track_id)
                .filter(TrackUserDescription.account_id == account_id)
                .distinct()
                .all()
            )
        }

        created = 0
        seen_template_track_ids: set[int] = set()
        for t in template_rows:
            if t.track_id in seen_template_track_ids:
                continue
            seen_template_track_ids.add(t.track_id)

            if t.track_id in existing_track_ids:
                continue

            self.session.add(
                TrackUserDescription(
                    account_id=account_id,
                    track_id=t.track_id,
                    energy_description=t.energy_description,
                    temperature_description=t.temperature_description,
                )
            )
            created += 1

        if created:
            logger.info(
                f"Seed TrackUserDescription: создано {created} записей для account_id={account_id} "
                f"из template_account_id={template_account_id}"
            )
        return created

    def ensure_track_descriptions_seeded(
        self,
        *,
        account_id: str,
        template_account_id: str = "test_user",
    ) -> int:
        """
        Если у account_id нет НИ ОДНОЙ записи в TrackUserDescription,
        создаёт дефолтные записи (копия из template_account_id).

        Возвращает количество созданных записей (0 если ничего не делали).
        """
        # Не трогаем шаблонного пользователя
        if account_id == template_account_id:
            return 0

        # Если user вообще не существует — ничего не делаем (FK на chat_meta)
        if not self.get_by_account_id(account_id):
            logger.warning(
                f"ensure_track_descriptions_seeded: ChatMeta не найден для account_id={account_id}"
            )
            return 0

        has_any = (
            self.session.query(TrackUserDescription.id)
            .filter(TrackUserDescription.account_id == account_id)
            .limit(1)
            .first()
            is not None
        )
        if has_any:
            return 0

        created = self._seed_track_descriptions_from_template(
            account_id=account_id,
            template_account_id=template_account_id,
        )
        if created:
            # важно: без commit в "read-only" сценариях данные не сохранятся
            self.session.commit()
        return created
    
    def get_by_account_id(self, account_id: str) -> Optional[ChatMeta]:
        """
        Получает ChatMeta по account_id.
        
        Args:
            account_id: Идентификатор пользователя
            
        Returns:
            ChatMeta или None если не найдено
        """
        return self.session.query(ChatMeta).filter_by(account_id=account_id).first()
    
    def create_or_update(self, account_id: str, **fields) -> ChatMeta:
        """
        Создаёт или обновляет ChatMeta.
        
        Args:
            account_id: Идентификатор пользователя
            **fields: Поля для обновления
            
        Returns:
            Обновлённый или созданный объект ChatMeta
        """
        meta = self.get_by_account_id(account_id)
        
        if meta:
            # Обновляем существующую запись
            for key, value in fields.items():
                if hasattr(meta, key):
                    setattr(meta, key, value)
            meta.last_updated = datetime.utcnow().isoformat()
            logger.debug(f"Обновлён ChatMeta для {account_id}")
        else:
            # Создаём новую запись
            meta = ChatMeta(account_id=account_id, **fields)
            self.session.add(meta)
            # flush нужен, чтобы account_id появился в БД до вставки зависимых строк (FK на chat_meta)
            self.session.flush()
            self._seed_track_descriptions_from_template(account_id=account_id)
            logger.debug(f"Создан ChatMeta для {account_id}")
        
        self.session.commit()
        self.session.refresh(meta)
        return meta
    
    def update_partial(self, account_id: str, **fields) -> Optional[ChatMeta]:
        """
        Частично обновляет ChatMeta (PATCH-семантика).
        
        Args:
            account_id: Идентификатор пользователя
            **fields: Поля для обновления (только те, что переданы)
            
        Returns:
            Обновлённый ChatMeta или None если не найдено
        """
        meta = self.get_by_account_id(account_id)
        
        if not meta:
            logger.warning(f"ChatMeta не найден для {account_id}")
            return None
        
        # Применяем только переданные поля
        for key, value in fields.items():
            if hasattr(meta, key):
                setattr(meta, key, value)
        
        meta.last_updated = datetime.utcnow().isoformat()
        self.session.commit()
        self.session.refresh(meta)
        
        logger.debug(f"Частично обновлён ChatMeta для {account_id}: {list(fields.keys())}")
        return meta
    
    def exists(self, account_id: str) -> bool:
        """Проверяет существование ChatMeta."""
        return self.session.query(
            self.session.query(ChatMeta).filter_by(account_id=account_id).exists()
        ).scalar()


    def get_by_demo_key(self, demo_key: str) -> Optional[ChatMeta]:
        return self.session.query(ChatMeta).filter(ChatMeta.demo_key == demo_key).first()

    def exists_demo_key(self, demo_key: str) -> bool:
        return self.session.query(
            self.session.query(ChatMeta).filter(ChatMeta.demo_key == demo_key).exists()
        ).scalar()

