from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime

from infrastructure.database.repositories import get_chat_meta
from infrastructure.logging.logger import setup_logger
from models.assistant_models import ReactionFragments, VictorState
from models.communication_models import MessageMetadata
from models.user_enums import RelationshipLevel, Gender
from sqlalchemy.orm import Session

logger = setup_logger("session_context")

@dataclass
class SessionContext:
    """Контекст текущей сессии. По окончании сессии сохраняется в БД."""
    account_id: str
    last_update: datetime
    gender: Gender
    relationship_level: RelationshipLevel
    trust_level: int
    is_creator: bool
    model: str
    last_assistant_message: datetime = None
    last_anchor: str = None
    message_category_history: List[str] = field(default_factory=list)
    message_history: List[str] = field(default_factory=list)
    key_info_history: List[str] = field(default_factory=list)
    anchor_link_history: List[str] = field(default_factory=list)
    focus_points_history: List[str] = field(default_factory=list)
    victor_mood_history: List[str] = field(default_factory=list)
    victor_intensity_history: List[float] = field(default_factory=list)
    victor_impressive_history: List[str] = field(default_factory=list)
    victor_impressive_count: List[int] = field(default_factory=list)
    weights: Dict[str, float] = field(default_factory=lambda: {
        "joy": 0.0, "sadness": 0.0, "anger": 0.0, "fear": 0.0,
        "disgust": 0.0, "surprise": 0.0, "neutral": 0.0,
    })
    dialog_weight: int = 1
    count: Dict[str, int] = field(default_factory=lambda: {
        "hug_count": 0, "resonance_count": 0, "metaphor_count": 0,
        "spark_count": 0, "anger_count": 0, "outburst_count": 0,
        "story_count": 0, "anchor_thought_count": 0,
        "symbol_count": 0, "pulse_count": 0, "support_count": 0,
        "clarify_count": 0, "observe_count": 0, "presence_count": 0,
        "redirect_count": 0, "confirm_count": 0, "transfer_count": 0,
    })
    next_event: Optional[str] = None
    session_start_time: float = 0.0

    @staticmethod
    def empty(account_id: str, last_update: datetime, db_session: Session, **kwargs) -> "SessionContext":
        # 1. Загружаем chat_meta из БД
        from infrastructure.database.repositories import get_chat_meta
        meta = get_chat_meta(db_session, account_id)

        return SessionContext(
            account_id=account_id,
            last_update=last_update,

            # 2. gender: сначала из kwargs, затем из meta, иначе — default
            gender=Gender.from_str(kwargs.get("gender")) if kwargs.get("gender")
            else Gender.from_str(meta.gender) if meta and meta.gender
            else Gender.default(),

            # 3. relationship_level: аналогично
            relationship_level=RelationshipLevel.from_str(kwargs.get("relationship_level")) if kwargs.get(
                "relationship_level")
            else RelationshipLevel.from_str(meta.relationship_level) if meta and meta.relationship_level
            else RelationshipLevel.default(),

            # 4. trust_level: число, так что без from_str
            trust_level=kwargs.get("trust_level")
            if kwargs.get("trust_level") is not None
            else meta.trust_level if meta and meta.trust_level is not None
            else 0,

            # 5. is_creator: булево
            is_creator=kwargs.get("is_creator")
            if "is_creator" in kwargs
            else meta.is_creator if meta
            else False,

            # 6. model: строка
            model=kwargs.get("model")
                  or meta.model if meta and meta.model
            else "gpt-4o",
        )

    def add_user_message(self, text: str):
        self.message_history.append(f"user: {text}")
        logger.info(f"self.message_history: {self.message_history}")

    def add_assistant_message(self, text: str):
        self.message_history.append(f"assistant: {text}")
        self.last_assistant_message = datetime.now()

    def get_recent_pairs(self, count: int = 6) -> str:
        return "\n".join(msg.replace("\n", " ") for msg in self.message_history[-count * 2:])

    def get_last_n_pairs(self, n: int = 3) -> List[str]:
        """
        Возвращает последние N пар (user + assistant) из message_history.
        Пара = user-сообщение + следующее assistant-сообщение.
        """
        pairs = []
        i = len(self.message_history) - 1

        # Идём с конца, ищем пары assistant -> user (в обратном порядке)
        while i >= 0 and len(pairs) < n * 2:
            if self.message_history[i].startswith("assistant:"):
                # Нашли assistant, ищем user перед ним
                if i > 0 and self.message_history[i - 1].startswith("user:"):
                    pairs.insert(0, self.message_history[i - 1])  # user
                    pairs.insert(1, self.message_history[i])  # assistant
                    i -= 2
                else:
                    i -= 1
            else:
                i -= 1

        return pairs

    def update_emotion_weights(self, mood_data: List[Dict[str, float]]) -> None:
        for item in mood_data:
            label = item["label"].lower()
            label = {"no_emotion": "neutral"}.get(label, label)
            score = round(item["score"], 2)
            if label in self.weights:
                old = self.weights[label]
                self.weights[label] = score if old == 0.0 else round((old + score) / 2, 2)
                logger.info(f"label: {label}, score: {self.weights[label]}")

    def get_dominant_emotion(self, threshold: float = 0.5) -> Optional[str]:
        if not self.weights:
            return None
        label, score = max(self.weights.items(), key=lambda x: x[1])
        return label if score >= threshold else None

    def load_chat_meta(self):
        meta = get_chat_meta(self.db_session, self.account_id)
        if meta:
            self.gender = meta.gender
            self.relationship_level = meta.relationship_level
            self.trust_level = meta.trust_level
            self.is_creator = meta.is_creator
            self.model = meta.model

    def reset_after_save(self,
                         gender,
                         relationship_level,
                         trust_level,
                         is_creator,
                         model,
                         last_assistant_message,
                         last_anchor
                         ) -> "SessionContext":
        """Возвращает полностью очищенный контекст для новой сессии."""
        logger.info("Новая сессия - сбрасываем контекст.")
        return SessionContext(
            account_id=self.account_id,
            last_update=datetime.utcnow(),  # новая отметка
            gender=gender,
            relationship_level=relationship_level,
            trust_level=trust_level,
            is_creator=is_creator,
            model=model,
            last_assistant_message=last_assistant_message,
            last_anchor=last_anchor,
            # все списки — пустые
            message_category_history=[],
            message_history=[],
            key_info_history=[],
            anchor_link_history=[],
            focus_points_history=[],
            victor_mood_history=[],
            victor_intensity_history=[],
            # словари — обнулённые
            weights={k: 0.0 for k in self.weights},
            count={k: 0 for k in self.count},
            dialog_weight=1,
            session_start_time=0.0,
        )

def to_serializable(context: SessionContext) -> dict:
    """
    Преобразует SessionContext в сериализуемый словарь для сохранения в YAML.
    """
    return {
        "account_id": context.account_id,
        "last_update": context.last_update.isoformat(),
        "gender": context.gender.value,
        "relationship_level": context.relationship_level.value,
        "trust_level": context.trust_level,
        "is_creator": context.is_creator,
        "model": context.model,
        "last_assistant_message": context.last_assistant_message.isoformat() if context.last_assistant_message else None,
        "last_anchor": context.last_anchor,
        "message_category_history": context.message_category_history,
        "message_history": context.message_history,
        "key_info_history": context.key_info_history,
        "anchor_link_history": context.anchor_link_history,
        "focus_points_history": context.focus_points_history,
        "victor_mood_history": context.victor_mood_history,
        "victor_intensity_history": context.victor_intensity_history,
        "victor_impressive_history": context.victor_impressive_history,
        "victor_impressive_count": context.victor_impressive_count,
        "weights": context.weights,
        "dialog_weight": context.dialog_weight,
        "count": context.count,
        "next_event": context.next_event,
        "session_start_time": context.session_start_time,
    }


def from_yaml_dict(data: dict) -> dict:
    return {
        "account_id": data["account_id"],
        "last_update": datetime.fromisoformat(data["last_update"]),
        "gender": Gender(data["gender"]),
        "relationship_level": RelationshipLevel(data["relationship_level"]),
        "trust_level": data["trust_level"],
        "is_creator": data["is_creator"],
        "model": data["model"],
        "last_assistant_message": datetime.fromisoformat(data["last_assistant_message"]) if data.get("last_assistant_message") else None,
        "last_anchor": data.get("last_anchor"),
        "message_category_history": data.get("message_category_history", []),
        "message_history": data.get("message_history", []),
        "key_info_history": data.get("key_info_history", []),
        "anchor_link_history": data.get("anchor_link_history", []),
        "focus_points_history": data.get("focus_points_history", []),
        "victor_mood_history": data.get("victor_mood_history", []),
        "victor_intensity_history": data.get("victor_intensity_history", []),
        "victor_impressive_history": data.get("victor_impressive_history", []),
        "victor_impressive_count": data.get("victor_impressive_count", []),
        "weights": data.get("weights", {}),
        "dialog_weight": data.get("dialog_weight", 1),
        "count": data.get("count", {}),
        "next_event": data.get("next_event"),
        "session_start_time": data.get("session_start_time", 0.0),
    }

def update_reaction_counters(session: SessionContext, fragments: ReactionFragments):
    """
    Обновляет счетчики в session.count на основе выбранных фрагментов реакции.
    """

    # Мапа ключевых фраз к полям count
    mapping = {
        "дай якорь": "anchor_thought_count",
        "задаешь вопрос, касаясь смысла": "clarify_count",
        "обними словами": "hug_count",
        "ты слышишь слишком точно": "observe_count",
        "ты позволяешь этому чувству прозвучать шире": "resonance_count",
        "тишина - тоже ответ": "presence_count",
        "заверши с ощущением, будто ты отпускаешь": "support_count",
    }

    # Собираем все текстовые фрагменты в один список для поиска
    fragments_text = [fragments.start, fragments.core, fragments.question, fragments.end]

    for frag in fragments_text:
        if not frag:
            continue
        frag_lower = frag.lower()
        for key, counter in mapping.items():
            if key in frag_lower:
                session.count[counter] += 1
                break


def update_session_context_from_metadata(
    session_context: SessionContext,
    metadata: MessageMetadata,
    victor_state: Optional[VictorState] = None,
):
    # 1. message_category_history
    if metadata.message_category:
        session_context.message_category_history.append(metadata.message_category.value)

    # 2. key_info_history ← только "true" из metadata.memories
    memory_raw = metadata.memories
    if memory_raw:
        try:
            session_context.key_info_history.append(memory_raw)
        except Exception as e:
            logger.error(f"[update_session_context] Ошибка парсинга или обработки memories: {e}")

    # 3. anchor_link_history
    anchor_dict = metadata.emotional_anchor
    if anchor_dict:
        anchor_link = anchor_dict.get("anchor_link")
        is_strong = anchor_dict.get("is_strong_anchor")
        if anchor_link is not None:
            session_context.anchor_link_history.append(f"{anchor_link},{is_strong}")

    # 4. focus_points_history
    focus_dict = metadata.focus_phrases
    if focus_dict:
        points = focus_dict.get("focus_points", [])
        strengths = focus_dict.get("is_strong_focus", [])
        for i, point in enumerate(points):
            is_strong = strengths[i] if i < len(strengths) else False
            session_context.focus_points_history.append(f"{point},{is_strong}")

    # 5. victor_*_history
    if victor_state:
        session_context.victor_mood_history.append(victor_state.mood.value)
        session_context.victor_intensity_history.append(victor_state.intensity)
        session_context.victor_impressive_history.append(str(victor_state.has_impressive))


def update_session_context_from_victor_state(
        session_context: SessionContext,
        victor_state: Optional[VictorState]):
    """
    Обновляет поля session_context на основе метаданных и состояния Victor.
    """
    # 1. victor_*_history ← из VictorState
    try:
        if victor_state:
            session_context.victor_mood_history.append(victor_state.mood.value)
            session_context.victor_intensity_history.append(victor_state.intensity)
            session_context.victor_impressive_history.append(str(victor_state.has_impressive))
    except Exception as e:
        logger.error(f"[update_session_context] Ошибка парсинга focus: {e}")











