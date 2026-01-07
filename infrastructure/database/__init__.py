"""
Database infrastructure package.

Экспортирует основные функции и классы для работы с базой данных.
"""

# Экспортируем классы-репозитории из пакета repositories/ (новый подход)
from .repositories import (
    ChatMetaRepository,
    AlarmsRepository,
    DialogueRepository,
    DiaryRepository,
    ModelUsageRepository,
    KeyInfoRepository,
)


# ===== Legacy wrapper функции для обратной совместимости =====
# Эти функции используют новые репозитории, но сохраняют старый интерфейс
def get_dialogue_history_paginated(session, account_id: str, limit: int = 25, before_id=None):
    """Legacy wrapper для DialogueRepository.get_paginated"""
    repo = DialogueRepository(session)
    return repo.get_paginated(account_id, limit, before_id)


def get_dialogue_context(session, account_id: str, message_id: int, context_before: int = 10, context_after: int = 10):
    """Legacy wrapper для DialogueRepository.get_context"""
    repo = DialogueRepository(session)
    return repo.get_context(account_id, message_id, context_before, context_after)


def search_dialogue_history(session, account_id: str, query: str, offset: int = 0):
    """Legacy wrapper для DialogueRepository.search"""
    repo = DialogueRepository(session)
    return repo.search(account_id, query, offset)


def save_dialogue_history(session, history):
    """Legacy wrapper для DialogueRepository.save_message"""
    repo = DialogueRepository(session)
    return repo.save_message(
        account_id=history.account_id,
        role=history.role,
        text=history.text,
        dialogue_id=history.dialogue_id,
        emoji=history.emoji,
        mood=history.mood,
        message_type=history.message_type,
        message_category=history.message_category,
        focus_points=history.focus_points,
        has_strong_focus=history.has_strong_focus,
        anchor_link=history.anchor_link,
        has_strong_anchor=history.has_strong_anchor,
        memories=history.memories,
        anchor=history.anchor,
    )


def save_session_context_as_history(session, context_dict: dict):
    """Legacy wrapper для DialogueRepository.save_session_context_as_history"""
    repo = DialogueRepository(session)
    return repo.save_session_context_as_history(context_dict)


def get_chat_meta(session, account_id: str):
    """Legacy wrapper для ChatMetaRepository.get_by_account_id"""
    repo = ChatMetaRepository(session)
    return repo.get_by_account_id(account_id)


def save_chat_meta(session, meta):
    """Legacy wrapper для ChatMetaRepository.create_or_update"""
    repo = ChatMetaRepository(session)
    # Получаем все поля из объекта meta (кроме account_id)
    fields = {k: v for k, v in meta.__dict__.items() if not k.startswith('_') and k != 'account_id'}
    return repo.create_or_update(meta.account_id, **fields)


def merge_session_and_db_history(session_context: dict, db_messages):
    """Legacy wrapper для DialogueRepository.merge_session_and_db_history"""
    from .session import Database
    db = Database.get_instance()
    with db.get_session() as session:
        repo = DialogueRepository(session)
        return repo.merge_session_and_db_history(session_context, db_messages)

# Экспортируем Database и модели
from .session import Database
from .models import (
    DialogueHistory,
    ChatMeta,
    KeyInfo,
    Diary,
    UserAlarms,
    MusicTrack,
    TrackPlayHistory,
    TrackUserDescription,
    ModelUsage,
    Reminder,
)

__all__ = [
    # Legacy функции (используют новые репозитории, но сохраняют старый интерфейс)
    "get_dialogue_history_paginated",
    "get_dialogue_context",
    "search_dialogue_history",
    "save_dialogue_history",
    "save_session_context_as_history",
    "get_chat_meta",
    "save_chat_meta",
    "merge_session_and_db_history",
    # Репозитории
    "ChatMetaRepository",
    "AlarmsRepository",
    "DialogueRepository",
    "DiaryRepository",
    "ModelUsageRepository",
    "KeyInfoRepository",
    # Database
    "Database",
    # Модели
    "DialogueHistory",
    "ChatMeta",
    "KeyInfo",
    "Diary",
    "UserAlarms",
    "MusicTrack",
    "TrackPlayHistory",
    "TrackUserDescription",
    "ModelUsage",
    "Reminder",
]
