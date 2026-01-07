# This file is part of victor_ai_backend.
#
# victor_ai_backend is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# victor_ai_backend is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with victor_ai_backend. If not, see <https://www.gnu.org/licenses/>.

import inspect
from logging import Logger
from typing import Callable, Dict, AsyncGenerator, Optional

from core.analysis.preanalysis.preanalysis import analyze_dialogue
from core.router.router_prompts import ROUTER_PROMPT
from infrastructure.context_store.session_context_store import SessionContextStore
from infrastructure.database.session import Database
from infrastructure.llm.client import LLMClient
from infrastructure.logging.logger import setup_logger
from settings import settings
from tools.carebank.carebank_tool import run_care_bank_chain
from tools.communication.communication_tool import run_communication
from tools.places.places_tool import PlacesContextBuilder
from tools.playlist.playlist_tool import run_playlist_chain
from tools.reminders.reminder_tool import run_reminder_chain
from tools.weather.weather_tool import WeatherContextBuilder

HandlerType = Callable[..., str]  # Тип обработчика может быть sync или async

class MessageTypeManager:
    def __init__(self, db: Optional[Database] = None, context_store: Optional[SessionContextStore] = None):
        self.default_route: HandlerType = run_communication
        self.logger: Logger = setup_logger("message_router")
        self.db = db or Database.get_instance()
        self.context_store = context_store or SessionContextStore(
            storage_path=settings.SESSION_CONTEXT_DIR
        )

    def _create_llm_client(self, account_id: str) -> LLMClient:
        """
        Создаёт LLMClient с учётом выбранной модели из ChatMeta.
        
        Args:
            account_id: ID аккаунта пользователя
            
        Returns:
            LLMClient с правильным режимом (foundation/advanced/creative) на основе ChatMeta.model
        """
        try:
            from infrastructure.database.repositories.chat_meta_repository import ChatMetaRepository
            
            db_session = self.db.get_session()
            try:
                repo = ChatMetaRepository(db_session)
                meta = repo.get_by_account_id(account_id)
                model = meta.model if meta and meta.model else None
                
                # Определяем режим на основе модели
                if model:
                    model_lower = model.lower()
                    if "grok" in model_lower:
                        mode = "creative"
                        self.logger.info(f"[ROUTER] Выбран режим 'creative' для модели {model}")
                    elif "gpt" in model_lower or "openai" in model_lower:
                        mode = "advanced"
                        self.logger.info(f"[ROUTER] Выбран режим 'advanced' для модели {model}")
                    elif "deepseek" in model_lower:
                        mode = "foundation"
                        self.logger.info(f"[ROUTER] Выбран режим 'foundation' для модели {model}")
                    else:
                        # Неизвестная модель — используем дефолт
                        mode = "foundation"
                        self.logger.warning(f"[ROUTER] Неизвестная модель {model}, используем режим 'foundation'")
                else:
                    mode = "foundation"
                    self.logger.info(f"[ROUTER] ChatMeta.model не задана, используем режим 'foundation'")
                    
            finally:
                db_session.close()
                
        except Exception as e:
            self.logger.warning(f"[ROUTER] Не удалось определить модель из ChatMeta: {e}, используем 'foundation'")
            mode = "foundation"
        
        return LLMClient(account_id=account_id, mode=mode)

    def _add_user_message_to_context(self, account_id: str, text: str) -> None:
        """
        Добавляет user-сообщение в контекст и сохраняет.
        
        НЕ обновляет last_update, чтобы не сбросить таймер staleness.
        Время обновится позже в MessageAnalyzer после проверки staleness.
        
        Args:
            account_id: ID аккаунта пользователя
            text: Текст сообщения пользователя
        """
        db_session = self.db.get_session()
        try:
            session_context = self.context_store.load(account_id, db_session)
            session_context.add_user_message(text)
            self.context_store.save(session_context, update_timestamp=False)
            self.logger.info(f"[ROUTER] User-сообщение добавлено в контекст: {text[:50]}...")
        finally:
            db_session.close()

    async def _handle_system_event(
        self,
        event_type: str,
        text: str,
        account_id: str
    ) -> tuple[str, str]:
        """
        Обрабатывает системные события от фронта.
        
        Args:
            event_type: Тип системного события (например, "food_flow_completed")
            text: Текст, присланный клиентом
            account_id: ID аккаунта пользователя
            
        Returns:
            Кортеж (text_to_use, function_call), где:
            - text_to_use: текст для обработки в дефолтном роуте
            - function_call: название вызванной функции
        """
        db_session = self.db.get_session()
        try:
            if event_type == "food_flow_completed":
                session_context = self.context_store.load(account_id, db_session)
                user_text = session_context.get_last_user_message(fallback=text)
                return user_text, "food_flow_completed"
            
            # Здесь в будущем добавятся другие события:
            # elif event_type == "walk_completed":
            #     ...
            
            return text, "None"
        finally:
            db_session.close()

    async def route_message(self, request) -> AsyncGenerator[str | dict, None]:  # ← стримит
        account_id = request.session_id
        geo = request.geo
        swipe_message_id = getattr(request, "swipe_message_id", None)

        # Базовый текст – то, что прислал клиент
        text = request.text.lower().strip()

        # Флаг: нужно ли добавлять user message в контекст перед дефолтным роутом
        skip_user_message = False
        
        # 🖼️ Извлекаем изображение если есть (пробрасываем в CommunicationPipeline)
        image_bytes = None
        mime_type = "image/png"
        if hasattr(request, 'screenshot_bytes') and request.screenshot_bytes:
            # Изображение пришло как multipart/form-data (байты)
            image_bytes = request.screenshot_bytes
            mime_type = getattr(request, 'mime_type', 'image/png')
            self.logger.info(f"[VISION] Обнаружено изображение: {len(image_bytes)} bytes, mime_type={mime_type}")
        else:
            self.logger.info("[ROUTER] Изображение не обнаружено")
        
        # 🔧 Создаём LLMClient один раз (учитывая выбранную модель из ChatMeta)
        llm_client = self._create_llm_client(account_id)
        
        # ⚡ Ветка: системное событие от фронта
        if request.system_event:
            text, function_call = await self._handle_system_event(
                event_type=request.system_event,
                text=text,
                account_id=account_id
            )
            # При system_event user message УЖЕ есть в SessionContext
            # (было добавлено ранее, например, в care_bank)
            skip_user_message = True
        else:
            # 🔍 Обычный роутер: анализируем диалог и решаем, что делать
            result_json = await analyze_dialogue(
                llm_client=llm_client,
                prompt_template=ROUTER_PROMPT,
                user_message=text,
            )
            function_call = result_json.get("function call", "None")

            if function_call == "reminder":
                # run_reminder_chain НЕ стримит — собираем в строку
                # НЕ добавляем user-сообщение для reminder
                response = await run_reminder_chain(account_id=account_id, text=text)
                yield response
                return

            elif function_call == "care_bank":
                # ✅ Добавляем user-сообщение для care_bank
                self._add_user_message_to_context(account_id, text)
                
                response, result = await run_care_bank_chain(
                    account_id=account_id,
                    text=text,
                    db=self.db
                )
                yield response  # ← строка для чата
                yield result  # ← словарь для сценария
                return

        # 🌊 Дефолтный маршрут — общий для обоих случаев:
        # - либо после обычного роутера
        # - либо после system_event="food_flow_completed"
        # ✅ Добавляем user-сообщение для дефолтного роута (если еще не добавлено)
        if not skip_user_message:
            self._add_user_message_to_context(account_id, text)
        
        async for chunk in self._execute_stream(
                self.default_route,
                account_id=account_id,
                text=text,
                function_call=function_call,
                geo=geo,
                db=self.db,
                session_context_store=self.context_store,
                llm_client=llm_client,  # 🔧 Прокидываем созданный клиент
                image_bytes=image_bytes,  # 🖼️ Пробрасываем байты изображения
                mime_type=mime_type,
                swipe_message_id=swipe_message_id,
        ):
            yield chunk

    async def _execute_stream(
            self,
            handler: HandlerType,
            **kwargs
    ) -> AsyncGenerator[str | dict, None]:
        """Выполняет handler и стримит результат."""
        if inspect.isasyncgenfunction(handler):
            # Если handler — async generator
            async for chunk in handler(**kwargs):
                yield chunk
        elif inspect.iscoroutinefunction(handler):
            # Если handler возвращает str
            result = await handler(**kwargs)
            yield result
        else:
            # Синхронный handler
            yield handler(**kwargs)



