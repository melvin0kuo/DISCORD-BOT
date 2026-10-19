import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import wavelink


def test_youtube_failure_retries_same_track_once_without_recommendation(memory_db, monkeypatch):
    import cogs.music as music
    async def run():
        cog = music.EnhancedMusic(SimpleNamespace())
        original = SimpleNamespace(source='youtube', identifier='1CTced9CMMk', encoded='original', title='Loser')
        fallback = SimpleNamespace(source='http', encoded='fallback', title='Loser')
        monkeypatch.setattr(music, 'resolve_youtube_fallback', AsyncMock(return_value=fallback), raising=False)
        player = SimpleNamespace(guild=SimpleNamespace(id=1), current=None, play=AsyncMock(),
                                 last_channel=SimpleNamespace(send=AsyncMock()), autoplay=wavelink.AutoPlayMode.disabled)
        payload = SimpleNamespace(player=player, track=original, exception={}, reason='loadFailed')
        await cog.on_wavelink_track_exception(payload)
        await cog.on_wavelink_track_end(payload)
        player.play.assert_awaited_once_with(fallback)
        music.resolve_youtube_fallback.assert_awaited_once_with(original)
        assert not player.last_channel.send.called
        assert 1 not in cog._playback_blocked
        await cog.on_wavelink_track_end(SimpleNamespace(player=player, track=fallback, reason='loadFailed'))
        assert player.last_channel.send.await_count == 1
    asyncio.run(run())


def test_stopped_request_cannot_resume_after_slow_fallback(memory_db, monkeypatch):
    import cogs.music as music
    async def run():
        cog = music.EnhancedMusic(SimpleNamespace())
        original = SimpleNamespace(source='youtube', identifier='1CTced9CMMk', encoded='original', title='Loser')
        player = SimpleNamespace(guild=SimpleNamespace(id=1), current=None, play=AsyncMock(), connected=True,
                                 last_channel=SimpleNamespace(send=AsyncMock()), autoplay=wavelink.AutoPlayMode.disabled)
        started, release = asyncio.Event(), asyncio.Event()
        async def resolve(track):
            started.set()
            await release.wait()
            return SimpleNamespace(source='http')
        monkeypatch.setattr(music, 'resolve_youtube_fallback', resolve, raising=False)
        task = asyncio.create_task(cog.on_wavelink_track_exception(SimpleNamespace(player=player, track=original, exception={})))
        await asyncio.wait_for(started.wait(), 1)
        cog._cancel_pending_playback(1)
        release.set()
        await task
        player.play.assert_not_awaited()
    asyncio.run(run())


@pytest.mark.parametrize('url', ['http://127.0.0.1/a', 'https://googlevideo.com.evil.test/a', 'file:///test'])
def test_fallback_rejects_non_google_audio_url(url):
    from utils.youtube_fallback import validate_audio_url
    with pytest.raises(ValueError):
        validate_audio_url(url)


def test_extractor_timeout_kills_and_reaps_child(monkeypatch):
    import utils.youtube_fallback as fallback
    from unittest.mock import Mock
    process = SimpleNamespace(returncode=None, kill=Mock(),
                              communicate=AsyncMock(side_effect=[asyncio.TimeoutError(), (b'', b'')]))
    monkeypatch.setattr(fallback.asyncio, 'create_subprocess_exec', AsyncMock(return_value=process))
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(fallback.extract_audio_url('1CTced9CMMk'))
    process.kill.assert_called_once()
    assert process.communicate.await_count == 2


def test_extractor_rejects_different_video(monkeypatch):
    import json
    import utils.youtube_fallback as fallback
    process = SimpleNamespace(returncode=0, communicate=AsyncMock(return_value=(json.dumps({
        'id': 'other_video', 'vcodec': 'none', 'url': 'https://a.googlevideo.com/audio'}).encode(), b'')))
    monkeypatch.setattr(fallback.asyncio, 'create_subprocess_exec', AsyncMock(return_value=process))
    with pytest.raises(ValueError, match='原影片'):
        asyncio.run(fallback.extract_audio_url('1CTced9CMMk'))


@pytest.mark.parametrize('event', ['track_exception', 'track_stuck'])
@pytest.mark.parametrize('new_song', [False, True])
def test_late_failure_after_stop_or_new_song_is_ignored(memory_db, monkeypatch, new_song, event):
    import cogs.music as music
    async def run():
        cog = music.EnhancedMusic(SimpleNamespace())
        old = SimpleNamespace(source='youtube', encoded='old', identifier='1CTced9CMMk', title='Old')
        player = SimpleNamespace(guild=SimpleNamespace(id=1), connected=True, play=AsyncMock(), current=None,
                                 last_channel=SimpleNamespace(send=AsyncMock()), autoplay=wavelink.AutoPlayMode.disabled)
        await cog._play_track(player, old, manual=True)
        if new_song:
            await cog._play_track(player, SimpleNamespace(encoded='new'), manual=True)
        else:
            cog._cancel_pending_playback(1)
        player.play.reset_mock()
        resolver = AsyncMock(return_value=SimpleNamespace(source='http', encoded='http'))
        monkeypatch.setattr(music, 'resolve_youtube_fallback', resolver)
        await getattr(cog, 'on_wavelink_' + event)(SimpleNamespace(player=player, track=old, exception={}))
        resolver.assert_not_awaited()
        player.play.assert_not_awaited()
        player.last_channel.send.assert_not_awaited()
    asyncio.run(run())


def test_exhausted_youtube_returns_soundcloud_choices_without_playing_them(memory_db, monkeypatch):
    import cogs.music as music
    async def run():
        cog = music.EnhancedMusic(SimpleNamespace())
        original = SimpleNamespace(source='youtube', identifier='1CTced9CMMk', encoded='original', title='Loser', author='BIGBANG')
        monkeypatch.setattr(music, 'resolve_youtube_fallback', AsyncMock(side_effect=RuntimeError('unavailable')))
        monkeypatch.setattr(music.wavelink.Playable, 'search', AsyncMock(return_value=[
            SimpleNamespace(title='Loser', uri='https://soundcloud.com/artist/loser')]))
        player = SimpleNamespace(guild=SimpleNamespace(id=1), current=None, play=AsyncMock(),
                                 last_channel=SimpleNamespace(send=AsyncMock()), autoplay=wavelink.AutoPlayMode.disabled)
        await cog.on_wavelink_track_exception(SimpleNamespace(player=player, track=original, exception={}))
        player.play.assert_not_awaited()
        text = player.last_channel.send.call_args.args[0]
        assert 'https://soundcloud.com/artist/loser' in text
        assert '/play' in text
    asyncio.run(run())


def test_stuck_candidate_search_cannot_stop_new_song(memory_db, monkeypatch):
    import cogs.music as music
    async def run():
        cog = music.EnhancedMusic(SimpleNamespace())
        old = SimpleNamespace(source='youtube', encoded='old', title='Old')
        new = SimpleNamespace(encoded='new')
        player = SimpleNamespace(guild=SimpleNamespace(id=1), current=None, play=AsyncMock(), stop=AsyncMock(),
                                 last_channel=SimpleNamespace(send=AsyncMock()), autoplay=wavelink.AutoPlayMode.disabled)
        await cog._play_track(player, old, manual=True)
        started, release = asyncio.Event(), asyncio.Event()
        async def search(*args, **kwargs):
            started.set()
            await release.wait()
            return []
        monkeypatch.setattr(music.wavelink.Playable, 'search', search)
        task = asyncio.create_task(cog.on_wavelink_track_stuck(SimpleNamespace(player=player, track=old)))
        await asyncio.wait_for(started.wait(), 1)
        await cog._play_track(player, new, manual=True)
        release.set()
        await task
        player.stop.assert_not_awaited()
        player.last_channel.send.assert_not_awaited()
    asyncio.run(run())
