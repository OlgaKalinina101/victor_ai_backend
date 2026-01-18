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


"""Зависимости для демонстрационной версии чата"""

from fastapi import Request

def get_logger(request: Request):
    return request.app.state.logger

def get_db(request: Request):
    return request.app.state.db

def get_context_store(request: Request):
    return request.app.state.context_store
