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

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

BASE_DIR = Path(os.getenv("VICTOR_CORE_ROOT", os.getcwd())).resolve()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    BASE_DIR: Path = BASE_DIR

    DEMO_KEYS_DIR: Path = BASE_DIR / os.getenv("DEMO_KEYS_DIR", "infrastructure/database/demo_keys.json")
    SESSION_CONTEXT_DIR: Path = BASE_DIR / os.getenv("SESSION_CONTEXT_DIR", "infrastructure/context_store/sessions")
    VECTOR_STORE_DIR: Path = BASE_DIR / os.getenv("VECTOR_STORE_DIR", "infrastructure/vector_store")

    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/victor_db")

    # лучше Optional, потому что getenv может вернуть None
    CHROMA_COLLECTION_NAME: Optional[str] = None
    EMBEDDING_MODEL_NAME: Optional[str] = None

    OPENAI_API_KEY: Optional[str] = None
    XAI_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    HUGGING_FACE_API_KEY: Optional[str] = None

    OPENWEATHER_API_KEY: Optional[str] = None
    GOOGLE_MAPS_API_KEY: Optional[str] = None

    PUSHY_SECRET_KEY: Optional[str] = None
    creator_account_id: Optional[str] = None
    timezone: Optional[str] = None

    SYSTEM_PROMPT_PATH: Path = (BASE_DIR / "core/persona/prompts/system.yaml").resolve()
    CONTEXT_PROMPT_PATH: Path = (BASE_DIR / "core/dialog/templates/context.yaml").resolve()

    VICTOR_CORE_ROOT: Optional[str] = None
    MODEL_SETTINGS: Optional[str] = None

settings = Settings()
