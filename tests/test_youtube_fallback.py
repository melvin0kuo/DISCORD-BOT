import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import wavelink


def test_finished_event_during_fallback_must_not_advance_queue(memory_db, monkeypatch):
    import cogs.music as music
    async def run():
        cog = music.EnhancedMusic(SimpleNamespace())
        original = SimpleNamespace(source='youtube', identifier='SZiwpL62to8', encoded='original', title='ANTIFRAGILE', extras={})
        fallback = SimpleNamespace(source='http', identifier='audio', encoded='fallback', extras={})
        player = SimpleNamespace(guild=SimpleNamespace(id=1), current=None, play=AsyncMock(), connected=True,
                                 last_channel=SimpleNamespace(send=AsyncMock()), autoplay=wavelink.AutoPlayMode.disabled)
        await cog._play_track(player, original, manual=True)
        player.play.reset_mock()
        cog.autoplay_enabled[1] = True
        cog.auto_recommend_and_play = AsyncMock()
        ready, release = asyncio.Event(), asyncio.Event()
        async def resolve(track):
            ready.set(); await release.wait(); return fallback
        monkeypatch.setattr(music, 'resolve_youtube_fallback', resolve)
        task = asyncio.create_task(cog.on_wavelink_track_exception(SimpleNamespace(player=player,track=original,exception={})))
        await ready.wait()
        await cog.on_wavelink_track_end(SimpleNamespace(player=player,track=original,reason='finished'))
        release.set(); await task
        cog.auto_recommend_and_play.assert_not_awaited()
        player.play.assert_awaited_once_with(fallback)
    asyncio.run(run())


def test_fallback_passes_final_redirect_url_to_lavalink(monkeypatch):
    import utils.youtube_fallback as fallback
    from utils.audio_relay import audio_relay
    from unittest.mock import Mock
    async def run():
        original = SimpleNamespace(identifier='SZiwpL62to8', title='ANTIFRAGILE', author='LE SSERAFIM', uri='https://www.youtube.com/watch?v=SZiwpL62to8', artwork=None, length=180000, extras={})
        monkeypatch.setattr(fallback, 'extract_audio_url', AsyncMock(return_value='https://a.googlevideo.com/original'))
        response = SimpleNamespace(status=206, url='https://b.googlevideo.com/final', headers={'Content-Type':'audio/webm'}, content=SimpleNamespace(read=AsyncMock(return_value=b'audio')))
        context = AsyncMock(); context.__aenter__.return_value = response
        session = SimpleNamespace(get=Mock(return_value=context))
        session_context = AsyncMock(); session_context.__aenter__.return_value = session
        monkeypatch.setattr(fallback.aiohttp, 'ClientSession', Mock(return_value=session_context))
        relay = AsyncMock(return_value='http://127.0.0.1:12345/audio/token')
        monkeypatch.setattr(audio_relay, 'add', relay)
        search = AsyncMock(return_value=[])
        monkeypatch.setattr(fallback.wavelink.Playable, 'search', search)
        with pytest.raises(RuntimeError,match='載入備援'):
            await fallback.resolve_youtube_fallback(original)
        relay.assert_awaited_once()
        assert relay.call_args.args[0]=='https://b.googlevideo.com/final'
        assert callable(relay.call_args.kwargs['refresh'])
        assert search.call_args.args[0] == 'http://127.0.0.1:12345/audio/token'
    asyncio.run(run())


def test_skip_while_fallback_loading_plays_next_and_invalidates_old_work(memory_db, monkeypatch):
    import cogs.music as music
    async def run():
        cog = music.EnhancedMusic(SimpleNamespace())
        original = SimpleNamespace(source='youtube',identifier='SZiwpL62to8',encoded='old',title='Old',extras={})
        next_track = SimpleNamespace(source='http',identifier='new',encoded='new',title='Next',extras={})
        player = SimpleNamespace(guild=SimpleNamespace(id=1),current=None,play=AsyncMock(),stop=AsyncMock(),connected=True,
                                 last_channel=SimpleNamespace(send=AsyncMock()),autoplay=wavelink.AutoPlayMode.disabled)
        await cog._play_track(player, original, manual=True)
        cog.get_queue(1).add(next_track)
        cog.get_queue(1).loop_mode = 'track'
        cog.get_queue(1).add_to_history(original)
        ready, release = asyncio.Event(), asyncio.Event()
        async def resolve(track):
            ready.set(); await release.wait(); return SimpleNamespace(source='http',extras={})
        monkeypatch.setattr(music,'resolve_youtube_fallback',resolve)
        task=asyncio.create_task(cog.on_wavelink_track_exception(SimpleNamespace(player=player,track=original,exception={})))
        await ready.wait()
        player.play.reset_mock()
        assert await cog._skip_track(player)
        release.set(); await task
        player.play.assert_awaited_once_with(next_track)
    asyncio.run(run())


def test_skip_waits_for_inflight_fallback_before_stopping(memory_db, monkeypatch):
    import cogs.music as music
    async def run():
        cog = music.EnhancedMusic(SimpleNamespace())
        original=SimpleNamespace(source='youtube',identifier='SZiwpL62to8',encoded='old',title='Old',extras={})
        fallback=SimpleNamespace(source='http',identifier='audio',encoded='audio',extras={})
        player=SimpleNamespace(guild=SimpleNamespace(id=1),current=None,play=AsyncMock(),stop=AsyncMock(),connected=True,
                               last_channel=SimpleNamespace(send=AsyncMock()),autoplay=wavelink.AutoPlayMode.disabled)
        await cog._play_track(player,original,manual=True)
        entered,release=asyncio.Event(),asyncio.Event()
        async def play(track):
            entered.set(); await release.wait()
        player.play=play
        monkeypatch.setattr(music,'resolve_youtube_fallback',AsyncMock(return_value=fallback))
        recovery=asyncio.create_task(cog.on_wavelink_track_exception(SimpleNamespace(player=player,track=original,exception={})))
        await entered.wait()
        skipping=asyncio.create_task(cog._skip_track(player))
        await asyncio.sleep(0)
        player.stop.assert_not_awaited()
        release.set(); await recovery; await skipping
        player.stop.assert_awaited_once()
        await cog.cog_unload()
    asyncio.run(run())


@pytest.mark.parametrize('command', ['next', 'back'])
def test_manual_switch_does_not_wait_for_stopped_or_repeat_track_loop(memory_db, command):
    import cogs.music as music
    async def run():
        cog=music.EnhancedMusic(SimpleNamespace())
        old=SimpleNamespace(source='youtube',identifier='old',encoded='old',title='Old',extras={})
        target=SimpleNamespace(source='http',identifier='target',encoded='target',title='Target',extras={})
        player=SimpleNamespace(guild=SimpleNamespace(id=1),current=None,play=AsyncMock(),stop=AsyncMock())
        await cog._play_track(player,old,manual=True)
        player.play.reset_mock()
        queue=cog.get_queue(1); queue.loop_mode='track'
        if command=='next':
            queue.add_to_history(old); queue.add(target)
        else:
            queue.add_to_history(target); queue.add_to_history(old)
        ctx=SimpleNamespace(guild=player.guild,voice_client=player,send=AsyncMock())
        await getattr(type(cog),command).callback(cog,ctx)
        player.play.assert_awaited_once_with(target)
        player.stop.assert_not_awaited()
    asyncio.run(run())


def test_failure_arriving_during_autoplay_search_cannot_replace_recovery(memory_db, monkeypatch):
    import cogs.music as music
    async def run():
        cog=music.EnhancedMusic(SimpleNamespace())
        original=SimpleNamespace(source='youtube',identifier='SZiwpL62to8',encoded='old',title='Old',extras={})
        fallback=SimpleNamespace(source='http',identifier='audio',encoded='audio',extras={})
        recommended=SimpleNamespace(source='youtube',identifier='other',encoded='other',title='Other',extras={})
        player=SimpleNamespace(guild=SimpleNamespace(id=1),current=None,play=AsyncMock(),connected=True,
                               last_channel=SimpleNamespace(send=AsyncMock()),autoplay=wavelink.AutoPlayMode.disabled)
        await cog._play_track(player,original,manual=True); player.play.reset_mock()
        cog.autoplay_enabled[1]=True
        search_started,search_release,recovery_started,recovery_release=[asyncio.Event() for _ in range(4)]
        async def recommend(p):
            search_started.set(); await search_release.wait(); cog.get_queue(1).add(recommended)
        async def resolve(track):
            recovery_started.set(); await recovery_release.wait(); return fallback
        cog.auto_recommend_and_play=recommend
        monkeypatch.setattr(music,'resolve_youtube_fallback',resolve)
        ending=asyncio.create_task(cog.on_wavelink_track_end(SimpleNamespace(player=player,track=original,reason='finished')))
        await search_started.wait()
        recovery=asyncio.create_task(cog.on_wavelink_track_exception(SimpleNamespace(player=player,track=original,exception={})))
        await recovery_started.wait(); search_release.set(); await ending
        player.play.assert_not_awaited()
        recovery_release.set(); await recovery
        player.play.assert_awaited_once_with(fallback)
    asyncio.run(run())


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
