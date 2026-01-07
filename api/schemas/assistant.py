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

"""
Схемы для эндпоинта /assistant.

Содержит модели запросов и ответов для работы с ассистентом,
включая обработку сообщений, управление памятью и состояниями.
"""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel

from api.schemas.common import GeoLocation, ImageContent


class AssistantRequest(BaseModel):
    """
    Запрос на обработку сообщения ассистентом.
    
    Поддерживает текстовые и мультимодальные запросы с изображениями,
    геолокацией и системными событиями.
    """
    session_id: str
    text: str
    geo: Optional[GeoLocation] = None
    images: Optional[List[ImageContent]] = None
    system_event: Optional[str] = None


class AssistantResponse(BaseModel):
    """
    Ответ ассистента на сообщение пользователя.
    """
    answer: str
    status: str


class AssistantState(BaseModel):
    """
    Состояние/настроение ассистента в конкретный момент.
    
    Используется для отслеживания эмоционального состояния
    и настроения ассистента в течение диалога.
    """
    state: str


class AssistantMind(BaseModel):
    """
    Активная мысль или фокус внимания ассистента.
    
    Представляет якоря (эмоциональные привязки) и фокусы
    (текущие точки внимания) в сознании ассистента.
    """
    mind: str
    type: Literal["anchor", "focus"]


class AssistantProvider(BaseModel):
    """
    Информация о провайдере языковой модели.
    """
    provider: str


class MemoryResponse(BaseModel):
    """
    Сохранённое воспоминание из векторной базы данных.
    
    Используется для возврата записей из долговременной памяти
    ассистента о пользователе.
    """
    id: str
    text: str
    metadata: Dict[str, Any]


class DeleteRequest(BaseModel):
    """
    Запрос на удаление записей из памяти.
    """
    record_ids: List[str]


class UpdateMemoryRequest(BaseModel):
    """
    Запрос на обновление записи в памяти.
    """
    text: str
    metadata: Optional[Dict[str, Any]] = None


class VisionImageRequest(BaseModel):
    """
    Запрос для теста vision-модели.

    Принимает одно изображение в формате base64
    в том же формате, что и AssistantRequest.images.
    """
    image: ImageContent


class VisionDescribeResponse(BaseModel):
    content: str

