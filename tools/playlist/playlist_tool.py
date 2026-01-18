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

from tools.playlist.playlist_builder import PlaylistContextBuilder


async def run_playlist_chain(
    account_id: str, 
    extra_context: str = None,
    db: "Database" = None
) -> tuple[dict, str]:
    """
    Запускает пайплайн выбора трека.

    :param account_id: ID пользователя.
    :param extra_context: Дополнительный контекст (опционально).
    :param db: Инстанс Database (опционально, для переиспользования).
    :return: Кортеж (track_data, context)
    """
    builder = PlaylistContextBuilder(
        account_id=account_id,
        extra_context=extra_context,
        db=db
    )
    track_data, context = await builder.build()
    return track_data, context