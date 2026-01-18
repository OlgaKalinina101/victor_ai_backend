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

from io import BytesIO
from logging import Logger
from pathlib import Path
from typing import Optional, Dict, Any

from PIL import Image

from infrastructure.logging.logger import setup_logger
from infrastructure.utils.io_utils import yaml_safe_load
from infrastructure.vision import VisionClient

# Путь к промптам Vision
PROMPTS_PATH = Path(__file__).parent / "vision_prompts.yaml"


class VisionBuilder:
    """
    Обёртка над vision-моделью:
    1) определяет тип изображения (photo / ui_screenshot / dialogue_screenshot),
    2) строит короткий текстовый vision-context для партнёра.
    """

    def __init__(
        self,
        model: str = "Qwen/Qwen3-VL-8B-Instruct:novita",
        api_url: str = "https://router.huggingface.co/v1/chat/completions",
        api_token: Optional[str] = None,
        logger: Optional[Logger] = None,
        account_id: str = None,
    ) -> None:
        self.logger = logger or setup_logger("vision_builder")

        self.client = VisionClient(
            model=model,
            api_url=api_url,
            api_token=api_token,
            logger=self.logger,
            timeout=30,
            account_id=account_id,
        )

        # Промпты для всех стадий vision-пайплайна
        self.prompts: Dict[str, str] = yaml_safe_load(PROMPTS_PATH, self.logger)
        self.system_prompt: str = self.prompts.get("vision_system_prompt", "")
        self.image_type_prompt_tpl: str = self.prompts.get("vision_image_type_prompt", "")
        self.vision_context_tpl: str = self.prompts.get("vision_context_prompt", "")
        
        # Настройки сжатия изображений
        self.max_image_size = 1024  # Максимальный размер по длинной стороне
        self.jpeg_quality = 85  # Качество JPEG сжатия

    # ---------- сжатие изображения ----------

    def compress_image(self, image_bytes: bytes, mime_type: str = "image/png") -> bytes:
        """
        Сжимает изображение до приемлемого размера для API.
        
        Args:
            image_bytes: Исходные байты изображения
            mime_type: MIME-тип изображения
            
        Returns:
            Сжатые байты изображения
        """
        try:
            # Открываем изображение
            img = Image.open(BytesIO(image_bytes))
            
            # Конвертируем RGBA в RGB для JPEG
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            
            original_size = img.size
            original_bytes = len(image_bytes)
            
            # Ресайзим если изображение слишком большое
            if max(img.size) > self.max_image_size:
                # Вычисляем новый размер с сохранением пропорций
                ratio = self.max_image_size / max(img.size)
                new_size = tuple(int(dim * ratio) for dim in img.size)
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                self.logger.info(f"[COMPRESS] Изображение изменено с {original_size} на {new_size}")
            
            # Сохраняем в JPEG с умеренным сжатием
            output = BytesIO()
            img.save(output, format='JPEG', quality=self.jpeg_quality, optimize=True)
            compressed_bytes = output.getvalue()
            
            compressed_size = len(compressed_bytes)
            compression_ratio = (1 - compressed_size / original_bytes) * 100
            
            self.logger.info(
                f"[COMPRESS] Сжатие: {original_bytes} bytes -> {compressed_size} bytes "
                f"({compression_ratio:.1f}% экономии)"
            )
            
            return compressed_bytes
            
        except Exception as e:
            self.logger.warning(f"[COMPRESS] Ошибка сжатия изображения: {e}, используем оригинал")
            return image_bytes

    # ---------- промпт для второй стадии (контекст) ----------

    def build_visual_context_prompt(self, image_type: str, user_input: str) -> str:
        """
        Собирает промпт для второй стадии (построение человекочитаемого описания),
        исходя из типа изображения и исходного текста пользователя.
        """

        type_to_prompt_key = {
            "photo": "vision_photo_context_prompt",
            "ui_screenshot": "vision_ui_screenshot_context_prompt",
            "dialogue_screenshot": "vision_dialogue_screenshot_context_prompt",
        }

        prompt_key = type_to_prompt_key.get(image_type, "vision_default_context_prompt")
        template = self.prompts.get(prompt_key, "")

        if not template:
            # Фолбэк на случай отсутствия конфигурации
            return ""

        return template.format(user_input=user_input)

    # ---------- стадия 1: определяем image_type ----------

    async def _detect_image_type(
        self,
        text: str,
        image_bytes: bytes,
        mime_type: str,
    ) -> str:
        """
        Вызывает vision-модель для определения типа изображения.
        Возвращает одно из: 'photo', 'ui_screenshot', 'dialogue_screenshot' или ''.
        """

        if not self.image_type_prompt_tpl:
            self.logger.warning("Не задан vision_image_type_prompt в промптах")
            return ""

        prompt = self.image_type_prompt_tpl.format(user_input=text)

        result: Dict[str, Any] = await self.client.analyze_json(
            image=image_bytes,
            prompt=prompt,
            system_prompt=self.system_prompt,
            mime_type=mime_type,
            temperature=0.0,
        )

        image_type = result.get("image_type", "")

        if not image_type:
            self.logger.warning(
                "Ответ vision-модели не содержит 'image_type'. result=%s",
                result,
            )

        return image_type

    # ---------- стадия 2: строим человекочитаемый vision_context ----------

    async def _build_vision_context(
        self,
        image_type: str,
        text: str,
        image_bytes: bytes,
        mime_type: str,
    ) -> str:
        """
        Строит короткий vision-context для Victor AI по типу изображения.
        """

        context_prompt = self.build_visual_context_prompt(
            image_type=image_type,
            user_input=text,
        )

        result: Dict[str, Any] = await self.client.analyze_json(
            image=image_bytes,
            prompt=context_prompt,
            system_prompt=self.system_prompt,
            mime_type=mime_type,
            temperature=0.0,
        )

        content: str = result.get("content", "") or ""

        if not content:
            self.logger.info(
                "Vision-контекст не содержит 'content', возвращаем пустой vision_context"
            )
            return ""

        # Если есть отдельный шаблон для финального vision_context — используем его,
        # иначе просто возвращаем content как есть.
        if self.vision_context_tpl:
            try:
                # Определяем текст в зависимости от типа изображения
                if image_type == "photo":
                    image_type_text = "фотографией"
                elif image_type in ["ui_screenshot", "dialogue_screenshot"]:
                    image_type_text = "скриншотом"
                else:
                    image_type_text = "изображением"
                
                vision_context = self.vision_context_tpl.format(
                    image_type_text = image_type_text,
                    content=content
                )
            except Exception:
                self.logger.exception(
                    "Ошибка форматирования vision_context_tpl, "
                    "возвращаем сырой content"
                )
                vision_context = content
        else:
            vision_context = content

        return vision_context

    # ---------- публичный метод ----------

    async def analyze_screenshot(
        self,
        text: str,
        image_bytes: bytes,
        mime_type: str = "image/png",
    ) -> str:
        """
        Анализирует изображение и возвращает vision-context для диалога.

        Args:
            text: Текст, который пришёл вместе с изображением (сообщение пользователя).
            image_bytes: байты изображения (фото / скриншот).
            mime_type: MIME-тип изображения.

        Returns:
            Строка для подмешивания в context_prompt (например:
            "Факт пространства: ...", "Контекст сцены: ...").
            В случае ошибки — пробрасывает исключение.
        """

        self.logger.info("Анализ изображения для сообщения: %s", text[:100])

        try:
            # 🔥 СЖИМАЕМ изображение перед отправкой в API
            compressed_image_bytes = self.compress_image(image_bytes, mime_type)
            
            image_type = await self._detect_image_type(
                text=text,
                image_bytes=compressed_image_bytes,
                mime_type="image/jpeg",  # После сжатия всегда JPEG
            )

            vision_context = await self._build_vision_context(
                image_type=image_type,
                text=text,
                image_bytes=compressed_image_bytes,
                mime_type="image/jpeg",  # После сжатия всегда JPEG
            )

            self.logger.info("Vision context: %s", vision_context or "<empty>")
            return vision_context

        except Exception as e:
            self.logger.exception("Ошибка при анализе изображения: %s", e)
            raise



