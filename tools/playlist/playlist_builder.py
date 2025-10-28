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
    get_single_track_by_artist, get_track_id_by_artist_and_title

logger = setup_logger("playlist_tool")

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
    def __init__(self, account_id: str, extra_context: str = None,
                 prompt_path: str = "tools/playlist/playlist_prompt.yaml"):
        """
        Инициализирует построитель контекста для плейлиста.

        :param account_id: ID пользователя.
        :param extra_context: Дополнительный контекст (опционально).
        :param prompt_path: Путь к файлу с шаблоном промпта.
        """
        self.account_id = account_id
        self.extra_context = extra_context
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
        db = Database()
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

    async def _stage_one(self) -> dict:
        """
        Стадия 1: Определение тегов (energy, mood).

        :return: dict с ключами "energy" и "mood" или дефолт при ошибке.
        """
        try:
            gender, relationship_level, memories, last_pairs = self._build_playlist_context()
            self.playlist_prompt_core = self._get_playlist_prompt(self.prompt_template, "playlist_prompt_core").format(
                gender=gender,
                relationship_level=relationship_level,
                memories=memories,
                last_pairs=last_pairs,
            )

            if self.extra_context:
                self.time_context = self._get_playlist_prompt(self.prompt_template,
                                                              "playlist_prompt_alarm_context").format(
                    accusative_pronoun=self.accusative_pronoun,
                )
            else:
                self.time_context = self._get_playlist_prompt(self.prompt_template,
                                                              "playlist_prompt_base_context").format(
                    accusative_pronoun=self.accusative_pronoun,
                )

            prompt_stage_one = self._get_playlist_prompt(self.prompt_template, "stage_one").format(
                time_context=self.time_context,
                energy_descriptions=energy_descriptions,
                temperature_descriptions=temperature_descriptions,
            )

            tags_data = await self.llm_client.get_response(
                system_prompt=self.playlist_prompt_core,
                context_prompt=prompt_stage_one,
                message_history=None,
                new_message=None,
                temperature=0.8
            )

            raw_data = parse_llm_json(tags_data)
            logger.info(f"Stage 1 завершена: {tags_data}")

            return raw_data

        except Exception as e:
            logger.error(f"🚨 ALARM stage_one: {e}")
            return DEFAULT_TAGS.copy()

    async def _stage_two(self, tags_data: dict, db_session) -> Tuple[dict, bool]:
        """
        Стадия 2: Выбор исполнителя на основе тегов.

        :param tags_data: Словарь с ключами "energy" и "mood".
        :param db_session: Сессия БД.
        :return: Кортеж (artist_data, is_single) или дефолт при ошибке.
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
                return {"artist": artist}, True

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

            artist_data = await self.llm_client.get_response(
                system_prompt=self.playlist_prompt_core,
                context_prompt=prompt_stage_two,
                message_history=None,
                new_message=None,
                temperature=0.8
            )
            raw_data = parse_llm_json(artist_data)
            logger.info(f"Stage 2 завершена: {artist_data}")

            return raw_data, False

        except Exception as e:
            logger.error(f"🚨 ALARM stage_two: {e}")
            return DEFAULT_ARTIST.copy(), False

    async def _stage_three(self, artist_data: dict, is_single: bool, tags_data: dict, db_session) -> dict:
        """
        Стадия 3: Выбор трека на основе исполнителя.

        :param artist_data: Словарь с ключом "artist".
        :param is_single: Флаг единственного исполнителя.
        :param tags_data: Словарь с ключами "energy" и "mood".
        :param db_session: Сессия БД.
        :return: Словарь с ключом "track" или дефолт при ошибке.
        """
        try:
            # Если один исполнитель и у него один трек
            if is_single:
                track = get_single_track_by_artist(db_session, artist_data["artist"])
                if track:
                    logger.info(f"Stage 3 завершена (единственный трек): {track}")
                    return {"track": track}

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

            track_data = await self.llm_client.get_response(
                system_prompt=self.playlist_prompt_core,
                context_prompt=prompt_stage_three,
                message_history=None,
                new_message=None,
                temperature=0.8
            )
            raw_data = parse_llm_json(track_data)
            logger.info(f"Stage 3 завершена: {track_data}")

            return raw_data

        except Exception as e:
            logger.error(f"🚨 ALARM stage_three: {e}")
            return DEFAULT_TRACK.copy()

    async def build(self) -> tuple[dict[str, None], str] | tuple[dict, str]:
        """
        Точка входа: управляет потоком выполнения стадий.

        :return: Словарь с финальным треком или дефолт при критической ошибке.
        """
        db = Database()
        db_session = db.get_session()
        prompt_stage_four=""
        try:
            tags_data = await self._stage_one()
            artist_data, is_single = await self._stage_two(tags_data, db_session)
            track_data = await self._stage_three(artist_data, is_single, tags_data, db_session)

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
                else:
                    logger.warning(
                        f"🚨 track_id не найден для: "
                        f"artist='{artist_data['artist']}', "
                        f"title='{track_data['track']}'"
                    )
                    track_data["track_id"] = None
            else:
                track_data["track_id"] = None

            prompt_stage_four = self._get_playlist_prompt(self.prompt_template, "stage_four").format(
                track_metadata=f"{artist_data['artist']} — {track_data['track']}",
                time_context=self.time_context,
            )
            logger.info(f"Build завершён успешно: {track_data}")
            return track_data, prompt_stage_four

        except Exception as e:
            logger.error(f"🚨 ALARM: build() критическая ошибка: {e}")
            return {**DEFAULT_TRACK, "track_id": None}, prompt_stage_four

        finally:
            db_session.close()


if __name__ == "__main__":
    builder = PlaylistContextBuilder(account_id="test_user")
    track_data, prompt = asyncio.run(builder.build())
    print(track_data)
    print(prompt)

