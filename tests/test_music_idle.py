import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock


def make_player():
    guild = SimpleNamespace(id=1, voice_client=None)
    player = SimpleNamespace(guild=guild, current=None, connected=True,
                             disconnect=AsyncMock(), play=AsyncMock())
    guild.voice_client = player
    return player


def test_queue_end_disconnects_after_idle_timeout(memory_db, monkeypatch):
    import config
    from cogs.music import EnhancedMusic
    monkeypatch.setattr(config, 'MUSIC_IDLE_TIMEOUT', 0.01, raising=False)
    async def run():
        cog = EnhancedMusic(SimpleNamespace())
        player = make_player()
        cog.autoplay_enabled[1] = False
        await cog.on_wavelink_track_end(SimpleNamespace(player=player, track=None, reason='finished'))
        await cog._idle_tasks[1]
        player.disconnect.assert_awaited_once_with(force=True)
    asyncio.run(run())


def test_new_play_cancels_idle_departure(memory_db, monkeypatch):
    import config
    from cogs.music import EnhancedMusic
    monkeypatch.setattr(config, 'MUSIC_IDLE_TIMEOUT', 0.01, raising=False)
    async def run():
        cog = EnhancedMusic(SimpleNamespace())
        player = make_player()
        cog._schedule_idle_disconnect(player)
        task = cog._idle_tasks[1]
        await cog._play_track(player, SimpleNamespace(encoded='new'), manual=True)
        await asyncio.gather(task, return_exceptions=True)
        player.disconnect.assert_not_awaited()
        player.play.assert_awaited_once()
    asyncio.run(run())


def test_inactive_event_leaves_without_touching_node(memory_db):
    from cogs.music import EnhancedMusic
    async def run():
        cog = EnhancedMusic(SimpleNamespace())
        player = make_player()
        await cog.on_wavelink_inactive_player(player)
        player.disconnect.assert_awaited_once_with(force=True)
    asyncio.run(run())


def test_backend_finished_track_clears_stale_current():
    from utils.music_player import VoicePlayer
    async def run():
        player = object.__new__(VoicePlayer)
        player._guild = SimpleNamespace(id=1)
        player._current = SimpleNamespace(title='Old')
        player._paused = True
        player._node = SimpleNamespace(fetch_player_info=AsyncMock(return_value=SimpleNamespace(
            track=None, paused=False, state=SimpleNamespace(connected=True))))
        assert await player.refresh_playback_state() is True
        assert player.current is None
        assert player.paused is False
    asyncio.run(run())


def test_disconnected_backend_player_is_rebuilt(memory_db, monkeypatch):
    import cogs.music as music
    from utils.music_player import VoicePlayer
    async def run():
        cog = music.EnhancedMusic(SimpleNamespace())
        cog.connect_to_lavalink = AsyncMock(return_value=True)
        guild = SimpleNamespace(id=1, voice_client=None)
        channel = SimpleNamespace(name='General', connect=AsyncMock(return_value=SimpleNamespace()))
        old = object.__new__(VoicePlayer)
        old._guild = guild;old.channel = channel;old._connected = True
        old._node = SimpleNamespace(fetch_player_info=AsyncMock(return_value=None))
        guild.voice_client = old
        async def disconnect(**kwargs):guild.voice_client = None
        old.disconnect = AsyncMock(side_effect=disconnect)
        monkeypatch.setattr(music.wavelink.Pool, '_Pool__nodes', {})
        result = await cog._connect_voice(guild, channel, None)
        assert result is channel.connect.return_value
        old.disconnect.assert_awaited_once_with(force=True)
    asyncio.run(run())


def test_autoplay_defaults_off_but_preserves_saved_guild_choices(memory_db):
    import json
    from pathlib import Path
    from cogs.music import EnhancedMusic
    Path('data').mkdir(exist_ok=True)
    Path('data/autoplay_config.json').write_text(json.dumps({'autoplay_enabled': {'1': True, '2': False}}))
    cog = EnhancedMusic(SimpleNamespace())
    assert cog.get_autoplay_status(1) is True
    assert cog.get_autoplay_status(2) is False
    assert cog.get_autoplay_status(3) is False


def test_http_track_can_finish_after_backend_updates_encoding(memory_db, monkeypatch):
    import config
    from cogs.music import EnhancedMusic
    monkeypatch.setattr(config, 'MUSIC_IDLE_TIMEOUT', 0.01)
    async def run():
        cog = EnhancedMusic(SimpleNamespace())
        player = make_player()
        requested = SimpleNamespace(source='http', identifier='same-audio-url', encoded='before-probing')
        await cog._play_track(player, requested, manual=True)
        finished = SimpleNamespace(source='http', identifier='same-audio-url', encoded='after-probing', extras=requested.extras)
        await cog.on_wavelink_track_end(SimpleNamespace(player=player, track=finished, reason='finished'))
        await cog._idle_tasks[1]
        player.disconnect.assert_awaited_once_with(force=True)
    asyncio.run(run())
