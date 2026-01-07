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

import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, UploadFile, File, Form, Depends
from starlette.responses import StreamingResponse

from api.dependencies.runtime import get_db
from api.helpers import (
    get_provider_by_model,
    load_serialized_session_context
)
from api.schemas.token import TokenRequest
from api.schemas.assistant import (
    AssistantRequest,
    AssistantResponse,
    AssistantState,
    AssistantMind,
    MemoryResponse,
    DeleteRequest,
    UpdateMemoryRequest,
    VisionDescribeResponse,
)
from api.schemas.common import Usage
from core.router.message_router import MessageTypeManager
from infrastructure.database.session import Database
from infrastructure.database.repositories import ModelUsageRepository
from infrastructure.firebase.tokens import TOKENS_FILE, save_device_token
from infrastructure.logging.logger import setup_logger
from infrastructure.vector_store.embedding_pipeline import PersonaEmbeddingPipeline
from settings import settings
from tools.vision.vision_tool import run_vision_chain

logger = setup_logger("assistant")

router = APIRouter(prefix="/assistant", tags=["Assistant"])


@router.post("/register_token")
async def register_token(req: TokenRequest, request: Request):
    """
    Регистрирует токен устройства для отправки push-уведомлений.

    Сохраняет связку user_id → device_token для последующей отправки
    уведомлений на мобильное устройство пользователя. Используется для
    Firebase Cloud Messaging (FCM) или аналогичных сервисов.

    Args:
        req: Объект запроса, содержащий:
            - user_id: Идентификатор пользователя
            - token: Токен устройства (FCM token)
        request: Объект HTTP-запроса для логирования IP-адреса

    Returns:
        Объект с результатом операции:
        - status: "ok" при успешном сохранении
        - tokens_file: Путь к файлу с сохранёнными токенами

    Raises:
        HTTPException 400: Если отсутствует user_id или token.
        HTTPException 500: При ошибке записи в файл или базу данных.

    Notes:
        - Токен устройства обновляется при каждом вызове (последний токен перезаписывает предыдущий)
        - IP-адрес клиента логируется для мониторинга
    """
    logger.info(f"register_token from {request.client.host} user={req.user_id}")
    save_device_token(req.user_id, req.token)
    return {"status": "ok", "tokens_file": str(TOKENS_FILE)}


@router.post("/message", response_model=AssistantResponse)
async def process_signal(request: AssistantRequest):
    """
    Обрабатывает пользовательское сообщение и возвращает ответ ассистента.

    Получает текстовое сообщение от пользователя, анализирует его тип с помощью
    MessageTypeManager, выбирает соответствующий инструмент обработки и генерирует
    ответ. Поддерживает мультимодальные запросы с изображениями.

    Args:
        request: Объект запроса, содержащий:
            - text: Текст сообщения пользователя
            - images: Список изображений в формате base64 (опционально)
            - account_id: Идентификатор пользователя
            - context: Дополнительный контекст диалога

    Returns:
        AssistantResponse с полями:
        - answer: Текстовый ответ ассистента
        - status: Статус обработки ("ok" или "error")

    Raises:
        HTTPException 400: Если текст отсутствует и нет изображений.
        HTTPException 413: Если размер данных (текст + изображения) превышает лимит.
        HTTPException 422: Если некорректный формат запроса.
        HTTPException 500: При внутренней ошибке обработки сообщения.

    Notes:
        - Если переданы изображения, они добавляются в начало контента
        - Base64-строки должны быть чистыми (без префикса data:image/...)
        - Изображения автоматически ресайзятся до 4096px
    """
    manager = MessageTypeManager()
    result = await manager.route_message(request)
    return AssistantResponse(answer=result, status="ok")


@router.post("/message/stream")
async def process_signal_stream(
    session_id: str = Form(...),
    text: str = Form(""),
    images: Optional[UploadFile] = File(None),  # 🖼️ Фронт отправляет как "images"
    geo: Optional[str] = Form(None),  # 🗺️ Фронт отправляет JSON строку
    swipe_message_id: Optional[int] = Form(None),  # 👆 свайп старого сообщения (id из dialogue_history)
    system_event: Optional[str] = Form(None),
):
    """
    Обрабатывает сообщение с потоковой передачей ответа.

    Принимает multipart/form-data для поддержки отправки изображений.
    Возвращает ответ в формате JSON Lines (NDJSON) для потоковой передачи. 
    Поддерживает постепенную генерацию текста, отправляя чанки по мере их создания.

    Args:
        session_id: ID сессии пользователя
        text: Текст сообщения от пользователя
        screenshot: Изображение (опционально)
        geo_lat: Широта (опционально)
        geo_lon: Долгота (опционально)
        system_event: Системное событие (опционально)

    Returns:
        StreamingResponse с media_type="application/x-ndjson", содержащий:
        - Чанки текста: {"chunk": "часть текста"}
        - Метаданные: {"metadata": {"track_id": "..."}} (если применимо)
        - Флаг завершения: {"done": true}
        - Ошибки: {"error": "сообщение об ошибке"}

    Raises:
        HTTPException 400: Если запрос некорректный.
        HTTPException 500: При ошибке в процессе потоковой генерации.

    Notes:
        - Каждая строка - валидный JSON объект, разделённый \n
        - Поток закрывается только при отправке {"done": true} или {"error": ...}
        - Поддерживает прерывание соединения клиентом
    """
    # Парсим GeoLocation если пришел JSON
    geo_location = None
    if geo:
        try:
            geo_dict = json.loads(geo)
            from api.schemas.common import GeoLocation
            geo_location = GeoLocation(lat=geo_dict["lat"], lon=geo_dict["lon"])
            logger.info(f"Геолокация: lat={geo_dict['lat']}, lon={geo_dict['lon']}")
        except Exception as e:
            logger.warning(f"Не удалось распарсить geo: {e}")
    
    # Читаем изображение если есть
    screenshot_bytes = None
    mime_type = "image/png"
    if images:
        screenshot_bytes = await images.read()
        mime_type = images.content_type or "image/png"
        logger.info(f"Получено изображение: {len(screenshot_bytes)} bytes, mime={mime_type}")
    
    # Создаем объект request для совместимости с MessageTypeManager
    # (он ожидает объект с атрибутами, а не словарь)
    class RequestObject:
        def __init__(self):
            self.session_id = session_id
            self.text = text
            self.geo = geo_location
            self.screenshot_bytes = screenshot_bytes
            self.mime_type = mime_type
            self.swipe_message_id = swipe_message_id
            self.system_event = system_event
    
    request = RequestObject()
    manager = MessageTypeManager()

    async def jsonlines_stream():
        try:
            async for item in manager.route_message(request):
                if isinstance(item, str):
                    # Текстовый чанк
                    yield json.dumps({"chunk": item}, ensure_ascii=False) + "\n"
                elif isinstance(item, dict):
                    # Метаданные (track_id)
                    yield json.dumps({"metadata": item}, ensure_ascii=False) + "\n"

            # Финальный чанк
            yield json.dumps({"done": True}, ensure_ascii=False) + "\n"

        except Exception as e:
            yield json.dumps({"error": str(e)}, ensure_ascii=False) + "\n"

    return StreamingResponse(
        jsonlines_stream(),
        media_type="application/x-ndjson; charset=utf-8"
    )


@router.get("/assistant-state", response_model=List[AssistantState])
async def get_assistant_state(
        account_id: str = Query(..., min_length=1)
):
    """
    Позволяет отслеживать изменение настроения ассистента в течение диалога.

    Args:
        account_id: Идентификатор пользователя (обязательный параметр)

    Returns:
        Список объектов AssistantState, каждый содержит:
        - state: Текстовое описание состояния/настроения ассистента
        - timestamp: Время записи состояния (если есть в модели)

    Raises:
        HTTPException 404: Если контекст пользователя не найден.
        HTTPException 500: При ошибке чтения или десериализации контекста.

    Notes:
        - История очищается при сбросе сессии пользователя
        - Порядок элементов соответствует хронологии (от старых к новым)
    """
    context_dict = load_serialized_session_context(account_id)
    mood_history = context_dict.get("victor_mood_history", [])

    return [AssistantState(state=m) for m in mood_history]


@router.get("/assistant-mind", response_model=List[AssistantMind])
async def get_assistant_mind(
        account_id: str = Query(..., min_length=1)
):
    """
    Возвращает активные мысли и фокусы внимания ассистента.

    Извлекает два типа ментальных состояний из контекста пользователя:
    1. Якоря (anchors) - эмоциональные якоря
    2. Фокусы (focuses) - текущие точки внимания в диалоге
    Только элементы с флагом True считаются активными.

    Args:
        account_id: Идентификатор пользователя (обязательный параметр)

    Returns:
        Список объектов AssistantMind, каждый содержит:
        - mind: Текст мысли/якоря/фокуса
        - type: Тип ("anchor" для якорей, "focus" для фокусов)

    Raises:
        HTTPException 404: Если контекст пользователя не найден.
        HTTPException 500: При ошибке обработки контекста.

    Notes:
        - Фильтрует записи вида "текст,True/False", оставляя только с True
        - Разделитель - последняя запятая в строке
        - Регистр флага не важен (true/TRUE/True)
    """
    context_dict = load_serialized_session_context(account_id)

    def extract_true_items(raw_list: list[str]) -> list[str]:
        """
        Фильтрует элементы вида "текст,True/False",
        оставляет только текст с флагом True.
        """
        result = []
        for item in raw_list:
            if "," in item:
                text, flag = item.rsplit(",", 1)
                if flag.strip().lower() == "true":
                    result.append(text.strip())
        return result

    # Вытаскиваем мысли
    anchor_links = extract_true_items(context_dict.get("anchor_link_history", []))
    focus_points = extract_true_items(context_dict.get("focus_points_history", []))

    # Формируем список объектов AssistantMind с типами
    anchors = [AssistantMind(mind=text, type="anchor") for text in anchor_links]
    focuses = [AssistantMind(mind=text, type="focus") for text in focus_points]

    # Возвращаем объединённый список
    return anchors + focuses


@router.get("/usage", response_model=List[Usage])
async def get_usage(
        account_id: str = Query(..., min_length=1),
        db: Database = Depends(get_db)
):
    """
    Возвращает агрегированную статистику использования языковых моделей.

    Показывает суммарную информацию по токенам (со всех аккаунтов) 
    и баланс (с test_user). Записи сортируются с приоритетом 
    текущего провайдера пользователя.

    Args:
        account_id: Идентификатор пользователя (используется для определения 
                   предпочитаемого провайдера для сортировки)

    Returns:
        Список объектов Usage, каждый содержит:
        - account_id: ID из запроса (для совместимости с фронтом)
        - model_name: Название использованной модели
        - provider: Провайдер модели (openai, anthropic, и др.)
        - input_tokens_used: Сумма токенов по ВСЕМ аккаунтам
        - output_tokens_used: Сумма токенов по ВСЕМ аккаунтам
        - input_token_price: Средняя цена входного токена
        - output_token_price: Средняя цена выходного токена
        - account_balance: Баланс с test_user

    Raises:
        HTTPException 404: Если записи об использовании не найдены.
        HTTPException 500: При ошибке доступа к базе данных.

    Notes:
        - Токены агрегируются по всем аккаунтам
        - Баланс берется только с test_user
        - Сортировка: записи текущего провайдера пользователя идут первыми
    """
    with db.get_session() as db_session:
        repo = ModelUsageRepository(db_session)
        # Агрегируем токены со всех аккаунтов, баланс берем с test_user
        # Передаем account_id для маркировки результата
        usage_list = repo.get_all_aggregated(account_id=account_id)
        
        # Фильтруем hugging_face провайдер
        usage_list = [u for u in usage_list if u.provider != "hugging_face"]
        
        if not usage_list:
            raise HTTPException(status_code=404, detail="No usage records found")
        
        # 🔍 DEBUG: Логируем что получили (после фильтрации)
        logger.info(f"[USAGE DEBUG] Возвращаем {len(usage_list)} записей для account_id={account_id} (hugging_face отфильтрован)")
        for u in usage_list:
            logger.info(
                f"[USAGE DEBUG] account_id={u.account_id}, provider={u.provider}, model={u.model_name}, "
                f"input_tokens={u.input_tokens_used}, output_tokens={u.output_tokens_used}, "
                f"balance={u.account_balance}"
            )

    # Получаем текущую модель из контекста для сортировки
    context_dict = load_serialized_session_context(account_id)
    model = context_dict.get("model")
    preferred_provider = get_provider_by_model(model, settings.MODEL_SETTINGS, logger)
    
    logger.info(f"[USAGE DEBUG] account_id={account_id}, model={model}, preferred_provider={preferred_provider}")

    # Сортируем usage_list: записи с preferred_provider идут первыми
    if preferred_provider:
        sorted_usage_list = sorted(
            usage_list,
            key=lambda u: u.provider != preferred_provider  # False (0) для preferred_provider, True (1) для остальных
        )
        logger.info(f"[USAGE DEBUG] Отсортировано с приоритетом provider={preferred_provider}")
    else:
        sorted_usage_list = usage_list  # Если провайдер не найден, оставляем исходный порядок
        logger.info(f"[USAGE DEBUG] Сортировка не применена (нет preferred_provider)")

    # Преобразуем в Pydantic-модель Usage
    result = [
        Usage(
            account_id=u.account_id,  # Реальный account_id из запроса
            model_name=u.model_name,
            provider=u.provider,
            input_tokens_used=u.input_tokens_used,
            output_tokens_used=u.output_tokens_used,
            input_token_price=u.input_token_price,
            output_token_price=u.output_token_price,
            account_balance=u.account_balance
        )
        for u in sorted_usage_list
    ]
    
    # 🔍 DEBUG: Логируем финальный результат перед отправкой с расчетом стоимости
    logger.info(f"[USAGE DEBUG] Отправляем на фронт {len(result)} записей")
    for r in result:
        spent = (r.input_tokens_used * r.input_token_price) + (r.output_tokens_used * r.output_token_price)
        remaining = r.account_balance - spent
        logger.info(
            f"[USAGE DEBUG FINAL] account_id={r.account_id}, provider={r.provider}, "
            f"model={r.model_name}, input={r.input_tokens_used}, output={r.output_tokens_used}, "
            f"balance={r.account_balance}, input_price={r.input_token_price}, "
            f"output_price={r.output_token_price}, SPENT=${spent:.4f}, REMAINING=${remaining:.4f}"
        )
    
    return result

@router.get("/memories", response_model=List[MemoryResponse])
async def get_memories(
        account_id: str = Query(..., min_length=1)
):
    """
    Возвращает все сохранённые воспоминания.

    Args:
        account_id: Идентификатор пользователя (обязательный, query-параметр)

    Returns:
        Список объектов MemoryResponse, каждый содержит:
        - id: Уникальный идентификатор записи
        - text: Текст воспоминания
        - embedding: Векторное представление (если включено)
        - metadata: Дополнительные метаданные
        - created_at: Время создания
        - updated_at: Время последнего обновления

    Raises:
        HTTPException 400: Если account_id не указан или короче 1 символа.
        HTTPException 500: При ошибке доступа к векторной БД.

    Notes:
        - Каждый пользователь имеет свою изолированную коллекцию
        - Воспоминания автоматически индексируются для семантического поиска
        - Лимит на количество воспоминаний может быть установлен на уровне провайдера
    """
    logger.info(f"Запрос GET /memories с account_id={account_id}")
    try:
        pipeline = PersonaEmbeddingPipeline()
        records = pipeline.get_collection_contents(account_id)
        logger.info(f"Получено {len(records)} записей для account_id={account_id}")
        return records
    except Exception as e:
        logger.error(f"Ошибка при запросе memories: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


@router.post("/memories/delete")
async def delete_memories(
        account_id: str = Query(..., min_length=1),
        request: DeleteRequest=None
):
    """
    Удаляет указанные воспоминания пользователя.

    Полностью удаляет записи из векторной базы данных по их идентификаторам.
    Операция необратима - удалённые воспоминания не подлежат восстановлению.

    Args:
        account_id: Идентификатор пользователя (обязательный, query-параметр)
        request: Объект DeleteRequest с полем record_ids (список ID для удаления)

    Returns:
        Объект с результатом операции:
        - message: Подтверждение удаления с перечислением ID

    Raises:
        HTTPException 400: Если account_id не указан или record_ids пуст.
        HTTPException 404: Если некоторые ID не найдены в коллекции.
        HTTPException 500: При ошибке удаления из векторной БД.

    Notes:
        - При попытке удалить несуществующий ID возвращается ошибка 404
        - Удаление не влияет на другие записи
    """
    logger.info(f"Запрос POST /memories/delete с account_id={account_id}, record_ids={request.record_ids}")
    try:
        pipeline = PersonaEmbeddingPipeline()
        pipeline.delete_collection_records(account_id, request.record_ids)
        logger.info(f"Успешно удалены записи {request.record_ids} для account_id={account_id}")
        return {"message": f"Записи {request.record_ids} успешно удалены для account_id: {account_id}"}
    except ValueError as e:
        logger.error(f"Ошибка при удалении memories: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при удалении memories: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


@router.put("/memories/update")
async def update_memory(
        record_id: str = Query(..., min_length=1),
        account_id: str = Query(..., min_length=1),
        request: UpdateMemoryRequest=None
):
    """
    Обновляет текст и метаданные существующего воспоминания.

    Изменяет содержание записи и пересчитывает её эмбеддинг в векторной
    базе данных. Полезно для исправления ошибок или уточнения информации.

    Args:
        record_id: Идентификатор обновляемой записи (обязательный, query-параметр)
        account_id: Идентификатор пользователя (обязательный, query-параметр)
        request: Объект UpdateMemoryRequest с полями text и metadata

    Returns:
        Объект с результатом операции:
        - message: Подтверждение обновления с ID записи

    Raises:
        HTTPException 400: Если record_id или account_id не указаны, либо text пустой.
        HTTPException 404: Если запись с указанным record_id не найдена.
        HTTPException 500: При ошибке обновления в векторной БД.

    Notes:
        - При обновлении пересчитывается эмбеддинг текста
        - Время updated_at автоматически обновляется
        - Metadata полностью заменяется (не частичное обновление)
    """
    logger.info(f"Запрос POST /assistant/memories/update с record_id={record_id}, account_id={account_id}, text={request.text[:50]}...")
    try:
        pipeline = PersonaEmbeddingPipeline()
        pipeline.update_entry(account_id, record_id, request.text, request.metadata)
        logger.info(f"Успешно обновлена запись {record_id} для account_id={account_id}")
        return {"message": f"Запись {record_id} успешно обновлена для account_id: {account_id}"}
    except ValueError as e:
        logger.error(f"Ошибка при обновлении memories: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при обновлении memories: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


@router.post("/vision/describe", response_model=VisionDescribeResponse)
async def describe_image(
    account_id: str = Query(..., min_length=1),
    screenshot: UploadFile = File(...),
    text: str = Form(""),
) -> VisionDescribeResponse:
    """
    Тестовый эндпоинт для vision-модели:
    принимает файл-изображение, возвращает extra-context.
    """
    screenshot_bytes = await screenshot.read()
    mime_type = screenshot.content_type or "image/png"

    extra_context = await run_vision_chain(
        account_id=account_id,
        text=text,
        image_bytes=screenshot_bytes,
        mime_type=mime_type,
    )

    return VisionDescribeResponse(content=extra_context)




