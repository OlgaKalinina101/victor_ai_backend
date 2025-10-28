import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.analysis.postanalysis.helpers import parse_key_info
from core.analysis.postanalysis.prompts import KEY_INFO_PROMPTS, IMPRESSIVE_RATING_PROMPT
from core.analysis.preanalysis.preanalysis import analyze_dialogue
from infrastructure.database.repositories import save_memory_as_key_info
from infrastructure.llm.client import LLMClient
from infrastructure.logging.logger import setup_logger
from infrastructure.vector_store.embedding_pipeline import PersonaEmbeddingPipeline
from models.communication_models import MessageMetadata
from settings import settings

from typing import Optional
from datetime import datetime, timezone
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class KeyInfoPostAnalyzer:
    def __init__(
        self,
        llm_client: Optional["LLMClient"] = None,
        pipeline: Optional["PersonaEmbeddingPipeline"] = None,
        logger=None,
    ) -> None:
        self.pipeline = pipeline or PersonaEmbeddingPipeline()
        self.logger = logger or setup_logger("postanalysis")
        self.llm_client = llm_client or LLMClient(mode="foundation")


    async def process(self, account_id: str, user_message: str, metadata: MessageMetadata) -> None:
        """
        Обрабатывает сообщение пользователя, извлекает ключевую информацию и сохраняет её.

        Args:
            account_id: ID аккаунта пользователя.
            user_message: Сообщение пользователя.
            metadata: Мета-данные сообщения.
        """
        self.logger.info(f"[INFO] Начало обработки сообщения для account_id: {account_id}")

        try:
            key_info = await self._analyze_dialogue(user_message)
            if not self._is_valid_key_info(key_info):
                self.logger.info("[INFO] Нет ключевой информации в сообщении пользователя.")
                return

            category, memory = self._parse_key_info(key_info)
            if not memory or not category:
                self.logger.warning("[WARNING] Недостаточно данных для сохранения key_info.")
                return

            impressive = await self._rate_impressiveness(memory)
            await self._save_to_pipeline(account_id, category, memory, impressive, metadata)
            self._save_to_database(account_id, category, memory, impressive, metadata)

            self.logger.info("[INFO] ✅ Обработка key info завершена успешно.")

        except Exception as e:
            self.logger.exception(f"[ERROR] ❌ Ошибка при обработке key info: {e}")
            raise  # или можно убрать raise, если не нужно пробрасывать ошибку дальше

    async def _analyze_dialogue(self, user_message: str) -> str:
        """Анализирует диалог и возвращает ключевую информацию."""
        try:
            return await analyze_dialogue(
                llm_client=self.llm_client,
                prompt_template=KEY_INFO_PROMPTS,
                user_message=user_message,
                return_json=False,
            )
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при анализе диалога: {e}")
            raise

    def _is_valid_key_info(self, key_info: str) -> bool:
        """Проверяет, содержит ли ключная информация валидные данные."""
        return key_info.lower() not in {"null", "none", "", "нет ключевой информации"}

    def _parse_key_info(self, key_info: str) -> tuple[Optional[str], Optional[str]]:
        """Парсит ключевую информацию и возвращает категорию и память."""
        try:
            category, memory = parse_key_info(key_info)
            return category, memory
        except Exception as e:
            self.logger.warning(f"[WARNING] Ошибка при парсинге key_info: {e}")
            return None, None

    async def _rate_impressiveness(self, memory: str) -> int:
        """Оценивает значимость памяти."""
        try:
            result = await analyze_dialogue(
                llm_client=self.llm_client,
                prompt_template=IMPRESSIVE_RATING_PROMPT,
                memories=memory,
                return_json=False,
            )
            rating = int(result.strip().replace('"', ''))
            if rating not in {1, 2, 3, 4}:
                raise ValueError(f"Недопустимая оценка: {rating}")
            self.logger.debug(f"[DEBUG] Оценка значимости: {rating}")
            return rating
        except Exception as e:
            self.logger.warning(f"[WARNING] Не удалось определить значимость: {e}, default=1")
            return 1

    async def _save_to_pipeline(self, account_id: str, category: str, memory: str, impressive: int, metadata: MessageMetadata) -> None:
        """Сохраняет данные в pipeline."""
        try:
            self.pipeline.add_entry(
                account_id=account_id,
                memory=memory,
                mood=metadata.mood,
                mood_level=metadata.mood_level,
                category=category,
                impressive=impressive,
                frequency=0,
                last_used=datetime.now(timezone.utc),
                external_id=str(uuid.uuid4()),
            )
            self.logger.info("[DEBUG] ✅ Key info успешно сохранено в Chroma.")
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при сохранении в pipeline: {e}")
            raise

    def _save_to_database(self, account_id: str, category: str, memory: str, impressive: int,
                          metadata: MessageMetadata) -> None:
        """Сохраняет данные в базу данных."""
        try:
            engine = create_engine(settings.DATABASE_URL)
            Session = sessionmaker(bind=engine)
            with Session() as session:
                save_memory_as_key_info(session, account_id, category,  memory, impressive, metadata)
                self.logger.info("[DEBUG] ✅ Key info успешно сохранено в database.")
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при сохранении в базу данных: {e}")
            raise