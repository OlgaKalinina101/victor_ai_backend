import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from fastapi import APIRouter, Request, HTTPException, Query
from geoalchemy2.functions import ST_AsGeoJSON
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse, StreamingResponse

from api.helpers import convert_message_history, load_serialized_session_context, get_provider_by_model, \
    get_energy_by_value, get_temperature_by_value
from infrastructure.context_store.session_context_store import SessionContextStore

from infrastructure.database.models import TrackUserDescription, MusicTrack
from infrastructure.database.repositories import save_diary, get_model_usage, get_music_tracks_with_descriptions, \
    get_track_description, save_track_description
from infrastructure.database.session import Database
from infrastructure.firebase.tokens import save_device_token, TOKENS_FILE
from api.firebase_models import TokenRequest
from api.request_models import AssistantRequest, UpdateHistoryRequest, DeleteRequest, UpdateMemoryRequest
from api.response_models import AssistantResponse, Message, Usage, AssistantState, AssistantMind, MemoryResponse, \
    AssistantProvider, TrackDescriptionUpdate
from core.router.message_router import MessageTypeManager
from infrastructure.logging.logger import setup_logger
from infrastructure.pushi.reminders_sender import check_and_send_reminders_pushi
from infrastructure.utils.io_utils import yaml_safe_load
from infrastructure.vector_store.embedding_pipeline import PersonaEmbeddingPipeline
from settings import settings
from tools.places.models import OSMElement
from tools.reminders.reminder_store import ReminderStore

# Настройка логгера для текущего модуля
logger = setup_logger("assistant")

router = APIRouter(prefix="/assistant", tags=["Assistant"])

@router.post("/message", response_model=AssistantResponse)
async def process_signal(request: AssistantRequest):
    """
    Получает текст от Android, выбирает tool и возвращает ответ.
    """
    manager = MessageTypeManager()
    result = await manager.route_message(request)
    return AssistantResponse(answer=result, status="ok")


@router.post("/message/stream")
async def process_signal_stream(request: AssistantRequest):
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

@router.post("/register_token")
async def register_token(req: TokenRequest, request: Request):
    logger.info(f"register_token from {request.client.host} user={req.user_id}")
    save_device_token(req.user_id, req.token)
    return {"status": "ok", "tokens_file": str(TOKENS_FILE)}

@router.post("/reminders/done")
async def reminders_done(req: Dict[str, str]):
    store = ReminderStore()
    store.mark_done(req["reminder_id"])
    return {"status": "ok"}

@router.post("/reminders/delay")
async def reminders_delay(req: Dict[str, str]):
    # +1 час
    store = ReminderStore()
    store.delay_one_hour(req["reminder_id"])
    return {"status": "ok"}

@router.post("/debug/run_reminders")
def debug_run():
    check_and_send_reminders_pushi()
    return {"status": "ran"}


class DiaryEntry(BaseModel):
    account_id: str
    entry_text: str
    timestamp: datetime = datetime.utcnow()

@router.post("/diary", tags=["Diary"])
async def save_diary_entry(entry: DiaryEntry):
    try:
        db = Database()
        db_session = db.get_session()
        save_diary(db_session, entry.account_id, entry.entry_text, entry.timestamp)
        return {"status": "ok"}

    except Exception as e:
        logger.error(f"[diary] Ошибка при сохранении: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/assistant-state", response_model=List[AssistantState])
async def get_assistant_state(account_id: str = "test_user"):
    context_dict = load_serialized_session_context(account_id)
    mood_history = context_dict.get("victor_mood_history", [])

    return [AssistantState(state=m) for m in mood_history]

@router.get("/assistant-mind", response_model=List[AssistantMind])
async def get_assistant_mind(account_id: str = "test_user"):
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

@router.get("/chat/history", response_model=List[Message])
async def get_chat_history(account_id: str = "test_user"):
    context_dict = load_serialized_session_context(account_id)
    raw_history = context_dict.get("message_history", [])

    return convert_message_history(raw_history)


@router.put("/chat/update_history")
async def update_chat_history(
        request: UpdateHistoryRequest,
        account_id: str = "test_user"
):
    """
    Полностью перезаписывает историю чата
    """
    try:
        db = Database()
        db_session = db.get_session()

        # Загружаем существующий контекст
        session_context_store = SessionContextStore(settings.SESSION_CONTEXT_DIR)
        session_context = session_context_store.load(
            account_id=account_id,
            db_session=db_session
        )

        # Конвертируем Message обратно в строковый формат
        raw_history = []
        for msg in request.messages:
            prefix = "user: " if msg.is_user else "assistant: "
            raw_history.append(f"{prefix}{msg.text}")

        # Обновляем историю в контексте
        session_context.message_history = raw_history  # 👈 просто меняем поле

        # Сохраняем (метод save() сам перезапишет YAML файл)
        session_context_store.save(session_context)  # 👈 вот и всё!

        logger.info(f"[history] История обновлена для {account_id}. Всего сообщений: {len(raw_history)}")

        return {
            "success": True,
            "message": f"История обновлена ({len(raw_history)} сообщений)"
        }

    except Exception as e:
        logger.error(f"[history] Ошибка обновления истории: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/usage", response_model=List[Usage])
async def get_usage(account_id: str = "test_user"):
    db = Database()
    db_session = db.get_session()
    usage_list = get_model_usage(account_id, db_session)
    if not usage_list:
        raise HTTPException(status_code=404, detail="No usage records found")

    # Получаем текущую модель из контекста
    context_dict = load_serialized_session_context(account_id)
    model = context_dict.get("model")
    preferred_provider = get_provider_by_model(model, settings.MODEL_SETTINGS, logger)

    # Сортируем usage_list: записи с preferred_provider идут первыми
    if preferred_provider:
        sorted_usage_list = sorted(
            usage_list,
            key=lambda u: u.provider != preferred_provider  # False (0) для preferred_provider, True (1) для остальных
        )
    else:
        sorted_usage_list = usage_list  # Если провайдер не найден, оставляем исходный порядок

    # Преобразуем в Pydantic-модель Usage
    return [
        Usage(
            account_id=u.account_id,
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

@router.get("/reminders", tags=["Reminders"])
async def get_reminders(account_id: str = "test_user"):
    store = ReminderStore(user_id=account_id)
    all_reminders = store._load_all()

    filtered = [r for r in all_reminders if r.get("user_id") == account_id]
    grouped = defaultdict(list)
    for date_key, items in grouped.items():
        for i, item in enumerate(items):
            if "repeatWeekly" not in item:
                logger.warning(f"⚠️ MISSING 'repeatWeekly' at {date_key}[{i}]: {item}")

    for r in filtered:
        repeat = r.get("repeat_weekly", False)
        dt_str = r.get("datetime")

        if not dt_str:
            continue

        try:
            dt = datetime.fromisoformat(dt_str)
        except ValueError:
            continue

        if repeat:
            # повторяющееся — группируем по дню недели
            grouped[dt.strftime("%A").upper()].append({
                "id": r["id"],
                "text": r["text"],
                "datetime": dt.isoformat(),
                "repeat_weekly": True,
                "dayOfWeek": dt.strftime("%A").upper()  # Пример: "FRIDAY"
            })
        else:
            # одноразовое — группируем по дате
            grouped[dt.date().isoformat()].append({
                "id": r["id"],
                "text": r["text"],
                "datetime": dt.isoformat(),  # ← ISO-строка с датой и временем
                "repeat_weekly": False,
                "dayOfWeek": None
            })
    logger.info(f"grouped: {grouped}")
    return JSONResponse(content=grouped or {})

# GET: Получение всех воспоминаний для account_id
@router.get("/memories", response_model=List[MemoryResponse])
async def get_memories(account_id: str = Query(..., min_length=1)):
    logger.info(f"Запрос GET /memories с account_id={account_id}")
    try:
        pipeline = PersonaEmbeddingPipeline()
        records = pipeline.get_collection_contents(account_id)
        logger.info(f"Получено {len(records)} записей для account_id={account_id}")
        return records
    except ValueError as e:
        logger.error(f"Ошибка при запросе memories: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при запросе memories: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


@router.post("/memories/delete")
async def delete_memories(account_id: str = Query(..., min_length=1), request: DeleteRequest=None):
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
async def update_memory(record_id: str = Query(..., min_length=1), account_id: str = Query(..., min_length=1), request: UpdateMemoryRequest=None):
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


@router.get("/tracks")
async def get_tracks_with_descriptions(account_id: str):
    """
    Получает все треки с их описаниями для заданного account_id.

    :param account_id: ID пользователя.
    :return: Список треков с описаниями.
    """
    db = Database()
    session = db.get_session()
    try:
        tracks = get_music_tracks_with_descriptions(session, account_id)
        if not tracks:
            raise HTTPException(status_code=404, detail="Треки не найдены")
        return tracks
    finally:
        session.close()


@router.post("/track-description")
async def update_track_description(update: TrackDescriptionUpdate):
    """
    Обновляет или создаёт описание трека для заданного account_id и track_id.

    :param update: Данные для обновления (account_id, track_id, energy_description, temperature_description).
    :return: Сообщение об успехе.
    """
    logger.info(f"Received update: {update}")
    logger.info(f"account_id: {update.account_id}")
    logger.info(f"track_id: {update.track_id}")
    logger.info(f"energy: {update.energy_description}")
    logger.info(f"temperature: {update.temperature_description}")
    db = Database()
    session = db.get_session()
    try:
        description = get_track_description(session, update.account_id, update.track_id)

        if not description:
            description = TrackUserDescription(
                account_id=update.account_id,
                track_id=update.track_id,
                energy_description=get_energy_by_value(
                    update.energy_description) if update.energy_description else None,
                temperature_description=get_temperature_by_value(
                    update.temperature_description) if update.temperature_description else None
            )
        else:
            if update.energy_description:
                description.energy_description = get_energy_by_value(update.energy_description)
            if update.temperature_description:
                description.temperature_description = get_temperature_by_value(update.temperature_description)

        save_track_description(session, description)
        return {"message": "Описание обновлено"}
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка: {e}")
    finally:
        session.close()


@router.get("/stream/{track_id}")
async def stream_track_media(track_id: int, account_id: str = Query(...)):
    """Прямой стрим для MediaPlayer"""
    db = Database()
    session = db.get_session()

    try:
        track = session.query(MusicTrack).filter(MusicTrack.id == track_id).first()

        if not track:
            raise HTTPException(status_code=404, detail="Трек не найден")

        file_path = Path(track.file_path)

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Файл не найден")

        mime_type = "audio/mpeg"
        if file_path.suffix == ".flac":
            mime_type = "audio/flac"
        elif file_path.suffix == ".wav":
            mime_type = "audio/wav"

        def iterfile():
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    yield chunk

        return StreamingResponse(
            iterfile(),
            media_type=mime_type,
            headers={
                "Content-Disposition": f'inline; filename="{track.filename}"',
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_path.stat().st_size)
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {e}")
    finally:
        session.close()


@router.get("/places")
def get_places(
        limit: int = 15000,
        offset: int = 0,
        bbox: str = None
):
    db = Database()
    session: Session = db.get_session()

    try:
        # 1. Создаём базовый запрос (БЕЗ limit/offset)
        query = session.query(
            OSMElement.id,
            OSMElement.type,
            OSMElement.tags,
            func.ST_AsGeoJSON(OSMElement.geometry).label('geojson')
        )

        # 2. Фильтр по bbox (если есть)
        if bbox:
            coords = [float(x) for x in bbox.split(',')]
            bbox_geom = func.ST_MakeEnvelope(
                coords[0], coords[1],  # min_lon, min_lat
                coords[2], coords[3],  # max_lon, max_lat
                4326
            )
            query = query.filter(
                func.ST_Intersects(OSMElement.geometry, bbox_geom)
            )

        # 3. ТОЛЬКО СЕЙЧАС применяем limit/offset
        elements = query.limit(limit).offset(offset).all()

        # Остальной код без изменений
        result = []
        for el in elements:
            geom = json.loads(el.geojson)
            item = {
                "id": el.id,
                "type": el.type,
                **(el.tags or {}),
            }

            if geom['type'] == 'LineString':
                item["points"] = geom['coordinates']
            elif geom['type'] == 'Point':
                item["point"] = geom['coordinates']
            elif geom['type'] == 'Polygon':
                item["rings"] = geom['coordinates']

            result.append(item)

        return {
            "items": result,
            "count": len(result),
            "limit": limit,
            "offset": offset
        }

    finally:
        session.close()



