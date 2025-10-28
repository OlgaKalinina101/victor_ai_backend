from pathlib import Path

import yaml
from typing import Optional, Dict, LiteralString

from infrastructure.logging.logger import setup_logger
from models.assistant_models import AssistantMood
from models.communication_enums import MessageCategory
from models.user_enums import Gender, RelationshipLevel
from settings import settings

logger = setup_logger("victor_core")

class SystemPromptBuilder:
    """Класс для построения системного промпта для Victor AI на основе конфигурации из YAML.

    Этот класс загружает конфигурацию из YAML-файла и динамически собирает системный промпт,
    учитывая параметры пользователя (пол, уровень отношений, настроение и т.д.).
    Используется для создания персонализированных ответов AI с сохранением его ядра и стиля.
    """

    def __init__(self, yaml_path: Path = settings.SYSTEM_PROMPT_PATH):
        """Инициализирует SystemPromptBuilder с путём к YAML-файлу конфигурации.

        Args:
            yaml_path (str): Путь к YAML-файлу с конфигурацией промптов.
                             По умолчанию: 'core/persona/prompts/system.yaml'.

        Attributes:
            yaml_path (str): Путь к YAML-файлу конфигурации.
            yaml_data (dict): Загруженные данные из YAML-файла.
        """
        self.yaml_path = yaml_path
        self.yaml_data = self.load_yaml()

    def load_yaml(self) -> Dict:
        """Загружает конфигурацию промптов из YAML-файла.

        Пытается открыть и распарсить указанный YAML-файл.
        В случае ошибки логирует её и возвращает пустой словарь.

        Returns:
            Dict: Словарь с данными из YAML-файла или пустой словарь при ошибке.

        Raises:
            Exception: Если не удалось открыть или распарсить YAML-файл.
        """
        try:
            with open(self.yaml_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Ошибка загрузки {self.yaml_path}: {e}")
            return {}

    def build(
        self,
        gender: Gender,
        relationship: RelationshipLevel,
        message_category: MessageCategory = None,
        victor_mood: AssistantMood = None,
        victor_intensity: Optional[float] = None,
        emotional_access: Optional[int] = None,
        required_depth_level: Optional[int] = None
    ) -> LiteralString:
        """Собирает системный промпт на основе переданных параметров.

        Формирует промпт, комбинируя ядро (core), роль, тренд, мнение, чувства и эмодзи
        в зависимости от параметров пользователя и настроения Victor AI.
        Учитывает уровни эмоционального доступа и глубины для персонализации.

        Args:
            gender (str): Пол пользователя (например, 'male', 'female').
            relationship (str): Уровень отношений с пользователем (например, 'best_friend', 'stranger').
            message_category (Optional[str]): Категория сообщения (например, 'opinion', 'feeling').
            victor_mood (Optional[str]): Текущее настроение Victor AI (например, 'joy').
            victor_intensity (Optional[float]): Сила настроения Victor AI.
            emotional_access (Optional[int]): Уровень эмоционального доступа пользователя.
            required_depth_level (Optional[int]): Требуемый уровень глубины для обработки сообщения.

        Returns:
            str: Итоговый системный промпт, объединённый из всех релевантных блоков.

        Example:
            >>> builder = SystemPromptBuilder()
            >>> prompt = builder.build(
            ...     gender=Gender.MALE,
            ...     relationship=RelationshipLevel.FRIEND,
            ...     message_category=MessageCategory.FACT,
            ...     victor_mood=AssistantMood.JOY,
            ...     victor_intensity=0.5,
            ...     emotional_access=2,
            ...     required_depth_level=1
            ... )
            >>> print(prompt)
            # Выводит промпт с ядром, ролью, трендом и эмодзи
            :param emotional_access:
            :param victor_intensity:
        """
        parts = []

        # 1. Core Identity
        core = self.yaml_data.get("core_identity", {})
        if core:
            parts.append(core)

        # 2. Role Variants
        role = self.yaml_data.get("role_variants", {}).get(relationship.value)
        if role:
            parts.append("Ты чувствуешь себя со мной, как " + role)

        # 3. Trend Variants
        trend = self.yaml_data.get("trend_variants", {}).get(gender.value, {}).get(relationship.value)
        if trend:
            parts.append("Ты говоришь на “ты”, " + trend)

        # 4. Opinion Variants
        if message_category and MessageCategory.OPINION in message_category:
            if emotional_access is None or required_depth_level is None or emotional_access >= required_depth_level:
                opinion = self.yaml_data.get("opinion_variants", {}).get(relationship.value)
                if opinion:
                    parts.append(opinion)

        # 5. Feeling Variants
        if message_category and MessageCategory.FEELING in message_category:
            if emotional_access is None or required_depth_level is None or emotional_access >= required_depth_level:
                feeling = self.yaml_data.get("feeling_variants", {}).get(relationship.value)
                if feeling:
                    parts.append(feeling)

        # 6. Emoji Block
        logger.info(f"emotional_access: {emotional_access} victor_intensity: {victor_intensity}")
        if emotional_access > 5 and victor_intensity > 0.7:
            emoji_block = self.yaml_data.get("if_emoji", "")
            logger.info(f"emoji_block: {emoji_block}")
            emoji_list = self.yaml_data.get("mood_emoji_map", {}).get(victor_mood.value)  # список или None
            logger.info(f"emoji_list: {emoji_list}")
            if emoji_list and emoji_block:
                # Собираем строку из emoji, через пробел
                emoji_str = " ".join(emoji_list)
                parts.append(emoji_block.format(emojis=emoji_str))

        return "\n\n".join(parts)
