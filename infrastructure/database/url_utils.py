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

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import parse_qsl, unquote, urlsplit

from sqlalchemy.engine import URL, make_url


@dataclass(frozen=True)
class _ParsedNetloc:
    username_raw: Optional[str]
    password_raw: Optional[str]
    host: Optional[str]
    port: Optional[int]


def _parse_netloc_raw(netloc: str) -> _ParsedNetloc:
    """
    Парсит netloc вручную, не триггеря встроенные .username/.password у urlsplit,
    потому что они могут пытаться percent-decode и падать на кривых последовательностях.
    """
    if not netloc:
        return _ParsedNetloc(None, None, None, None)

    userinfo: Optional[str] = None
    hostport = netloc

    if "@" in netloc:
        userinfo, hostport = netloc.rsplit("@", 1)

    username_raw: Optional[str] = None
    password_raw: Optional[str] = None

    if userinfo is not None and userinfo != "":
        if ":" in userinfo:
            username_raw, password_raw = userinfo.split(":", 1)
        else:
            username_raw = userinfo

    host: Optional[str]
    port: Optional[int] = None

    # IPv6 в квадратных скобках: [::1]:5432
    if hostport.startswith("[") and "]" in hostport:
        end = hostport.find("]")
        host = hostport[1:end]
        rest = hostport[end + 1 :]
        if rest.startswith(":") and rest[1:].isdigit():
            port = int(rest[1:])
    else:
        # host:port
        if ":" in hostport:
            h, p = hostport.rsplit(":", 1)
            host = h or None
            if p.isdigit():
                port = int(p)
        else:
            host = hostport or None

    return _ParsedNetloc(username_raw, password_raw, host, port)


def _unquote_strict(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    # strict важен: мы хотим поймать битые последовательности и обработать их сами
    return unquote(value, encoding="utf-8", errors="strict")


def _unquote_lenient(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return unquote(value, encoding="utf-8", errors="replace")

def _escape_percent_literal(value: Optional[str]) -> Optional[str]:
    """
    Если значение содержит битые percent-escape (например, '%C2'), трактуем '%' как ЛИТЕРАЛ.
    Самый безопасный способ — экранировать '%' -> '%25', чтобы downstream (SQLAlchemy/psycopg2)
    не пытались интерпретировать это как bytes UTF-8.
    """
    if value is None:
        return None
    return value.replace("%", "%25")


def normalize_database_url(db_url: Any) -> str:
    """
    Делает DATABASE_URL устойчивым к битому percent-encoding в user/pass.

    Частый кейс: пароль содержит подстроки вида '%C2' (неполная UTF-8 последовательность),
    из-за чего `psycopg2.connect()` падает с UnicodeDecodeError.

    Тактика:
    - парсим URL безопасно;
    - пробуем strict percent-decode для username/password;
    - если strict падает — трактуем исходную подстроку как ЛИТЕРАЛ и даём SQLAlchemy
      корректно её экранировать (например, '%' -> '%25').
    """
    if db_url is None:
        raise ValueError("DATABASE_URL is None")

    if isinstance(db_url, (bytes, bytearray, memoryview)):
        # На всякий случай: если кто-то передал bytes, пробуем безопасно декодировать.
        # UTF-8 first; fallback на cp1251 (часто на Windows).
        try:
            db_url = bytes(db_url).decode("utf-8")
        except UnicodeDecodeError:
            db_url = bytes(db_url).decode("cp1251")

    if not isinstance(db_url, str):
        raise TypeError(f"DATABASE_URL must be str, got {type(db_url)!r}")

    db_url = db_url.strip()
    if not db_url:
        raise ValueError("DATABASE_URL is empty")

    parts = urlsplit(db_url)
    if not parts.scheme.startswith("postgresql"):
        return db_url

    netloc = _parse_netloc_raw(parts.netloc)

    # База данных (часть пути без ведущего /)
    database = parts.path[1:] if parts.path.startswith("/") else parts.path
    database = database or None

    # Query params
    query_items = parse_qsl(parts.query, keep_blank_values=True)
    query: dict[str, str] = {k: v for k, v in query_items}

    # username/password: сначала strict unquote, если падает — считаем значение literal.
    username: Optional[str]
    password: Optional[str]

    try:
        username = _unquote_strict(netloc.username_raw)
    except UnicodeDecodeError:
        username = _escape_percent_literal(netloc.username_raw)

    try:
        password = _unquote_strict(netloc.password_raw)
    except UnicodeDecodeError:
        password = _escape_percent_literal(netloc.password_raw)

    url = URL.create(
        drivername=parts.scheme,
        username=username,
        password=password,
        host=netloc.host,
        port=netloc.port,
        database=database,
        query=query or None,
    )
    # hide_password=False, потому что это значение дальше реально используется для connect.
    return url.render_as_string(hide_password=False)


def redact_database_url(db_url: Any) -> str:
    """
    Возвращает строку подключения без пароля (для логов/ошибок).
    Не должна бросать исключений.
    """
    try:
        normalized = normalize_database_url(db_url)
        # SQLAlchemy уже умеет прятать пароль корректно.
        return make_url(normalized).render_as_string(hide_password=True)
    except Exception:
        # Фолбэк: максимально безопасно, без попытки парсинга.
        s = str(db_url)
        if "://" in s and "@" in s:
            # very rough masking: user:pass@ -> user:***@
            prefix, rest = s.split("://", 1)
            if "@" in rest:
                creds, tail = rest.rsplit("@", 1)
                if ":" in creds:
                    user, _ = creds.split(":", 1)
                    return f"{prefix}://{user}:***@{tail}"
        return s


