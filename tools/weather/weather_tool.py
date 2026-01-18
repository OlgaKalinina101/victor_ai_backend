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

import yaml
from datetime import datetime

from infrastructure.logging.logger import setup_logger
from tools.weather.api_utils import get_weather_data


class WeatherContextBuilder:
    def __init__(self, prompt_path: str = "tools/weather/weather_prompt.yaml"):
        self.logger = setup_logger("weather_tool")
        self.prompt_path = prompt_path
        self.context_template = self._load_prompt_template()

    def _load_prompt_template(self) -> dict:
        try:
            with open(self.prompt_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            self.logger.error(f"Ошибка загрузки {self.prompt_path}: {e}")
            return {}

    async def build(self, latitude: float, longitude: float) -> str:
        """Формирует промпт с погодой по координатам"""
        try:
            weather_data = await get_weather_data(latitude=latitude, longitude=longitude)

            weather_description = (
                f"На улице {weather_data['current_description']}, температура около "
                f"{round(weather_data['current_temperature'])}°C. Ветер {weather_data['wind']} м/с. "
            )

            if weather_data.get("alerts"):
                weather_description += "Предупреждения: " + "; ".join(weather_data["alerts"])

            prompt_template = self.context_template.get("weather_prompt", "")
            now = datetime.now()
            formatted_time = now.strftime("%A, %d %B %Y, %I:%M %p")
            return prompt_template.format(
                weather_context=weather_description,
                local_time=formatted_time
            ).strip()

        except Exception as e:
            self.logger.error(f"Ошибка при формировании weather_context: {e}")
            return ""
