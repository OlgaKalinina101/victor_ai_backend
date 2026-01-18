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

"""Репозиторий для работы с DialogueHistory."""

import json
import uuid
from typing import List, Optional, Tuple, Dict
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func

from infrastructure.database.models import DialogueHistory
from infrastructure.logging.logger import setup_logger

logger = setup_logger("dialogue_repository")


class DialogueRepository:
    """
    Репозиторий для работы с историей диалогов.
    
    Инкапсулирует всю логику работы с DialogueHistory:
    - Сохранение сообщений
    - Пагинация истории
    - Поиск по тексту
    - Получение контекста вокруг сообщения
    - Работа с emoji
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    def save_message(
        self,
        account_id: str,
        role: str,
        text: str,
        dialogue_id: Optional[str] = None,
        emoji: Optional[str] = None,
        mood: Optional[str] = None,
        message_type: Optional[str] = None,
        message_category: Optional[str] = None,
        focus_points: Optional[str] = None,
        has_strong_focus: Optional[str] = None,
        anchor_link: Optional[str] = None,
        has_strong_anchor: Optional[bool] = None,
        memories: Optional[str] = None,
        anchor: Optional[str] = None,
        vision_context: Optional[str] = None,
        swiped_message_id: Optional[int] = None,
        swiped_message_text: Optional[str] = None,
    ) -> DialogueHistory:
        """
        Сохраняет одно сообщение в историю диалога.
        
        Args:
            account_id: ID аккаунта пользователя
            role: Роль отправителя ('user' или 'assistant')
            text: Текст сообщения
            dialogue_id: ID диалога (опционально)
            emoji: Эмодзи связанное с сообщением (опционально)
            mood: Настроение (из victor_mood_history)
            message_type: Тип сообщения (из victor_impressive_history)
            message_category: Категория сообщения
            focus_points: JSON строка с фокус-точками
            has_strong_focus: JSON строка с флагами сильного фокуса
            anchor_link: Эмоциональный якорь
            has_strong_anchor: Флаг сильного якоря
            memories: JSON строка с воспоминаниями
            anchor: Якорь
            vision_context: Контекст изображения (если было отправлено)
            
        Returns:
            Созданная запись DialogueHistory
        """
        message = DialogueHistory(
            account_id=account_id,
            dialogue_id=dialogue_id,
            role=role,
            text=text,
            emoji=emoji,
            mood=mood,
            message_type=message_type,
            message_category=message_category,
            focus_points=focus_points,
            has_strong_focus=has_strong_focus,
            anchor_link=anchor_link,
            has_strong_anchor=has_strong_anchor,
            memories=memories,
            anchor=anchor,
            vision_context=vision_context,
            swiped_message_id=swiped_message_id,
            swiped_message_text=swiped_message_text,
            created_at=datetime.utcnow(),
        )
        
        self.session.add(message)
        self.session.commit()
        self.session.refresh(message)
        
        logger.debug(f"Сохранено сообщение id={message.id} для {account_id}, role={role}, emoji={emoji}")
        return message
    
    def get_paginated(
        self,
        account_id: str,
        limit: int = 25,
        before_id: Optional[int] = None
    ) -> Tuple[List[DialogueHistory], bool]:
        """
        Получает историю диалога с пагинацией.
        
        Args:
            account_id: ID пользователя
            limit: Количество сообщений для загрузки
            before_id: ID сообщения, до которого загружать (для скролла вверх)
            
        Returns:
            Tuple (список сообщений, есть ли еще сообщения)
            Сообщения возвращаются в порядке от старых к новым.
        """
        query = self.session.query(DialogueHistory).filter(
            DialogueHistory.account_id == account_id
        )
        
        if before_id is not None:
            query = query.filter(DialogueHistory.id < before_id)
        
        # Сортируем по id в обратном порядке (новые первыми)
        query = query.order_by(desc(DialogueHistory.id))
        
        # Берем limit + 1 для проверки наличия еще записей
        messages = query.limit(limit + 1).all()
        
        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]
        
        # Возвращаем в прямом порядке (старые первыми)
        messages.reverse()
        
        logger.debug(f"Загружено {len(messages)} сообщений для {account_id}, before_id={before_id}, has_more={has_more}")
        return messages, has_more
    
    def search(
        self,
        account_id: str,
        query_text: str,
        offset: int = 0
    ) -> Tuple[List[DialogueHistory], int]:
        """
        Поиск сообщений по тексту с пагинацией.
        
        Args:
            account_id: ID пользователя
            query_text: Поисковый запрос
            offset: Смещение для навигации по результатам
            
        Returns:
            Tuple (список найденных сообщений, общее количество найденных)
            Возвращается одно сообщение с указанным offset.
        """
        # Общий запрос для подсчета
        base_query = self.session.query(DialogueHistory).filter(
            DialogueHistory.account_id == account_id,
            DialogueHistory.text.ilike(f"%{query_text}%")
        )
        
        # Подсчитываем общее количество
        total_count = base_query.count()
        
        # Получаем конкретное сообщение с offset
        results = base_query.order_by(desc(DialogueHistory.created_at)).offset(offset).limit(1).all()
        
        logger.debug(f"Найдено {total_count} совпадений для '{query_text}', возвращен offset={offset}")
        return results, total_count
    
    def get_context(
        self,
        account_id: str,
        message_id: int,
        context_before: int = 10,
        context_after: int = 10
    ) -> List[DialogueHistory]:
        """
        Получает контекст вокруг конкретного сообщения.
        
        Args:
            account_id: ID пользователя
            message_id: ID целевого сообщения
            context_before: Количество сообщений до целевого
            context_after: Количество сообщений после целевого
            
        Returns:
            Список сообщений от старых к новым, включая целевое
        """
        # Получаем сообщения ДО целевого
        before_messages = self.session.query(DialogueHistory).filter(
            DialogueHistory.account_id == account_id,
            DialogueHistory.id < message_id
        ).order_by(desc(DialogueHistory.id)).limit(context_before).all()
        
        before_messages.reverse()  # От старых к новым
        
        # Получаем целевое сообщение
        target_message = self.session.query(DialogueHistory).filter(
            DialogueHistory.account_id == account_id,
            DialogueHistory.id == message_id
        ).first()
        
        # Получаем сообщения ПОСЛЕ целевого
        after_messages = self.session.query(DialogueHistory).filter(
            DialogueHistory.account_id == account_id,
            DialogueHistory.id > message_id
        ).order_by(asc(DialogueHistory.id)).limit(context_after).all()
        
        # Объединяем
        if target_message:
            result = before_messages + [target_message] + after_messages
        else:
            result = before_messages + after_messages
        
        logger.debug(f"Загружен контекст: {len(before_messages)} до + {len(after_messages)} после = {len(result)} всего")
        return result
    
    def get_by_id(self, message_id: int) -> Optional[DialogueHistory]:
        """
        Получает сообщение по ID.
        
        Args:
            message_id: ID сообщения
            
        Returns:
            DialogueHistory или None если не найдено
        """
        return self.session.query(DialogueHistory).filter_by(id=message_id).first()
    
    def update_emoji(self, account_id: str, message_id: int, emoji: Optional[str]) -> Optional[DialogueHistory]:
        """
        Обновляет emoji для сообщения с проверкой владельца.
        
        Args:
            account_id: ID аккаунта пользователя (для проверки прав доступа)
            message_id: ID сообщения
            emoji: Новое emoji (или None для удаления)
            
        Returns:
            Обновленное сообщение или None если не найдено или не принадлежит пользователю
        """
        # Получаем сообщение с проверкой account_id
        message = self.session.query(DialogueHistory).filter(
            DialogueHistory.id == message_id,
            DialogueHistory.account_id == account_id
        ).first()
        
        if not message:
            logger.warning(f"Сообщение id={message_id} не найдено для account_id={account_id}")
            return None
        
        old_emoji = message.emoji
        message.emoji = emoji
        
        self.session.commit()
        self.session.refresh(message)
        
        logger.info(f"Обновлено emoji для сообщения id={message_id} (account_id={account_id}): '{old_emoji}' → '{emoji}'")
        return message
    
    def update_message_text(self, account_id: str, message_id: int, new_text: str) -> Optional[DialogueHistory]:
        """
        Обновляет текст сообщения с проверкой владельца.
        
        Args:
            account_id: ID аккаунта пользователя (для проверки прав доступа)
            message_id: ID сообщения
            new_text: Новый текст сообщения
            
        Returns:
            Обновленное сообщение или None если не найдено или не принадлежит пользователю
        """
        # Получаем сообщение с проверкой account_id
        message = self.session.query(DialogueHistory).filter(
            DialogueHistory.id == message_id,
            DialogueHistory.account_id == account_id
        ).first()
        
        if not message:
            logger.warning(f"Сообщение id={message_id} не найдено для account_id={account_id}")
            return None
        
        old_text = message.text[:50] + "..." if len(message.text) > 50 else message.text
        message.text = new_text
        
        self.session.commit()
        self.session.refresh(message)
        
        new_text_short = new_text[:50] + "..." if len(new_text) > 50 else new_text
        logger.info(f"Обновлён текст сообщения id={message_id} (account_id={account_id}): '{old_text}' → '{new_text_short}'")
        return message
    
    def get_messages_with_emoji(
        self,
        account_id: str,
        emoji: str,
        limit: int = 50
    ) -> List[DialogueHistory]:
        """
        Получает все сообщения с определенным emoji.
        
        Args:
            account_id: ID пользователя
            emoji: Искомое emoji
            limit: Максимальное количество результатов
            
        Returns:
            Список сообщений от новых к старым
        """
        messages = self.session.query(DialogueHistory).filter(
            DialogueHistory.account_id == account_id,
            DialogueHistory.emoji == emoji
        ).order_by(desc(DialogueHistory.created_at)).limit(limit).all()
        
        logger.debug(f"Найдено {len(messages)} сообщений с emoji '{emoji}' для {account_id}")
        return messages
    
    def get_count(self, account_id: str) -> int:
        """
        Возвращает общее количество сообщений пользователя.
        
        Args:
            account_id: ID пользователя
            
        Returns:
            Количество сообщений
        """
        count = self.session.query(func.count(DialogueHistory.id)).filter(
            DialogueHistory.account_id == account_id
        ).scalar()
        
        return count or 0
    
    def delete_message(self, message_id: int) -> bool:
        """
        Удаляет сообщение по ID.
        
        Args:
            message_id: ID сообщения
            
        Returns:
            True если удалено, False если не найдено
        """
        message = self.get_by_id(message_id)
        
        if not message:
            logger.warning(f"Сообщение id={message_id} не найдено для удаления")
            return False
        
        self.session.delete(message)
        self.session.commit()
        
        logger.info(f"Удалено сообщение id={message_id}")
        return True
    
    def save_session_context_as_history(self, context_dict: dict) -> None:
        """
        Сохраняет содержимое session_context (в виде словаря) в таблицу DialogueHistory.
        Все anchor и focus сохраняются целиком, без парсинга.
        
        Args:
            context_dict: Словарь с session context (message_history, mood_history, etc)
        """
        dialogue_id = str(uuid.uuid4())
        
        try:
            raw_messages = context_dict.get("message_history", [])
            
            # Парсим сообщения: определяем роль из префикса и убираем его
            messages = []
            roles = []
            for msg in raw_messages:
                if msg.startswith("user: "):
                    roles.append("user")
                    messages.append(msg[6:])  # убираем "user: "
                elif msg.startswith("assistant: "):
                    roles.append("assistant")
                    messages.append(msg[11:])  # убираем "assistant: "
                else:
                    # Fallback: если префикса нет, пытаемся определить по контексту
                    # или используем предыдущую роль (инвертированную)
                    prev_role = roles[-1] if roles else "assistant"
                    roles.append("user" if prev_role == "assistant" else "assistant")
                    messages.append(msg)
            
            mood_list = context_dict.get("victor_mood_history", [])
            impressive_list = context_dict.get("victor_impressive_history", [])
            intensity_list = context_dict.get("victor_intensity_history", [])
            category_list = context_dict.get("message_category_history", [])
            
            anchor_block = json.dumps(context_dict.get("anchor_link_history", []))
            focus_block = json.dumps(context_dict.get("focus_points_history", []))
            mem_text = json.dumps(context_dict.get("key_info_history", []))
            
            account_id = context_dict.get("account_id", "unknown")
            
            for i, (role, text) in enumerate(zip(roles, messages)):
                mood = mood_list[i] if i < len(mood_list) else None
                impressive = impressive_list[i] if i < len(impressive_list) else None
                intensity = intensity_list[i] if i < len(intensity_list) else None
                category = category_list[i] if i < len(category_list) else None
                
                record = DialogueHistory(
                    account_id=account_id,
                    dialogue_id=dialogue_id,
                    role=role,
                    text=text,
                    mood=mood,
                    message_type=None,
                    message_category=category,
                    focus_points=focus_block,
                    has_strong_focus=None,
                    anchor_link=anchor_block,
                    has_strong_anchor=None,
                    memories=mem_text,
                    anchor=None,
                    created_at=datetime.utcnow(),
                )
                self.session.add(record)
            
            self.session.commit()
            logger.info(f"Сохранено {len(messages)} сообщений из session_context, dialogue_id={dialogue_id}")
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Ошибка при сохранении session_context как истории: {e}")
            raise
    
    def merge_session_and_db_history(
        self,
        session_context: dict,
        db_messages: List[DialogueHistory]
    ) -> List[Dict]:
        """
        Мержит SessionContext и БД, убирая дубли по (text, role).
        
        Args:
            session_context: Словарь с session context
            db_messages: Список сообщений из БД
            
        Returns:
            Список словарей с объединёнными сообщениями без дублей
        """
        # 1. Парсим SessionContext
        session_msgs = []
        for msg in session_context.get("message_history", []):
            if ":" in msg:
                role, text = msg.split(":", 1)
                session_msgs.append({
                    "role": role.strip(),
                    "text": text.strip(),
                    "source": "session",
                    "id": None,
                    "created_at": None
                })
        
        logger.info(f"[MERGE_SESSION] Session сообщения: {len(session_msgs)}")
        for i, msg in enumerate(session_msgs[:5]):
            logger.info(f"  SESSION[{i}] role={msg['role']}, text={msg['text'][:30]}...")
        
        # 2. Парсим БД (очищаем от возможных префиксов)
        db_msgs = []
        for record in db_messages:
            text = record.text
            # Убираем префиксы если они есть (legacy данные)
            if record.role == "user" and text.startswith("user: "):
                text = text[6:]
            elif record.role == "assistant" and text.startswith("assistant: "):
                text = text[11:]
            
            db_msgs.append({
                "id": record.id,
                "role": record.role,
                "text": text,
                "created_at": record.created_at,
                "source": "db"
            })
        
        logger.info(f"[MERGE_DB] БД сообщения: {len(db_msgs)}")
        for i, msg in enumerate(db_msgs[:5]):
            logger.info(f"  DB[{i}] id={msg.get('id')}, role={msg['role']}")
        
        # 3. Создаём set для дедупликации по (role, text)
        seen = set()
        unique = []
        
        # Сначала БД (старые) — они имеют приоритет (есть id)
        for msg in db_msgs:
            key = (msg["role"], msg["text"].strip()[:100])  # первые 100 символов для сравнения
            if key not in seen:
                seen.add(key)
                unique.append(msg)
        
        # Потом SessionContext (новые) — только если нет дубля
        for msg in session_msgs:
            key = (msg["role"], msg["text"].strip()[:100])
            if key not in seen:
                seen.add(key)
                unique.append(msg)
        
        logger.info(f"[MERGE_FINAL] После дедупликации: {len(unique)} (было DB={len(db_msgs)}, session={len(session_msgs)})")
        for i, msg in enumerate(unique[:8]):
            msg_id = msg.get('id', 'session')
            logger.info(f"  FINAL[{i}] id={msg_id}, role={msg['role']}, source={msg.get('source')}")
        
        return unique

