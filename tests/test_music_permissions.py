import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def context():
    channel = SimpleNamespace(id=10)
    player = SimpleNamespace(channel=channel, connected=True)
    guild = SimpleNamespace(id=1, voice_client=player)
    player.guild = guild
    interaction = SimpleNamespace(guild=guild, user=SimpleNamespace(voice=SimpleNamespace(channel=channel)), response=SimpleNamespace(send_message=AsyncMock()))
    return player, interaction


@pytest.mark.parametrize('view_name', ['MusicControlView', 'VolumeView'])
@pytest.mark.parametrize('invalid', ['dm', 'no_voice', 'other_voice', 'stale', 'disconnected'])
def test_playback_controls_reject_invalid_interactions(view_name, invalid):
    import cogs.music as music
    async def run():
        player, interaction = context()
        view = music.MusicControlView(player, SimpleNamespace()) if view_name == 'MusicControlView' else music.VolumeView(player)
        if invalid == 'dm': interaction.guild = None
        elif invalid == 'no_voice': interaction.user.voice = None
        elif invalid == 'other_voice': interaction.user.voice.channel = SimpleNamespace(id=20)
        elif invalid == 'stale': interaction.guild.voice_client = SimpleNamespace(channel=player.channel)
        else: player.connected = False
        assert await view.interaction_check(interaction) is False
        assert interaction.response.send_message.await_args.kwargs['ephemeral'] is True
    asyncio.run(run())


def test_voice_membership_is_rechecked_when_member_leaves():
    from cogs.music import VolumeView
    async def run():
        player, interaction = context()
        view = VolumeView(player)
        assert await view.interaction_check(interaction) is True
        interaction.user.voice = None
        assert await view.interaction_check(interaction) is False
    asyncio.run(run())

@pytest.mark.parametrize('invalid', ['no_voice', 'stale'])
def test_queue_clear_rejects_without_mutating_queue(invalid):
    from cogs.music import MusicQueue, PlaylistView
    async def run():
        player, interaction = context()
        queue = MusicQueue()
        queue.add('keep')
        cog = SimpleNamespace(get_queue=lambda _: queue)
        view = PlaylistView(cog, 1, player)
        if invalid == 'no_voice': interaction.user.voice = None
        else: interaction.guild.voice_client = SimpleNamespace()
        await view.clear_queue.callback(interaction)
        assert queue.queue == ['keep']
        assert interaction.response.send_message.await_args.kwargs['ephemeral'] is True
    asyncio.run(run())


def test_load_modal_rechecks_membership_after_opening():
    from cogs.music import LoadPlaylistModal
    async def run():
        player, interaction = context()
        modal = LoadPlaylistModal(SimpleNamespace(), player)
        assert await modal.interaction_check(interaction) is True
        interaction.user.voice = None
        await modal.on_submit(interaction)
        assert interaction.response.send_message.await_args.kwargs['ephemeral'] is True
    asyncio.run(run())


def test_same_voice_controls_allow_members_without_admin():
    from cogs.music import MusicControlView
    async def run():
        player, interaction = context()
        assert await MusicControlView(player, SimpleNamespace()).interaction_check(interaction) is True
        interaction.response.send_message.assert_not_awaited()
    asyncio.run(run())


@pytest.mark.parametrize('command', ['play', 'search'])
def test_search_selection_rejects_replaced_player(memory_db, monkeypatch, command):
    import cogs.music as music
    async def run():
        player, interaction = context()
        cog = music.EnhancedMusic(SimpleNamespace())
        tracks = [SimpleNamespace(title='One', author='Author', length=100, uri='one'), SimpleNamespace(title='Two', author='Author', length=100, uri='two')]
        monkeypatch.setattr(music.wavelink.Pool, '_Pool__nodes', {'test': SimpleNamespace()})
        monkeypatch.setattr(music.wavelink.Playable, 'search', AsyncMock(return_value=tracks))
        cog._connect_voice = AsyncMock(return_value=player)
        ctx = SimpleNamespace(guild=interaction.guild, voice_client=player, author=interaction.user, channel=SimpleNamespace(), defer=AsyncMock(), send=AsyncMock())
        await getattr(music.EnhancedMusic, command).callback(cog, ctx, **({'search': 'song'} if command == 'play' else {'query': 'song'}))
        view = ctx.send.await_args.kwargs['view']
        assert await view.interaction_check(interaction) is True
        interaction.guild.voice_client = SimpleNamespace(channel=player.channel, connected=True)
        assert await view.interaction_check(interaction) is False
        assert interaction.response.send_message.await_args.kwargs['ephemeral'] is True
        assert cog.get_queue(1).queue == []
    asyncio.run(run())

@pytest.mark.parametrize('view_name', ['SavedPlaylistView', 'LoadPlaylistModal'])
@pytest.mark.parametrize('invalid', ['no_voice', 'stale'])
def test_saved_playlist_ui_rejects_unauthorized_or_stale_session(view_name, invalid):
    import cogs.music as music
    async def run():
        player, interaction = context()
        if view_name == 'SavedPlaylistView':
            view = music.SavedPlaylistView(SimpleNamespace(), 1, player)
        else:
            view = music.LoadPlaylistModal(SimpleNamespace(), player)
        if invalid == 'no_voice': interaction.user.voice = None
        else: interaction.guild.voice_client = SimpleNamespace()
        assert await view.interaction_check(interaction) is False
        assert interaction.response.send_message.await_args.kwargs['ephemeral'] is True
    asyncio.run(run())


def test_playlist_load_does_not_add_tracks_after_player_replaced(memory_db, monkeypatch):
    import cogs.music as music
    async def run():
        player, interaction = context()
        interaction.user.id = 1
        cog = music.EnhancedMusic(SimpleNamespace())
        cog.saved_playlists = {'1': {'mix': [{'uri': 'one'}]}}
        modal = music.LoadPlaylistModal(cog, player)
        modal.name_input._value = 'mix'
        async def search(_):
            interaction.guild.voice_client = SimpleNamespace()
            return [SimpleNamespace(title='Track')]
        monkeypatch.setattr(music.wavelink.Playable, 'search', search)
        await modal.on_submit(interaction)
        assert cog.get_queue(1).queue == []
        assert interaction.response.send_message.await_args.kwargs['ephemeral'] is True
    asyncio.run(run())
