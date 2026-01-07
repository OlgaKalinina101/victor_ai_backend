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
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import FileResponse
from starlette.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from api.dependencies.runtime import get_db

from api.helpers import get_energy_by_value, get_temperature_by_value
from api.schemas.tracks import PlaylistMomentOut, TrackDescriptionUpdate
from infrastructure.database.database_enums import (
    EnergyDescription,
    TemperatureDescription,
)
from infrastructure.database.session import Database
from infrastructure.logging.logger import setup_logger
from infrastructure.database.repositories.chat_meta_repository import ChatMetaRepository
from tools.playlist.repository import PlaylistRepository
from tools.playlist.playlist_tool import run_playlist_chain
from tools.playlist.playlist_builder import PlaylistContextBuilder

logger = setup_logger("tracks")

router = APIRouter(prefix="/tracks", tags=["tracks"])


@router.get("/history")
async def get_track_history(account_id: str = Query(...)):
    """
    Получает полную историю прослушиваний треков для указанного пользователя.

    Возвращает хронологический список всех воспроизведённых треков пользователя
    с детальной информацией о каждом прослушивании, включая метаданные трека,
    время начала/окончания и контекстные данные (энергия, температура).

    Args:
        account_id: Идентификатор пользователя (обязательный параметр).

    Returns:
        Список объектов истории прослушиваний, отсортированный по убыванию времени начала.
    """
    db = Database.get_instance()
    with db.get_session() as session:
        try:
            repo = PlaylistRepository(session)
            history = repo.get_play_history(account_id)

            result = []
            for h in history:
                result.append({
                    "id": h.id,
                    "track_id": h.track_id,
                    "title": h.track.title if h.track else None,
                    "artist": h.track.artist if h.track else None,
                    "album": h.track.album if h.track else None,
                    "started_at": h.started_at.isoformat() if h.started_at else None,
                    "ended_at": h.ended_at.isoformat() if h.ended_at else None,
                    "duration_played": h.duration_played,
                    "energy_on_play": h.energy_on_play.value if h.energy_on_play else None,
                    "temperature_on_play": h.temperature_on_play.value if h.temperature_on_play else None,
                })

            logger.info(f"[tracks] Получена история для {account_id}: {len(result)} записей")
            return result

        except Exception as e:
            logger.error(f"[tracks] Ошибка получения истории: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка получения истории: {e}")


@router.get("/playlist_moments", response_model=List[PlaylistMomentOut])
async def get_playlist_moments(
    account_id: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Возвращает историю моментов выбора трека (PlaylistMoment) для пользователя.

    В ответе возвращаются:
    - stage1_text / stage2_text / stage3_text
    - все системные поля момента (id, account_id, created_at, track_id)
    - вложенный `track` (если выбранный трек есть в моменте)
    """
    db = Database.get_instance()
    with db.get_session() as session:
        try:
            repo = PlaylistRepository(session)
            moments = repo.get_playlist_moments(account_id=account_id, limit=limit)
            return [PlaylistMomentOut.model_validate(m) for m in moments]
        except Exception as e:
            logger.error(f"[tracks] Ошибка получения playlist moments: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка получения playlist moments: {e}")


@router.get("/stats")
async def get_track_statistics(
    account_id: str = Query(...),
    period: str = Query("week", description="week or month")
):
    """
    Возвращает агрегированную статистику по прослушиваниям пользователя за указанный период.

    Анализирует музыкальные предпочтения пользователя, предоставляя:
    - Общее количество прослушиваний
    - Топ-5 самых прослушиваемых треков
    - Преобладающие уровни энергии и температуры
    - Среднюю продолжительность прослушивания
    """
    db = Database.get_instance()
    with db.get_session() as session:
        try:
            repo = PlaylistRepository(session)
            
            now = datetime.utcnow()
            start = now - timedelta(days=30 if period == "month" else 7)
            
            # Получаем статистику через репозиторий
            stats = repo.get_period_statistics(account_id, start)
            
            logger.info(
                f"[tracks] Статистика для {account_id} ({period}): "
                f"{stats['total_plays']} прослушиваний"
            )
            
            return {
                "period": period,
                "from": start.isoformat(),
                "to": now.isoformat(),
                **stats
            }

        except Exception as e:
            logger.error(f"[tracks] Ошибка получения статистики: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка при получении статистики: {e}")


@router.post("/run_playlist_wave")
async def run_playlist_wave(
    account_id: str = Query(...),
    energy: Optional[str] = Query(None),
    temperature: Optional[str] = Query(None),
    limit: int = Query(20)   # сколько треков в “волне”
):
    """
    Генерирует "волну" треков на основе:
    - Текущее желаемое состояние (энергия/температура)

    Алгоритм выбирает треки из базы, помеченные пользователем с указанными
    характеристиками, и возвращает их в случайном порядке для создания
    разнообразного потока музыки.

    Args:
        account_id: Идентификатор пользователя (обязательный параметр).
        energy: Желаемый уровень энергии для подбора треков.
                Допустимые значения: "low", "medium", "high" или None.
        temperature: Желаемая температурная характеристика.
                    Допустимые значения: "cold", "neutral", "warm" или None.
        limit: Максимальное количество треков в возвращаемой "волне".
               По умолчанию 20.

    Returns:
        Объект с подобранной "волной" треков:
        - tracks: Список треков с метаданными и stream_url для воспроизведения
        - energy: Использованный уровень энергии для фильтрации
        - temperature: Использованная температурная характеристика
        - message: Информационное сообщение (если треки не найдены)

    Raises:
        HTTPException 400: Если `account_id` не указан или параметры невалидны.
        HTTPException 500: При ошибке базы данных или подбора треков.
    """
    energy_enum = EnergyDescription.from_value(energy) if energy else None
    temp_enum = TemperatureDescription.from_value(temperature) if temperature else None

    db = Database.get_instance()
    with db.get_session() as session:
        try:
            # Если у пользователя нет TrackUserDescription — создаём дефолты из test_user
            ChatMetaRepository(session).ensure_track_descriptions_seeded(account_id=account_id)

            repo = PlaylistRepository(session)
            
            # Подбираем треки через репозиторий
            tracks = repo.get_tracks_by_energy_temperature(
                account_id=account_id,
                energy=energy_enum,
                temperature=temp_enum,
                limit=limit
            )

            if not tracks:
                logger.info(f"[tracks] Нет треков для {account_id} с energy={energy}, temp={temperature}")
                return {
                    "tracks": [],
                    "message": "Нет треков под такие энергию и температуру"
                }

            # Собираем payload для фронта
            payload = []
            for t in tracks:
                # Берём описание именно этого пользователя
                desc = next(
                    (d for d in t.user_descriptions if d.account_id == account_id),
                    None
                )
                payload.append({
                    "id": t.id,
                    "title": t.title,
                    "artist": t.artist,
                    "duration": t.duration,
                    "energy_description": getattr(desc, "energy_description", None),
                    "temperature_description": getattr(desc, "temperature_description", None),
                    "stream_url": f"/stream/{t.id}?account_id={account_id}",
                })

            logger.info(f"[tracks] Подобрано {len(payload)} треков для {account_id} (волна)")
            
            return {
                "tracks": payload,
                "energy": energy,
                "temperature": temperature,
            }

        except Exception as e:
            logger.error(f"[tracks] Ошибка подбора волны: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка подбора волны: {e}")


@router.get("")
async def get_tracks_with_descriptions(
        account_id: str
):
    """
    Возвращает все треки пользователя с их персонализированными описаниями.

    Получает полный список музыкальных треков, доступных пользователю,
    вместе с описаниями (энергия, температура), которые пользователь
    ранее назначил каждому треку. Если описания отсутствуют, соответствующие
    поля будут иметь значение null.

    Args:
        account_id: Идентификатор пользователя (обязательный параметр).

    Returns:
        Список объектов треков, каждый из которых содержит:
        - Основные метаданные трека (id, title, artist, album, duration, file_path)
        - Пользовательские описания (energy_description, temperature_description)
        - Флаг наличия файла для воспроизведения

    Raises:
        HTTPException 400: Если `account_id` не указан или пуст.
        HTTPException 404: Если для пользователя не найдено ни одного трека.
        HTTPException 500: При внутренней ошибке базы данных.
    """
    db = Database.get_instance()
    with db.get_session() as session:
        try:
            # Если у пользователя нет TrackUserDescription — создаём дефолты из test_user
            ChatMetaRepository(session).ensure_track_descriptions_seeded(account_id=account_id)

            repo = PlaylistRepository(session)
            tracks = repo.get_tracks_with_descriptions(account_id)
            
            if not tracks:
                raise HTTPException(status_code=404, detail="Треки не найдены")
            
            logger.info(f"[tracks] Получено {len(tracks)} треков с описаниями для {account_id}")
            return tracks
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[tracks] Ошибка получения треков: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка получения треков: {e}")


@router.post("/update_track_description")
async def update_track_description(
        account_id: str = Query(...),
        update: TrackDescriptionUpdate = ...,
):
    """
    Обновляет или создаёт персонализированное описание трека для пользователя.

    Позволяет пользователю аннотировать треки характеристиками "энергия" и "температура".
    Если описание для данной пары (пользователь, трек) уже существует, оно обновляется.
    В противном случае создаётся новая запись.

    Args:
        account_id: Идентификатор пользователя.
        update: Объект обновления описания трека, содержащий:
            - track_id: Идентификатор трека
            - energy_description: Уровень энергии ("low", "medium", "high" или null)
            - temperature_description: Температурная характеристика ("cold", "neutral", "warm" или null)

    Returns:
        Объект с сообщением об успешном выполнении:
        {
            "message": "Описание обновлено"
        }

    Raises:
        HTTPException 400: Если данные запроса невалидны или отсутствуют обязательные поля.
        HTTPException 404: Если указанный трек не существует.
        HTTPException 500: При ошибке сохранения в базу данных.
    """
    logger.info(
        f"[tracks] Обновление описания для {account_id}, track_id={update.track_id}, "
        f"energy={update.energy_description}, temp={update.temperature_description}"
    )
    
    db = Database.get_instance()
    with db.get_session() as session:
        try:
            repo = PlaylistRepository(session)
            
            # Конвертируем строковые значения в enums
            energy = get_energy_by_value(update.energy_description) if update.energy_description else None
            temperature = get_temperature_by_value(update.temperature_description) if update.temperature_description else None
            
            # Используем upsert из репозитория
            repo.upsert_track_description(
                account_id=account_id,
                track_id=update.track_id,
                energy_description=energy,
                temperature_description=temperature
            )
            
            logger.info(f"[tracks] Описание трека {update.track_id} обновлено для {account_id}")
            return {"message": "Описание обновлено"}
            
        except Exception as e:
            logger.error(f"[tracks] Ошибка обновления описания: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка: {e}")


@router.get("/stream/{track_id}")
async def stream_track_media(
        track_id: int,
        account_id: str = Query(...)
):
    """
    Потоковая передача аудиофайла трека с автоматическим логированием прослушивания.

    Основной эндпоинт для воспроизведения музыки через ExoPlayer (Android).
    При каждом запросе:
    1. Проверяет существование файла трека
    2. Определяет MIME-тип по расширению файла
    3. Создаёт запись в истории прослушиваний
    4. Возвращает файл в виде потокового ответа

    Args:
        track_id: Идентификатор трека (из пути URL).
        account_id: Идентификатор пользователя (обязательный query-параметр).

    Returns:
        FileResponse с аудиофайлом, готовым для потокового воспроизведения.
        Заголовки ответа включают правильный Content-Type и Content-Disposition.

    Raises:
        HTTPException 404: Если трек с указанным ID не найден или файл отсутствует.
        HTTPException 500: При ошибке чтения файла или записи истории прослушивания.

    Note:
        История прослушивания записывается даже при ошибках логирования,
        чтобы не прерывать воспроизведение для пользователя.
    """
    db = Database.get_instance()
    with db.get_session() as session:
        try:
            repo = PlaylistRepository(session)
            
            # Получаем трек через репозиторий
            track = repo.get_track_by_id(track_id)
            if not track:
                raise HTTPException(status_code=404, detail="Трек не найден")

            file_path = Path(track.file_path)
            if not file_path.exists():
                raise HTTPException(status_code=404, detail="Файл не найден")

            # Определяем MIME
            suffix = file_path.suffix.lower()
            mime_type = (
                "audio/flac" if suffix == ".flac"
                else "audio/wav" if suffix == ".wav"
                else "audio/mpeg"
            )

            # 💾 Безопасно логируем начало прослушивания
            try:
                logger.info(f"[tracks] Стрим: track={track.id} ({track.title}), user={account_id}")
                
                # Получаем описание пользователя для трека
                desc = repo.get_track_description(account_id, track.id)
                
                # Записываем историю прослушивания
                repo.create_play_record(
                    account_id=account_id,
                    track_id=track.id,
                    started_at=datetime.utcnow(),
                    energy_on_play=desc.energy_description if desc else None,
                    temperature_on_play=desc.temperature_description if desc else None
                )
                
                logger.info(f"[tracks] ✅ Записано прослушивание: {track.title}")
                
            except Exception as log_error:
                logger.error(f"[tracks] ⚠️ Ошибка логирования трека {track.id}: {log_error}")

            # 🎵 Возвращаем файл — независимо от результата логирования
            return FileResponse(
                file_path,
                media_type=mime_type,
                filename=track.filename,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[tracks] ❌ Ошибка стриминга трека {track_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка: {e}")


@router.post("/choose_for_me")
async def run_playlist_chain_endpoint(
    account_id: str = Query(...),
    extra_context: str = Query(None)
):
    """
    Запускает подбор трека (волну) по кнопке "выбери сам".

    Args:
        account_id: Идентификатор пользователя (обязательный параметр).
        extra_context: Дополнительный текстовый контекст для уточнения подбора.
                      Например: "для тренировки", "расслабиться", "сосредоточиться".

    Returns:
        Объект с подобранным треком и контекстом выбора:
        {
            "track": { ... метаданные трека ... },
            "context": "Кусочек промпта (extra_context) для основного пайплайне, в эндпоинте не используется."
        }

    Raises:
        HTTPException 400: Если `account_id` не указан.
        HTTPException 404: Если не удалось подобрать подходящий трек.
        HTTPException 500: При ошибке алгоритма подбора или базы данных.
    """
    try:
        track_data, context = await run_playlist_chain(
            account_id=account_id,
            extra_context=extra_context
        )

        return {
            "track": track_data,
            "context": context
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка запуска волны: {e}")


@router.post("/choose_for_me/stream")
async def run_playlist_chain_stream(
    account_id: str = Query(...),
    extra_context: str = Query(None)
):
    """
    Streaming версия подбора трека с живыми логами после каждой стадии.
    
    Возвращает поток событий в формате NDJSON (JSON Lines):
    - {"log": "текст лога"} - прогресс подбора и reasoning после каждой стадии
    - {"track": {...}} - итоговый трек с метаданными
    - {"context": "..."} - контекст для основного пайплайна
    - {"done": true} - маркер завершения
    - {"error": "..."} - ошибка при выполнении
    
    Args:
        account_id: Идентификатор пользователя (обязательный параметр).
        extra_context: Дополнительный текстовый контекст для уточнения подбора.
    
    Returns:
        StreamingResponse в формате application/x-ndjson с постепенной отправкой логов.
        
    Raises:
        HTTPException 400: Если `account_id` не указан.
        HTTPException 500: При критической ошибке подбора.
        
    Example response stream:
        {"log": "🎵 анализирую твоё настроение..."}
        {"log": "вижу что ты устала 😔 нужно что-то тёплое"}
        {"log": "🎤 выбираю исполнителя..."}
        {"log": "её голос как тёплое одеяло ✨"}
        {"log": "🎼 ищу идеальный трек..."}
        {"log": "эта песня про надежду 💫 пусть всё сбудется"}
        {"track": {"track_id": 123, "track": "...", "artist": "..."}}
        {"context": "..."}
        {"done": true}
    """
    
    logger.info(f"[tracks] 🎵 Начало streaming для account_id={account_id}, extra_context={extra_context}")
    
    async def jsonlines_stream():
        """Генератор потока данных в формате JSON Lines"""
        line_count = 0
        try:
            logger.info(f"[tracks] 📦 Создаём PlaylistContextBuilder для {account_id}")
            builder = PlaylistContextBuilder(
                account_id=account_id,
                extra_context=extra_context
            )
            
            logger.info(f"[tracks] 🔄 Начинаем генерацию логов через build_with_logs()")
            
            # Стримим логи и данные по мере их генерации
            async for item in builder.build_with_logs():
                line_count += 1
                line = json.dumps(item, ensure_ascii=False) + "\n"
                logger.info(f"[tracks] 📝 Отправляем строку #{line_count}: {line.strip()[:100]}...")
                yield line
            
            # Финальный маркер
            line_count += 1
            final_line = json.dumps({"done": True}, ensure_ascii=False) + "\n"
            logger.info(f"[tracks] ✅ Отправляем финальную строку #{line_count}: {final_line.strip()}")
            yield final_line
            
            logger.info(f"[tracks] 🎉 Stream успешно завершён для {account_id}. Всего строк: {line_count}")
            
        except Exception as e:
            line_count += 1
            error_line = json.dumps({"error": str(e)}, ensure_ascii=False) + "\n"
            logger.error(f"[tracks] ❌ Ошибка в streaming подборе (строка #{line_count}): {e}", exc_info=True)
            yield error_line
    
    return StreamingResponse(
        jsonlines_stream(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Отключаем nginx buffering
            "Connection": "keep-alive",
        }
    )


@router.get("/choose_for_me/stream_sse")
async def run_playlist_chain_stream_sse(
    account_id: str = Query(...),
    extra_context: str = Query(None)
):
    """
    SSE (Server-Sent Events) версия подбора трека - лучше работает через ngrok!
    
    SSE автоматически обходит большинство прокси-буферизаций.
    Формат: text/event-stream с событиями вида:
        event: log
        data: {"text": "🎵 анализирую..."}
        
        event: track
        data: {"track_id": 123, ...}
    
    Args:
        account_id: Идентификатор пользователя
        extra_context: Дополнительный контекст
    
    Returns:
        EventSourceResponse с постепенной отправкой событий
    """
    
    logger.info(f"[tracks] 🎵 Начало SSE streaming для account_id={account_id}")
    
    async def event_generator():
        """Генератор SSE событий"""
        event_count = 0
        try:
            builder = PlaylistContextBuilder(
                account_id=account_id,
                extra_context=extra_context
            )
            
            logger.info(f"[tracks] 🔄 Начинаем генерацию SSE событий")
            
            async for item in builder.build_with_logs():
                event_count += 1
                
                if "log" in item:
                    # Событие лога
                    logger.info(f"[tracks] 📝 SSE событие #{event_count}: log")
                    yield {
                        "event": "log",
                        "data": json.dumps({"text": item["log"]}, ensure_ascii=False)
                    }
                    
                elif "track" in item:
                    # Событие трека
                    logger.info(f"[tracks] 🎧 SSE событие #{event_count}: track")
                    yield {
                        "event": "track",
                        "data": json.dumps(item["track"], ensure_ascii=False)
                    }
                    
                elif "context" in item:
                    # Событие контекста
                    logger.info(f"[tracks] 📋 SSE событие #{event_count}: context")
                    yield {
                        "event": "context",
                        "data": json.dumps({"context": item["context"]}, ensure_ascii=False)
                    }
                    
                elif "error" in item:
                    # Событие ошибки
                    logger.error(f"[tracks] ❌ SSE событие #{event_count}: error")
                    yield {
                        "event": "error",
                        "data": json.dumps({"error": item["error"]}, ensure_ascii=False)
                    }
            
            # Финальное событие
            event_count += 1
            logger.info(f"[tracks] ✅ SSE событие #{event_count}: done")
            yield {
                "event": "done",
                "data": json.dumps({"done": True}, ensure_ascii=False)
            }
            
            logger.info(f"[tracks] 🎉 SSE stream завершён. Всего событий: {event_count}")
            
        except Exception as e:
            event_count += 1
            logger.error(f"[tracks] ❌ Ошибка в SSE streaming: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}, ensure_ascii=False)
            }
    
    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )
