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

from typing import Optional

import aiohttp
from datetime import datetime, timedelta

from settings import settings


async def get_weather_data(latitude: float, longitude: float) -> Optional[dict]:
    """Получает погоду по API Open Weather"""
    current_url = (
        f"http://api.openweathermap.org/data/2.5/weather?"
        f"lat={latitude}&lon={longitude}&units=metric&appid={settings.OPENWEATHER_API_KEY}"
    )
    forecast_url = (
        f"http://api.openweathermap.org/data/2.5/forecast?"
        f"lat={latitude}&lon={longitude}&units=metric&appid={settings.OPENWEATHER_API_KEY}"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(current_url) as current_response:
                if current_response.status != 200:
                    print(f"[ERROR] OpenWeather current response status: {current_response.status}")
                    return None
                current_data = await current_response.json()

            async with session.get(forecast_url) as forecast_response:
                if forecast_response.status != 200:
                    print(f"[ERROR] OpenWeather forecast response status: {forecast_response.status}")
                    return None
                forecast_data = await forecast_response.json()

        result = {
            "current_temperature": current_data["main"]["temp"],
            "current_description": current_data["weather"][0]["description"],
            "wind": current_data["wind"]["speed"],
            "alerts": []
        }

        if forecast_data.get("cod") != "200":
            print(f"Ошибка прогноза: {forecast_data.get('message')}")
            return result

        now = datetime.utcnow()
        next_hours = now + timedelta(hours=9)

        # Два окна
        window_3h = set()
        window_6h = set()

        for entry in forecast_data["list"]:
            forecast_time = datetime.fromtimestamp(entry["dt"])
            if forecast_time > next_hours:
                break

            delta = (forecast_time - now).total_seconds() / 3600
            weather_desc = entry["weather"][0]["main"]
            wind_speed = entry["wind"]["speed"]

            if "rain" in weather_desc.lower():
                if delta <= 3:
                    window_3h.add("дождь")
                elif delta <= 6:
                    window_6h.add("дождь")

            if wind_speed > 8:
                if delta <= 3:
                    window_3h.add("усиление ветра")
                elif delta <= 6:
                    window_6h.add("усиление ветра")

        # Формируем сообщения по временным окнам
        if window_3h:
            result["alerts"].append("В течение ближайших 3 часов: " + ", ".join(sorted(window_3h)) + ".")
        if window_6h:
            result["alerts"].append("В течение 3–6 часов: " + ", ".join(sorted(window_6h)) + ".")

        # Если ни одно окно не дало предупреждений — добавляем нейтральную фразу
        if not result["alerts"]:
            result["alerts"].append("Серьёзных изменений в погоде в ближайшие часы не ожидается.")

        return result

    except Exception as e:
        print(f"Ошибка при запросе к OpenWeather API: {e}")
        return None

def compose_weather_message(weather_data: dict) -> tuple[str, str]:
    """Формирует саммари погоды для ответа"""
    description = weather_data["current_description"]
    temp = weather_data["current_temperature"]
    wind = weather_data["wind"]

    summary = f"Сейчас в твоём регионе — {description}, температура {temp:.1f}°C, \nветер {wind:.1f} м/с."

    alerts_list = weather_data.get("alerts", [])
    alerts = "\n\n⚠️ Прогноз:\n" + "\n".join(f"⚠️ {a}" for a in alerts_list) if alerts_list else ""

    print(f"[DEBUG] Сводка погоды: {summary}")
    print(f"[DEBUG] Предупреждения: {alerts or 'нет предупреждений'}")
    return summary, alerts