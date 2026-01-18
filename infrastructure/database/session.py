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

from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker, Session
from settings import settings
from infrastructure.database.url_utils import normalize_database_url, redact_database_url

class Database:
    """
    Database class with singleton pattern support and proper connection pooling.
    
    Usage:
        # Get singleton instance (recommended)
        db = Database.get_instance()
        
        # Create new instance (for testing only)
        db = Database(db_url="postgresql://...")
    """
    _instance: Optional['Database'] = None
    _instance_lock = False
    
    def __init__(self, db_url: Optional[str] = None):
        raw_url = db_url or settings.DATABASE_URL
        try:
            self.db_url = normalize_database_url(raw_url)
        except Exception as e:
            raise RuntimeError(
                f"Invalid DATABASE_URL (cannot normalize): {redact_database_url(raw_url)}"
            ) from e

        # Синхронный движок с настройками пула
        self.engine = create_engine(
            self.db_url,
            future=True,
            # Настройки пула соединений
            pool_size=10,              # Базовый размер пула (было 5 по умолчанию)
            max_overflow=20,           # Дополнительные соединения при нагрузке (было 10)
            pool_recycle=3600,         # Пересоздавать соединения каждый час (было -1 = никогда)
            pool_pre_ping=True,        # Проверять соединение перед использованием
            pool_timeout=30,           # Таймаут ожидания свободного соединения
            echo_pool=False,           # Логирование пула (для отладки можно включить)
        )

        # На Windows при неуспешном коннекте libpq может вернуть сообщение не в UTF-8,
        # и psycopg2 падает UnicodeDecodeError вместо нормального OperationalError.
        # Перехватываем и поднимаем понятную ошибку с подсказкой (без утечки пароля).
        @event.listens_for(self.engine, "do_connect")
        def _do_connect(dialect, conn_rec, cargs, cparams):  # type: ignore[no-redef]
            try:
                return dialect.dbapi.connect(*cargs, **cparams)
            except UnicodeDecodeError as e:
                raise RuntimeError(
                    "PostgreSQL connection failed, but psycopg2 couldn't decode the libpq "
                    "error message (non-UTF8 locale/encoding on Windows is a common cause). "
                    f"Check that Postgres is running and DATABASE_URL is correct: "
                    f"{redact_database_url(self.db_url)}"
                ) from e

        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

    def get_session(self) -> Session:
        return self.SessionLocal()
    
    def dispose(self):
        """Dispose of the connection pool. Useful for cleanup."""
        if self.engine:
            self.engine.dispose()
    
    @classmethod
    def get_instance(cls, db_url: Optional[str] = None) -> 'Database':
        """
        Get singleton instance of Database.
        
        Args:
            db_url: Optional database URL (only used on first call)
            
        Returns:
            Singleton Database instance
        """
        if cls._instance is None:
            cls._instance = cls(db_url=db_url)
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """Reset singleton instance. Useful for testing."""
        if cls._instance is not None:
            cls._instance.dispose()
            cls._instance = None


