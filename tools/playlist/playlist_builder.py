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

import asyncio
from dataclasses import field
from datetime import datetime
from pathlib import Path
from typing import Tuple, Dict, Any, Coroutine

import yaml

from core.analysis.preanalysis.preanalysis_helpers import parse_llm_json
from infrastructure.context_store.session_context_store import SessionContextStore
from infrastructure.database.database_enums import EnergyDescription, TemperatureDescription
from infrastructure.database.session import Database
from infrastructure.llm.client import LLMClient
from infrastructure.logging.logger import setup_logger
from infrastructure.vector_store.helpers import MemoryProcessor
from models.user_enums import Gender
from settings import settings
from tools.playlist.helpers import get_artists_by_description, get_tracks_by_artist, is_single_artist_by_description, \
    get_single_track_by_artist, get_track_id_by_artist_and_title, get_track_atmosphere_by_id
from tools.playlist.repository import PlaylistRepository

logger = setup_logger("playlist_tool")


def parse_llm_response_with_reasoning(response: str) -> Tuple[dict, str]:
    """
    Парсит ответ LLM который содержит JSON + reasoning.
    
    Ожидаемый формат:
    {"key": "value"}
    Reasoning text here...
    
    :param response: Ответ от LLM
    :return: Кортеж (parsed_json, reasoning_text)
    """
    try:
        # Ищем JSON в первой части
        lines = response.strip().split('\n')
        json_part = ""
        reasoning_lines = []
        json_found = False
        
        for line in lines:
            line_stripped = line.strip()
            if not json_found and (line_stripped.startswith('{') or json_part):
                json_part += line_stripped
                if line_stripped.endswith('}'):
                    json_found = True
            elif json_found and line_stripped:
                reasoning_lines.append(line_stripped)
        
        # Парсим JSON
        parsed_data = parse_llm_json(json_part) if json_part else {}
        
        # Собираем reasoning
        reasoning = ' '.join(reasoning_lines).strip()
        
        return parsed_data, reasoning
        
    except Exception as e:
        logger.error(f"Ошибка парсинга ответа с reasoning: {e}")
        # Фолбэк - пытаемся парсить как обычный JSON
        try:
            parsed_data = parse_llm_json(response)
            return parsed_data, ""
        except:
            return {}, ""

# Вместо простых списков - передавай описания
energy_descriptions = """
- Светлая-ритмичная: лёгкость движения, игривость, воздушность, танцевальная текучесть
- Тёплая-сердечная: эмоциональная глубина, искренность, задушевность, человеческое тепло  
- Тихая-заземляющая: умиротворение, стабильность, медитативность, почва под ногами
- Отражающее-наблюдение: созерцательность, самоанализ, зеркало души, глубокая рефлексия
- Сложно-рефлексивные: многослойность, интеллектуальная глубина, экзистенциальные поиски
"""

temperature_descriptions = """
- Тёплая: обволакивающее тепло, близость, доверие, мягкое принятие
- Умеренная: уравновешенность, гармония, стабильность, комфортная нейтральность
- Горячая: страсть, интенсивность, живость, эмоциональный подъём  
- Холодная: отстранённость, ясность, интеллектуальность, чистота чувств
- Ледяная: отрешённость, глубокая меланхолия, хрупкость, замороженные эмоции
"""

# Дефолты для безопасного фолбэка
DEFAULT_TAGS = {"energy": "Тёплая-сердечная", "mood": "Тёплая"}
DEFAULT_ARTIST = {"artist": "Michael Buble"}
DEFAULT_TRACK = {"track": None}


class PlaylistContextBuilder:
    def __init__(
        self, 
        account_id: str, 
        extra_context: str = None,
        db: "Database" = None,
        prompt_path: str = "tools/playlist/playlist_prompt.yaml"
    ):
        """
        Инициализирует построитель контекста для плейлиста.

        :param account_id: ID пользователя.
        :param extra_context: Дополнительный контекст (опционально).
        :param db: Инстанс Database (опционально, для переиспользования).
        :param prompt_path: Путь к файлу с шаблоном промпта.
        """
        self.account_id = account_id
        self.extra_context = extra_context
        self.db = db or Database.get_instance()
        self.time_context = None
        self.prompt_path = prompt_path
        self.accusative_pronoun = None
        self.playlist_prompt_core = None
        self.prompt_template = self._load_prompt_template()
        self.memory_processor = MemoryProcessor()
        self.llm_client = LLMClient(account_id=self.account_id, mode="foundation")

    def _load_prompt_template(self) -> dict:
        """
        Загружает шаблон промпта из YAML-файла.

        :return: Словарь с шаблоном промпта или пустой словарь при ошибке.
        """
        try:
            with open(str(Path(settings.BASE_DIR / self.prompt_path)), "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data or {}
        except Exception as e:
            logger.error(f"Ошибка загрузки {self.prompt_path}: {e}")
            return {}

    def _build_playlist_context(self) -> Tuple[str, str, str, str]:
        """
        Формирует отформатированный контекст для плейлиста.

        :return: Кортеж (gender, relationship_level, memories, last_pairs).
        """
        db = Database.get_instance()
        db_session = db.get_session()
        try:
            session_context = SessionContextStore(str(Path(settings.BASE_DIR / settings.SESSION_CONTEXT_DIR)))
            raw_data = session_context.load(self.account_id, db_session)
            last_pairs_raw = raw_data.get_last_n_pairs(n=2)
            dative_pronoun = "ней" if raw_data.gender == Gender.FEMALE else "нем"
            self.accusative_pronoun = "нее" if raw_data.gender == Gender.FEMALE else "него"
            gender = raw_data.gender.value
            relationship_level = raw_data.relationship_level.value
        finally:
            db_session.close()

        memories_raw = self.memory_processor.get_memory(self.account_id)
        memories = f"=== Твои воспоминания о {dative_pronoun} ===\n\n"
        if memories_raw.startswith("Нет доступных воспоминаний"):
            memories += f"{memories_raw}\n"
        else:
            memory_lines = memories_raw.split("\n")
            for i, line in enumerate(memory_lines, 1):
                if line.strip():
                    memories += f"{i}. {line.strip()}\n"
        memories += "\n"

        last_pairs = "=== Ваш последний диалог ===\n\n"
        if not last_pairs_raw:
            last_pairs += "Нет доступных сообщений.\n"
        else:
            for pair in last_pairs_raw:
                parts = pair.split("/n")
                for part in parts:
                    if part.startswith("user:"):
                        last_pairs += f"**Пользователь** ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}):\n"
                        last_pairs += f"  {part[5:].strip()}\n"
                    elif part.startswith("assistant:"):
                        last_pairs += f"**Ассистент** ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}):\n"
                        last_pairs += f"  {part[10:].strip()}\n"
                last_pairs += "\n"

        return gender, relationship_level, memories, last_pairs

    def _get_playlist_prompt(self, prompt_template: dict, stage_prompt_name: str) -> str:
        try:
            prompt = prompt_template.get(stage_prompt_name, "")
            if not prompt:
                logger.error(f"Ключ '{stage_prompt_name}' не найден в prompt_template")
                return ""
            return prompt
        except Exception as e:
            logger.error(f"Ошибка при получении prompt_template[{stage_prompt_name}]: {e}")
            return ""

    async def _stage_one(self) -> Tuple[dict, str]:
        """
        Стадия 1: Определение тегов (energy, mood) + reasoning.

        :return: Кортеж (dict с ключами "energy" и "mood", reasoning text) или дефолт при ошибке.
        """
        try:
            gender, relationship_level, memories, last_pairs = self._build_playlist_context()
            self.playlist_prompt_core = self._get_playlist_prompt(self.prompt_template, "playlist_prompt_core").format(
                gender=gender,
                relationship_level=relationship_level,
                memories=memories,
                last_pairs=last_pairs,
            )

            self.time_context = self._get_playlist_prompt(self.prompt_template,
                                                          "playlist_prompt_base_context").format(
                accusative_pronoun=self.accusative_pronoun,
            )

            prompt_stage_one = self._get_playlist_prompt(self.prompt_template, "stage_one").format(
                time_context=self.time_context,
                energy_descriptions=energy_descriptions,
                temperature_descriptions=temperature_descriptions,
            )

            response = await self.llm_client.get_response(
                system_prompt=self.playlist_prompt_core,
                context_prompt=prompt_stage_one,
                message_history=None,
                new_message=None,
                temperature=0.8
            )

            raw_data, reasoning = parse_llm_response_with_reasoning(response)
            logger.info(f"Stage 1 завершена: {response}")

            return raw_data, reasoning

        except Exception as e:
            logger.error(f"🚨 ALARM stage_one: {e}")
            return DEFAULT_TAGS.copy(), ""

    async def _stage_two(self, tags_data: dict, db_session) -> Tuple[dict, bool, str]:
        """
        Стадия 2: Выбор исполнителя на основе тегов + reasoning.

        :param tags_data: Словарь с ключами "energy" и "mood".
        :param db_session: Сессия БД.
        :return: Кортеж (artist_data, is_single, reasoning) или дефолт при ошибке.
        """
        try:
            energy_db = EnergyDescription.from_value(tags_data["energy"])
            temp_db = TemperatureDescription.from_value(tags_data["temperature"])

            # Проверяем, есть ли ровно один исполнитель
            is_single, artist = is_single_artist_by_description(
                db_session,
                account_id=self.account_id,
                energy_description=energy_db,
                temperature_description=temp_db
            )

            logger.info(f"Ровно один исполнитель: {is_single}, Исполнитель: {artist}")

            if is_single:
                return {"artist": artist}, True, f"нашла идеального исполнителя - {artist} ✨"

            # Если несколько исполнителей, получаем их список
            artists_with_genres = get_artists_by_description(
                db_session,
                account_id=self.account_id,
                energy_description=energy_db,
                temperature_description=temp_db
            )

            logger.info(f"Получены исполнители: {artists_with_genres}")

            prompt_stage_two = self._get_playlist_prompt(self.prompt_template, "stage_two").format(
                time_context=self.time_context,
                artists_with_genres=artists_with_genres,
            )

            response = await self.llm_client.get_response(
                system_prompt=self.playlist_prompt_core,
                context_prompt=prompt_stage_two,
                message_history=None,
                new_message=None,
                temperature=0.8
            )
            raw_data, reasoning = parse_llm_response_with_reasoning(response)
            logger.info(f"Stage 2 завершена: {response}")

            return raw_data, False, reasoning

        except Exception as e:
            logger.error(f"🚨 ALARM stage_two: {e}")
            return DEFAULT_ARTIST.copy(), False, ""

    async def _stage_three(self, artist_data: dict, is_single: bool, tags_data: dict, db_session) -> Tuple[dict, str]:
        """
        Стадия 3: Выбор трека на основе исполнителя + reasoning.

        :param artist_data: Словарь с ключом "artist".
        :param is_single: Флаг единственного исполнителя.
        :param tags_data: Словарь с ключами "energy" и "mood".
        :param db_session: Сессия БД.
        :return: Кортеж (track_data, reasoning) или дефолт при ошибке.
        """
        try:
            # Если один исполнитель и у него один трек
            if is_single:
                track = get_single_track_by_artist(db_session, artist_data["artist"])
                if track:
                    logger.info(f"Stage 3 завершена (единственный трек): {track}")
                    return {"track": track}, f"выбрала {track} 💫"

            # Если треков несколько
            energy_db = EnergyDescription.from_value(tags_data["energy"])
            temp_db = TemperatureDescription.from_value(tags_data["temperature"])

            track_list_with_duration = get_tracks_by_artist(
                session=db_session,
                artist=artist_data["artist"],
                account_id=self.account_id,
                energy_description=energy_db,
                temperature_description=temp_db
            )

            prompt_stage_three = self._get_playlist_prompt(self.prompt_template, "stage_three").format(
                time_context=self.time_context,
                track_list_with_duration=track_list_with_duration,
            )

            response = await self.llm_client.get_response(
                system_prompt=self.playlist_prompt_core,
                context_prompt=prompt_stage_three,
                message_history=None,
                new_message=None,
                temperature=0.8
            )
            raw_data, reasoning = parse_llm_response_with_reasoning(response)
            logger.info(f"Stage 3 завершена: {response}")

            return raw_data, reasoning

        except Exception as e:
            logger.error(f"🚨 ALARM stage_three: {e}")
            return DEFAULT_TRACK.copy(), ""

    async def build(self) -> tuple[dict[str, None], str] | tuple[dict, str]:
        """
        Точка входа: управляет потоком выполнения стадий (без streaming).

        :return: Кортеж (track_data, prompt_stage_four).
        """
        db_session = self.db.get_session()
        prompt_stage_four=""
        try:
            tags_data, _ = await self._stage_one()
            artist_data, is_single, _ = await self._stage_two(tags_data, db_session)
            track_data, _ = await self._stage_three(artist_data, is_single, tags_data, db_session)

            # Получаем track_id из БД
            if track_data.get("track"):
                track_id = get_track_id_by_artist_and_title(
                    session=db_session,
                    account_id=self.account_id,
                    artist=artist_data["artist"],
                    title=track_data["track"]
                )

                if track_id:
                    track_data["track_id"] = track_id
                    logger.info(f"Найден track_id: {track_id}")
                    raw_data = get_track_atmosphere_by_id(db_session, self.account_id, track_id)

                    track_metadata = f"""
                    Песня: {raw_data['title']}
                    Исполнитель: {raw_data['artist']}
                    Жанр: {raw_data['genre']} 
                    Температура: {raw_data['temperature']}
                    Энергия: {raw_data['energy']}
                    Возьми отсюда то, что откликается тебе. 
                    """
                    prompt_stage_four = self._get_playlist_prompt(self.prompt_template, "stage_four").format(
                        track_metadata=track_metadata,
                        time_context=self.time_context,
                    )
                else:
                    logger.warning(
                        f"🚨 track_id не найден для: "
                        f"artist='{artist_data['artist']}', "
                        f"title='{track_data['track']}'"
                    )
                    track_data["track_id"] = None
                    prompt_stage_four=""
            else:
                track_data["track_id"] = None
                prompt_stage_four=""


            logger.info(f"Build завершён успешно: {track_data}")
            return track_data, prompt_stage_four

        except Exception as e:
            logger.error(f"🚨 ALARM: build() критическая ошибка: {e}")
            return {**DEFAULT_TRACK, "track_id": None}, prompt_stage_four

        finally:
            db_session.close()
    
    async def build_with_logs(self):
        """
        Точка входа для streaming: управляет потоком выполнения стадий с логами.
        
        :yield: Словари с логами, track_data и context для streaming на фронт.
        """
        logger.info(f"[build_with_logs] 🎵 Начало для account_id={self.account_id}")
        db_session = self.db.get_session()
        prompt_stage_four = ""
        repository = PlaylistRepository(db_session)
        
        # Переменные для сохранения reasoning из каждого stage
        stage1_reasoning = ""
        stage2_reasoning = ""
        stage3_reasoning = ""
        final_track_id = None
        
        try:
            # === Stage 1: Выбор энергии и температуры ===
            logger.info("[build_with_logs] 📝 Stage 1: отправляем начальный лог")
            yield {"log": "🎵 анализирую твоё настроение..."}
            await asyncio.sleep(0.1)  # Даём время на flush
            
            logger.info("[build_with_logs] 🔄 Stage 1: вызываем _stage_one()")
            tags_data, stage1_reasoning = await self._stage_one()
            logger.info(f"[build_with_logs] ✅ Stage 1: получили tags={tags_data}, reasoning='{stage1_reasoning[:50] if stage1_reasoning else 'пусто'}...'")
            
            if stage1_reasoning:
                logger.info(f"[build_with_logs] 📝 Stage 1: отправляем reasoning")
                yield {"log": stage1_reasoning}
                await asyncio.sleep(0.1)  # Даём время на flush
            
            # === Stage 2: Выбор исполнителя ===
            logger.info("[build_with_logs] 📝 Stage 2: отправляем начальный лог")
            yield {"log": "🎤 выбираю исполнителя..."}
            await asyncio.sleep(0.1)  # Даём время на flush
            
            logger.info("[build_with_logs] 🔄 Stage 2: вызываем _stage_two()")
            artist_data, is_single, stage2_reasoning = await self._stage_two(tags_data, db_session)
            logger.info(f"[build_with_logs] ✅ Stage 2: получили artist={artist_data}, reasoning='{stage2_reasoning[:50] if stage2_reasoning else 'пусто'}...'")
            
            if stage2_reasoning:
                logger.info(f"[build_with_logs] 📝 Stage 2: отправляем reasoning")
                yield {"log": stage2_reasoning}
                await asyncio.sleep(0.1)  # Даём время на flush
            
            # === Stage 3: Выбор трека ===
            logger.info("[build_with_logs] 📝 Stage 3: отправляем начальный лог")
            yield {"log": "🎼 ищу идеальный трек..."}
            await asyncio.sleep(0.1)  # Даём время на flush
            
            logger.info("[build_with_logs] 🔄 Stage 3: вызываем _stage_three()")
            track_data, stage3_reasoning = await self._stage_three(artist_data, is_single, tags_data, db_session)
            logger.info(f"[build_with_logs] ✅ Stage 3: получили track={track_data}, reasoning='{stage3_reasoning[:50] if stage3_reasoning else 'пусто'}...'")
            
            if stage3_reasoning:
                logger.info(f"[build_with_logs] 📝 Stage 3: отправляем reasoning")
                yield {"log": stage3_reasoning}
                await asyncio.sleep(0.1)  # Даём время на flush
            
            # === Получаем track_id и формируем Stage 4 ===
            logger.info("[build_with_logs] 🔍 Получаем track_id из БД")
            if track_data.get("track"):
                track_id = get_track_id_by_artist_and_title(
                    session=db_session,
                    account_id=self.account_id,
                    artist=artist_data["artist"],
                    title=track_data["track"]
                )
                
                if track_id:
                    track_data["track_id"] = track_id
                    final_track_id = track_id
                    logger.info(f"[build_with_logs] ✅ Найден track_id: {track_id}")
                    raw_data = get_track_atmosphere_by_id(db_session, self.account_id, track_id)
                    
                    track_metadata = f"""
                    Песня: {raw_data['title']}
                    Исполнитель: {raw_data['artist']}
                    Жанр: {raw_data['genre']} 
                    Температура: {raw_data['temperature']}
                    Энергия: {raw_data['energy']}
                    Возьми отсюда то, что откликается тебе. 
                    """
                    prompt_stage_four = self._get_playlist_prompt(self.prompt_template, "stage_four").format(
                        track_metadata=track_metadata,
                        time_context=self.time_context,
                    )
                    logger.info("[build_with_logs] ✅ Stage 4 context сформирован")
                else:
                    logger.warning(
                        f"[build_with_logs] 🚨 track_id не найден для: "
                        f"artist='{artist_data['artist']}', "
                        f"title='{track_data['track']}'"
                    )
                    track_data["track_id"] = None
            else:
                track_data["track_id"] = None
                logger.warning("[build_with_logs] ⚠️ track_data не содержит 'track'")
            
            # === Сохраняем момент выбора плейлиста в БД ===
            try:
                moment = repository.create_playlist_moment(
                    account_id=self.account_id,
                    stage1_text=stage1_reasoning,
                    stage2_text=stage2_reasoning,
                    stage3_text=stage3_reasoning,
                    track_id=final_track_id
                )
                logger.info(f"[build_with_logs] 💾 Сохранён playlist moment: id={moment.id}")
            except Exception as e:
                logger.error(f"[build_with_logs] ❌ Ошибка сохранения момента: {e}", exc_info=True)
            
            # === Возвращаем финальные данные ===
            logger.info(f"[build_with_logs] 📦 Отправляем финальный track: {track_data}")
            yield {"track": track_data}
            await asyncio.sleep(0.1)  # Даём время на flush
            
            logger.info(f"[build_with_logs] 📦 Отправляем context (длина={len(prompt_stage_four)})")
            yield {"context": prompt_stage_four}
            await asyncio.sleep(0.1)  # Даём время на flush
            
            logger.info(f"[build_with_logs] 🎉 Build with logs завершён успешно")
            
        except Exception as e:
            logger.error(f"[build_with_logs] ❌ Критическая ошибка: {e}", exc_info=True)
            yield {"error": str(e)}
            
        finally:
            logger.info("[build_with_logs] 🔒 Закрываем db_session")
            db_session.close()


if __name__ == "__main__":
    # Example usage - требует явный account_id
    import sys
    account_id = sys.argv[1] if len(sys.argv) > 1 else "test_user"
    builder = PlaylistContextBuilder(account_id=account_id)
    db = Database()
    session = db.get_session()

    track_data, prompt = asyncio.run(builder.build())
    print(track_data)
    print(prompt)

