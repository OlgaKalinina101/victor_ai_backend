import os

from pydantic.v1 import ConfigDict
from pydantic_settings import BaseSettings
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # Загружаем .env, если он есть

# Используем переменную окружения или текущую рабочую директорию
BASE_DIR = Path(os.getenv("VICTOR_CORE_ROOT", os.getcwd())).resolve()

class Settings(BaseSettings):
    BASE_DIR: Path = BASE_DIR
    # Пути к базам данных
    SESSION_CONTEXT_DIR: Path = BASE_DIR / os.getenv("SESSION_CONTEXT_DIR", "infrastructure/context_store/sessions")
    VECTOR_STORE_DIR: Path = BASE_DIR / os.getenv("VECTOR_STORE_DIR", "infrastructure/vector_store")

    DATABASE_URL: str = "postgresql+psycopg2://postgres:up2wAzqr2@localhost:5432/victor_db"

    # Название коллекции Chroma
    CHROMA_COLLECTION_NAME: str = os.getenv("CHROMA_COLLECTION_NAME")

    # Название модели эмбеддингов
    EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME")

    #OpenAI API_KEY
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    XAI_API_KEY: str = os.getenv("XAI_API_KEY")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY")

    elevenlabs_api_key: str = os.getenv("ELEVENLABS_API_KEY")
    elevenlabs_voice_id: str = os.getenv("ELEVENLABS_VOICE_ID")
    OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY")
    GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY")
    YANDEX_MAPS_API_KEY: str = os.getenv("YANDEX_MAPS_API_KEY")

    PUSHY_SECRET_KEY: str = os.getenv("PUSHY_SECRET_KEY")
    creator_account_id: str = os.getenv("CREATOR_ACCOUNT_ID")
    timezone: str = os.getenv("TIMEZONE")

    #Пути к промптам
    SYSTEM_PROMPT_PATH: Path = (BASE_DIR / "core/persona/prompts/system.yaml").resolve()
    CONTEXT_PROMPT_PATH: Path = (BASE_DIR / "core/dialog/templates/context.yaml").resolve()
    VICTOR_CORE_ROOT: Path = os.getenv("VICTOR_CORE_ROOT")
    MODEL_SETTINGS: Path = os.getenv("MODEL_SETTINGS")

    model_config = ConfigDict(env_file=".env")


settings = Settings()