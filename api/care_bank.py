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

from pathlib import Path
from typing import List

from fastapi import APIRouter, Form, UploadFile, HTTPException, Depends
from fastapi.params import File

from api.dependencies.runtime import get_db
from api.schemas.care_bank import (
    CareBankEntryRead,
    CareBankEntryCreate,
    ItemSelectionResponse, CareBankSettingsRead, CareBankSettingsUpdate,
)
from infrastructure.database.session import Database
from infrastructure.logging.logger import setup_logger
from tools.carebank.repository import CareBankRepository

router = APIRouter(prefix="/care_bank", tags=["CareBank"])
logger = setup_logger("care_bank_api")


@router.post("", response_model=CareBankEntryRead)
def create_care_bank_entry(payload: CareBankEntryCreate, db: Database = Depends(get_db)):
    """
    Создаёт или обновляет запись в CareBank для пользователя.

    Реализует upsert-поведение: если для пары (account_id, emoji) уже существует
    запись, она будет обновлена новыми значениями полей. Если записи нет —
    создаётся новая. Используется для сохранения сценариев «заботы»:
    эмодзи + координаты кликов, поисковый текст, URL магазина и т.д., чтобы
    агент мог повторять эти действия автоматически.

    Args:
        payload: CareBankEntryCreate — тело запроса с данными записи:
            - account_id: идентификатор пользователя, для которого создаётся сценарий.
            - emoji: уникальный маркер сценария заботы (одна запись на эмодзи).
            - value: человекочитаемое название/описание сценария.
            - timestamp_ms: временная метка создания/обновления сценария в мс.
            - search_url: URL страницы магазина/сервиса, на которой выполнялись действия.
            - search_field: текст поиска/фильтра, который вводился пользователем.
            - add_to_cart_1_coords..add_to_cart_5_coords: координаты кликов
              для добавления товаров в корзину.
            - open_cart_coords: координаты открытия корзины.
            - place_order_coords: координаты оформления заказа.

    Returns:
        CareBankEntryRead: Итоговое состояние записи после создания/обновления,
        включая все сохранённые поля.

    Raises:
        HTTPException 500: Любая внутренняя ошибка при работе с базой данных
        или репозиторием CareBank.

    Notes:
        - Уникальность записей определяется парой (account_id, emoji).
        - Логика upsert полностью инкапсулирована в CareBankRepository.upsert_entry().
        - В случае ошибки подробности фиксируются в логах (logger [care_bank]).
    """
    with db.get_session() as session:
        try:
            repo = CareBankRepository(session)
            
            # Вся логика upsert инкапсулирована в репозитории
            entry = repo.upsert_entry(
                account_id=payload.account_id,
                emoji=payload.emoji,
                value=payload.value,
                timestamp_ms=payload.timestamp_ms,
                search_url=payload.search_url,
                search_field=payload.search_field,
                add_to_cart_1_coords=payload.add_to_cart_1_coords,
                add_to_cart_2_coords=payload.add_to_cart_2_coords,
                add_to_cart_3_coords=payload.add_to_cart_3_coords,
                add_to_cart_4_coords=payload.add_to_cart_4_coords,
                add_to_cart_5_coords=payload.add_to_cart_5_coords,
                open_cart_coords=payload.open_cart_coords,
                place_order_coords=payload.place_order_coords,
            )
            
            logger.info(f"[care_bank] Создана/обновлена запись для {payload.account_id}/{payload.emoji}")
            return entry
            
        except Exception as e:
            logger.error(f"[care_bank] Ошибка создания записи: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/{account_id}", response_model=List[CareBankEntryRead])
def get_care_bank_entries(account_id: str, db: Database = Depends(get_db)):
    """
    Возвращает все записи CareBank для указанного пользователя.

    Используется интерфейсом CareBank для получения списка сохранённых сценариев
    «заботы» (эмодзи + координаты и параметры) для конкретного пользователя.
    Если записей ещё нет, возвращает пустой список.

    Args:
        account_id: Идентификатор пользователя (path-параметр, обязательный).

    Returns:
        List[CareBankEntryRead]: Список всех записей CareBank для данного пользователя.
        Может быть пустым, если пользователь ещё ничего не сохранял.

    Raises:
        HTTPException 500: Любая внутренняя ошибка при работе с базой данных
        или репозиторием CareBank.

    Notes:
        - Эндпоинт не использует пагинацию — возвращает все записи сразу.
        - Порядок записей определяется реализацией хранилища/репозитория
          (обычно по дате создания или обновления).
        - Результат может использоваться для отображения списка сценариев
          и их дальнейшего редактирования или запуска.
    """
    with db.get_session() as session:
        try:
            repo = CareBankRepository(session)
            entries = repo.get_all_entries(account_id)
            
            logger.info(f"[care_bank] Получено {len(entries)} записей для {account_id}")
            return entries
            
        except Exception as e:
            logger.error(f"[care_bank] Ошибка получения записей: {e}")
            raise HTTPException(status_code=500, detail=str(e))

# 📂 Директория для сохранения последнего скриншота (для дебага)
DEBUG_SCREENSHOTS_DIR = Path(__file__).parent.parent / "tools" / "carebank" / "debug_screenshots"


@router.post("/process-screenshot", response_model=ItemSelectionResponse)
async def process_screenshot(
    account_id: str = Form(...),
    screenshot: UploadFile = File(...),
    query: str | None = Form(None),
):
    """
    Анализирует скриншот доставки и выбирает лучшую позицию.

    Args:
        account_id: ID аккаунта пользователя
        screenshot: Скриншот WebView с результатами поиска
        query: Поисковый запрос пользователя (например, "блинчики")

    Returns:
        ItemSelectionResponse: Выбранная позиция с сообщением для пользователя
    """
    from tools.carebank.screenshot_selection import ItemSelector

    # Читаем скриншот в память
    screenshot_bytes = await screenshot.read()
    orig_name = screenshot.filename or "screenshot.png"
    ext = Path(orig_name).suffix or ".png"

    # Определяем MIME-тип
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    mime_type = mime_map.get(ext.lower(), "image/png")

    logger.info(
        f"[care_bank] Получен скриншот от {account_id}, "
        f"query={query}, size={len(screenshot_bytes)} bytes"
    )

    try:
        # Инициализируем селектор
        selector = ItemSelector(account_id=account_id, logger=logger)

        # Получаем сессию БД
        with db.get_session() as db_session:
            # Вызываем выбор позиции
            result = await selector.select_item(
                screenshot_bytes=screenshot_bytes,
                search_query=query or "",
                mime_type=mime_type,
                db_session=db_session,
            )

            # Сохраняем последний скриншот для дебага
            DEBUG_SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
            debug_path = DEBUG_SCREENSHOTS_DIR / f"last_screenshot{ext}"
            with open(debug_path, "wb") as f:
                f.write(screenshot_bytes)
            logger.info(f"[care_bank] Скриншот сохранен для дебага: {debug_path}")

            logger.info(
                f"[care_bank] Выбрана позиция: id={result['id']}, "
                f"match_type={result['match_type']}"
            )

            return ItemSelectionResponse(**result)

    except Exception as e:
        logger.exception(f"[care_bank] Ошибка при обработке скриншота: {e}")
        # Возвращаем дефолтный ответ в случае ошибки
        return ItemSelectionResponse(
            id="0",
            selectedItem="Неизвестно",
            matchType="none",
            userMessage="Извини, что-то пошло не так при анализе скриншота 😔",
        )

@router.get("/settings/{account_id}", response_model=CareBankSettingsRead)
def get_care_bank_settings(account_id: str, db: Database = Depends(get_db)):
    """
    Получает настройки CareBank для пользователя.

    Если настройки ещё не были созданы, инициализирует их с дефолтными
    значениями и сохраняет в базе. Эндпоинт удобно вызывать при старте
    клиента или модуля CareBank, чтобы гарантировать наличие настроек.

    Args:
        account_id: Идентификатор пользователя (path-параметр, обязательный).

    Returns:
        CareBankSettingsRead: Объект настроек CareBank для пользователя.
        Включает либо уже существующие значения, либо только что созданные
        дефолтные настройки.

    Raises:
        HTTPException 500: Любая внутренняя ошибка при работе с базой данных
        или репозиторием CareBank.

    Notes:
        - Если настроек нет, создаются дефолтные (сейчас auto_approved=False).
        - Эндпоинт идемпотентен: при повторных вызовах для одного и того же
          account_id будут возвращаться одни и те же настройки (с учётом
          возможных последующих изменений через другие эндпоинты).
        - Логика создания/обновления настроек инкапсулирована в
          CareBankRepository.create_or_update_settings().
    """
    with db.get_session() as session:
        try:
            repo = CareBankRepository(session)
            settings = repo.get_settings(account_id)

            if not settings:
                # Создаём дефолтные настройки
                settings = repo.create_or_update_settings(
                    account_id=account_id,
                    auto_approved=False,
                )
                logger.info(f"[care_bank] Созданы дефолтные настройки для {account_id}")

            return settings
            
        except Exception as e:
            logger.error(f"[care_bank] Ошибка получения настроек: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings", response_model=CareBankSettingsRead)
def upsert_care_bank_settings(payload: CareBankSettingsUpdate, db: Database = Depends(get_db)):
    """
    Создаёт или обновляет настройки Care Bank для пользователя.

    Реализует upsert-логику: если настройки существуют — обновляет указанные поля,
    если нет — создаёт новую запись. Поддерживает частичное обновление.

    Args:
        payload: Объект CareBankSettingsUpdate, содержащий:
            - account_id: Идентификатор пользователя (обязательный)
            - auto_approved: Автоподтверждение заказов (опционально)
            - presence_address: Адрес присутствия (опционально)
            - max_order_cost: Максимальная стоимость (опционально)
            - preferred_taxi_class: Класс такси (опционально)

    Returns:
        CareBankSettingsRead: Обновлённые или созданные настройки.

    Raises:
        HTTPException 400: Если отсутствует account_id.
        HTTPException 422: Если невалидные значения полей.
        HTTPException 500: При ошибке работы с базой данных.

    Notes:
        - Обновляет только те поля, которые явно переданы (не null)
        - auto_approved по умолчанию False при создании новой записи
        - При обновлении существующей записи сохраняет старые значения для полей, не переданных в payload
        - Все строковые поля обрезаются от пробелов
    """
    with db.get_session() as session:
        try:
            repo = CareBankRepository(session)
            
            # Собираем только переданные поля
            update_fields = {}
            if payload.auto_approved is not None:
                update_fields["auto_approved"] = payload.auto_approved
            if payload.presence_address is not None:
                update_fields["presence_address"] = payload.presence_address
            if payload.max_order_cost is not None:
                update_fields["max_order_cost"] = payload.max_order_cost
            if payload.preferred_taxi_class is not None:
                update_fields["preferred_taxi_class"] = payload.preferred_taxi_class
            
            # Если не переданы поля - ставим дефолт для auto_approved при создании
            if not update_fields and not repo.get_settings(payload.account_id):
                update_fields["auto_approved"] = False
            
            settings = repo.create_or_update_settings(
                account_id=payload.account_id,
                **update_fields
            )
            
            logger.info(f"[care_bank] Обновлены настройки для {payload.account_id}: {list(update_fields.keys())}")
            return settings
            
        except Exception as e:
            logger.error(f"[care_bank] Ошибка обновления настроек: {e}")
            raise HTTPException(status_code=500, detail=str(e))

