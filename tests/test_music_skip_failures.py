import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import wavelink


def test_failed_song_skips_to_queue_once_and_ignores_single_loop(memory_db):
    from cogs.music import EnhancedMusic
    async def run():
        cog=EnhancedMusic(SimpleNamespace())
        old=SimpleNamespace(source='http',identifier='old',title='Bad',extras={})
        next_track=SimpleNamespace(source='http',identifier='next',title='Good',extras={})
        player=SimpleNamespace(guild=SimpleNamespace(id=1),current=None,connected=True,play=AsyncMock(),last_channel=SimpleNamespace(send=AsyncMock()),autoplay=wavelink.AutoPlayMode.disabled)
        await cog._play_track(player,old,manual=True);player.play.reset_mock()
        queue=cog.get_queue(1);queue.loop_mode='track';queue.add_to_history(old);queue.add(old);queue.add(next_track)
        payload=SimpleNamespace(player=player,track=old,exception={},reason='loadFailed')
        await cog.on_wavelink_track_exception(payload)
        await cog.on_wavelink_track_end(payload)
        player.play.assert_awaited_once_with(next_track)
        assert player.last_channel.send.await_count==1
        assert '跳過' in player.last_channel.send.call_args.args[0]
        assert 1 not in cog._playback_blocked
    asyncio.run(run())


def test_three_consecutive_failures_halt_without_looping(memory_db):
    from cogs.music import EnhancedMusic
    async def run():
        cog=EnhancedMusic(SimpleNamespace());cog.autoplay_enabled[1]=False
        tracks=[SimpleNamespace(source='http',identifier=str(n),title=str(n),extras={}) for n in range(4)]
        player=SimpleNamespace(guild=SimpleNamespace(id=1),current=None,connected=True,play=AsyncMock(),last_channel=SimpleNamespace(send=AsyncMock()),autoplay=wavelink.AutoPlayMode.disabled)
        await cog._play_track(player,tracks[0],manual=True)
        for track in tracks[1:]:cog.get_queue(1).add(track)
        player.play.reset_mock()
        for track in tracks[:3]:await cog.on_wavelink_track_exception(SimpleNamespace(player=player,track=track,exception={}))
        assert player.play.await_count==2
        assert 1 in cog._playback_blocked
        assert tracks[3] in cog.get_queue(1).queue
        await cog._play_track(player,tracks[3],manual=True)
        assert 1 not in cog._playback_blocked and 1 not in cog._consecutive_failures
    asyncio.run(run())


def test_failed_song_can_use_enabled_autoplay(memory_db):
    from cogs.music import EnhancedMusic
    async def run():
        cog=EnhancedMusic(SimpleNamespace());cog.autoplay_enabled[1]=True
        old=SimpleNamespace(source='http',identifier='old',title='Bad',extras={})
        new=SimpleNamespace(source='http',identifier='new',title='Good',extras={})
        player=SimpleNamespace(guild=SimpleNamespace(id=1),current=None,connected=True,play=AsyncMock(),last_channel=SimpleNamespace(send=AsyncMock()),autoplay=wavelink.AutoPlayMode.disabled)
        await cog._play_track(player,old,manual=True);player.play.reset_mock()
        async def recommend(player):cog.get_queue(1).add(new)
        cog.auto_recommend_and_play=AsyncMock(side_effect=recommend)
        await cog.on_wavelink_track_exception(SimpleNamespace(player=player,track=old,exception={}))
        player.play.assert_awaited_once_with(new)
    asyncio.run(run())


def test_stop_during_failure_transition_cannot_restart_playback(memory_db):
    from cogs.music import EnhancedMusic
    async def run():
        cog=EnhancedMusic(SimpleNamespace())
        old=SimpleNamespace(source='http',identifier='old',title='Bad',extras={})
        new=SimpleNamespace(source='http',identifier='new',title='Good',extras={})
        player=SimpleNamespace(guild=SimpleNamespace(id=1),current=None,connected=True,play=AsyncMock(),last_channel=SimpleNamespace(send=AsyncMock()),autoplay=wavelink.AutoPlayMode.disabled)
        await cog._play_track(player,old,manual=True);player.play.reset_mock();cog.get_queue(1).add(new)
        async with cog._voice_locks[1]:
            task=asyncio.create_task(cog.on_wavelink_track_exception(SimpleNamespace(player=player,track=old,exception={})))
            await asyncio.sleep(0)
            cog._cancel_pending_playback(1)
        await task
        player.play.assert_not_awaited()
        player.last_channel.send.assert_not_awaited()
    asyncio.run(run())
