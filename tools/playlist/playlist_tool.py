from tools.playlist.playlist_builder import PlaylistContextBuilder


async def run_playlist_chain(account_id: str, extra_context: str = None) -> tuple[dict, str]:
    """
    Запускает пайплайн выбора трека.

    :return: Кортеж (track_data, context)
    """
    builder = PlaylistContextBuilder(
        account_id=account_id,
        extra_context=extra_context
    )
    track_data, context = await builder.build()
    return track_data, context