import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import wavelink


def test_failed_track_stops_autoplay_and_reports_once(memory_db):
    from cogs.music import EnhancedMusic
    async def run():
        cog = EnhancedMusic(SimpleNamespace())
        player = SimpleNamespace(guild=SimpleNamespace(id=1), current=None,
                                 last_channel=SimpleNamespace(send=AsyncMock()), autoplay=wavelink.AutoPlayMode.enabled)
        track = SimpleNamespace(title='Loser', identifier='failed')
        cog.autoplay_enabled[1] = True
        cog.auto_recommend_and_play = AsyncMock()
        for reason in ('loadFailed', 'loadfailed'):
            await cog.on_wavelink_track_end(SimpleNamespace(player=player, track=track, reason=reason))
        assert cog.auto_recommend_and_play.await_count == 0
        assert player.last_channel.send.await_count == 1
        assert player.autoplay == wavelink.AutoPlayMode.disabled
        assert 1 in cog._playback_blocked
    asyncio.run(run())


def test_track_exception_and_end_share_one_failure_notice(memory_db):
    from cogs.music import EnhancedMusic
    async def run():
        cog = EnhancedMusic(SimpleNamespace())
        player = SimpleNamespace(guild=SimpleNamespace(id=1), current=None,
                                 last_channel=SimpleNamespace(send=AsyncMock()), autoplay=wavelink.AutoPlayMode.disabled)
        payload = SimpleNamespace(player=player, track=SimpleNamespace(title='Loser'),
                                  exception={'message': 'requires login'}, reason='loadFailed')
        await cog.on_wavelink_track_exception(payload)
        await cog.on_wavelink_track_end(payload)
        assert player.last_channel.send.await_count == 1
    asyncio.run(run())


@pytest.mark.parametrize('server_first', [True, False])
def test_voice_handshake_works_in_either_event_order(server_first):
    from utils.music_player import VoicePlayer
    async def run():
        player = object.__new__(VoicePlayer)
        player._voice_state = {'voice': {}}
        player._guild = SimpleNamespace(id=1)
        player._node = SimpleNamespace(_update_player=AsyncMock())
        player._connection_event = asyncio.Event()
        player.client = SimpleNamespace(get_channel=lambda channel_id: SimpleNamespace(id=channel_id))
        state = {'channel_id': '2', 'session_id': 'session'}
        server = {'token': 'token', 'endpoint': 'voice.example'}
        if server_first:
            await player.on_voice_server_update(server)
            assert not player._connection_event.is_set()
            await player.on_voice_state_update(state)
        else:
            await player.on_voice_state_update(state)
            assert not player._connection_event.is_set()
            await player.on_voice_server_update(server)
        assert player._connection_event.is_set()
        assert player.node._update_player.await_count == 1
        assert player.node._update_player.call_args.kwargs['data']['voice']['channelId'] == '2'
    asyncio.run(run())


def test_voice_timeout_retries_player_without_closing_node(memory_db, monkeypatch):
    import cogs.music as music
    async def run():
        cog = music.EnhancedMusic(SimpleNamespace())
        cog.connect_to_lavalink = AsyncMock(return_value=True)
        cog.switch_lavalink_server = AsyncMock()
        stale = SimpleNamespace(disconnect=AsyncMock())
        channel = SimpleNamespace(name='General', connect=AsyncMock())
        player = SimpleNamespace()
        guild = SimpleNamespace(id=1, voice_client=stale, change_voice_state=AsyncMock())
        channel.connect.side_effect = [wavelink.ChannelTimeoutException('timeout'), player]
        monkeypatch.setattr(music.asyncio, 'sleep', AsyncMock())
        result = await cog._connect_voice(guild, channel, SimpleNamespace())
        assert result is player
        stale.disconnect.assert_awaited_once()
        cog.switch_lavalink_server.assert_not_awaited()
        assert channel.connect.await_count == 2
        assert channel.connect.call_args.kwargs['timeout'] >= 30
    asyncio.run(run())


def test_finished_track_advances_once_and_failure_blocks_further_advancement(memory_db):
    from cogs.music import EnhancedMusic
    async def run():
        cog = EnhancedMusic(SimpleNamespace())
        track = SimpleNamespace(title='Next')
        player = SimpleNamespace(guild=SimpleNamespace(id=1), current=None, play=AsyncMock())
        cog.get_queue(1).add(track)
        await cog.on_wavelink_track_end(SimpleNamespace(player=player, track=None, reason='finished'))
        player.play.assert_awaited_once_with(track)
        cog._playback_blocked.add(1)
        cog.get_queue(1).add(track)
        await cog.on_wavelink_track_end(SimpleNamespace(player=player, track=None, reason='finished'))
        assert player.play.await_count == 1
        await cog._play_track(player, track, manual=True)
        assert 1 not in cog._playback_blocked
        assert player.play.await_count == 2
    asyncio.run(run())


def test_track_start_never_sends_empty_or_failed_playback_embed(memory_db, monkeypatch):
    import cogs.music as music
    async def run():
        cog = music.EnhancedMusic(SimpleNamespace())
        player = SimpleNamespace(guild=SimpleNamespace(id=1), current=None,
                                 last_channel=SimpleNamespace(send=AsyncMock()))
        payload = SimpleNamespace(player=player, track=SimpleNamespace(title='failed'))
        monkeypatch.setattr(music.asyncio, 'sleep', AsyncMock())
        await cog.on_wavelink_track_start(payload)
        player.current = payload.track
        cog._playback_blocked.add(1)
        await cog.on_wavelink_track_start(payload)
        player.last_channel.send.assert_not_awaited()
    asyncio.run(run())


def test_concurrent_voice_requests_reuse_healthy_player(memory_db):
    from cogs.music import EnhancedMusic
    async def run():
        cog = EnhancedMusic(SimpleNamespace())
        cog.connect_to_lavalink = AsyncMock(return_value=True)
        guild = SimpleNamespace(id=1, voice_client=None)
        channel = SimpleNamespace(name='General')
        player = SimpleNamespace(connected=True, channel=channel, disconnect=AsyncMock())
        async def connect(**kwargs):
            guild.voice_client = player
            return player
        channel.connect = AsyncMock(side_effect=connect)
        results = await asyncio.gather(cog._connect_voice(guild, channel, None), cog._connect_voice(guild, channel, None))
        assert results == [player, player]
        channel.connect.assert_awaited_once()
        player.disconnect.assert_not_awaited()
    asyncio.run(run())


@pytest.mark.parametrize('event', ['track_start', 'track_end', 'track_exception', 'track_stuck'])
def test_events_for_removed_player_are_ignored(memory_db, event):
    from cogs.music import EnhancedMusic
    cog = EnhancedMusic(SimpleNamespace())
    asyncio.run(getattr(cog, 'on_wavelink_' + event)(SimpleNamespace(player=None)))
