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