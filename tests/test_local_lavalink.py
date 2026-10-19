import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
import zipfile

import pytest


def test_local_manager_never_loads_public_nodes_from_cache(tmp_path):
    from utils.lavalink_manager import LavalinkServerManager, LavalinkServer
    manager = LavalinkServerManager()
    cached = tmp_path / 'servers.json'
    cached.write_text(json.dumps({'servers': [{'uri': 'https://public.example', 'password': 'public'}]}))
    manager.cache_file = str(cached)
    manager.fetch_server_list = AsyncMock(return_value=[LavalinkServer('https://public.example', 'public')])
    asyncio.run(manager.update_server_list(force=True))
    assert [server.uri for server in manager.servers] == ['http://127.0.0.1:2333']


@pytest.mark.parametrize('status,data', [
    (200, None), (200, {}), (200, {'version': {'major': 3}}), (401, None),
])
def test_local_manager_rejects_html_and_invalid_api_responses(status, data):
    from utils.lavalink_manager import LavalinkServerManager, LavalinkServer
    class Response:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def json(self, **kwargs):
            if data is None: raise ValueError('HTML response')
            return data
    response = Response()
    response.status = status
    manager = LavalinkServerManager()
    manager._get_session = AsyncMock(return_value=SimpleNamespace(get=lambda *a, **kw: response))
    server = LavalinkServer('http://127.0.0.1:2333', 'local')
    assert asyncio.run(manager.test_server(server)) is False


def test_local_manager_validates_version_four_api():
    from utils.lavalink_manager import LavalinkServerManager
    class Response:
        status = 200
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def json(self, **kwargs):
            return {'version': {'major': 4, 'semver': '4.2.2'}, 'sourceManagers': ['youtube']}
    manager = LavalinkServerManager()
    manager._get_session = AsyncMock(return_value=SimpleNamespace(get=lambda *a, **kw: Response()))
    assert asyncio.run(manager.test_server(manager.servers[0])) is True


def test_local_reconnect_reuses_current_local_server():
    from utils.lavalink_manager import LavalinkServerManager
    manager = LavalinkServerManager()
    manager.current_server = manager.servers[0]
    manager.test_server = AsyncMock(return_value=True)
    assert asyncio.run(manager.get_next_server()).uri == 'http://127.0.0.1:2333'


def test_java_archive_cannot_extract_outside_runtime(tmp_path):
    from utils.local_lavalink import extract_runtime
    archive = tmp_path / 'java.zip'
    with zipfile.ZipFile(archive, 'w') as zipped:
        zipped.writestr('../outside.txt', 'bad')
    with pytest.raises(ValueError):
        extract_runtime(archive, tmp_path / 'runtime')
    assert not (tmp_path / 'outside.txt').exists()


def test_runtime_reuses_running_service_without_spawning_java(tmp_path):
    from utils.local_lavalink import LocalLavalinkRuntime
    runtime = LocalLavalinkRuntime(root=tmp_path)
    runtime.is_ready = AsyncMock(return_value=True)
    async def run():
        assert await runtime.ensure_started() is True
        assert runtime.process is None
        await runtime.close()
    asyncio.run(run())


def test_music_connection_ejects_public_nodes_before_local_connect(memory_db, monkeypatch):
    import wavelink
    import cogs.music as music
    from utils.lavalink_manager import LavalinkServerManager
    nodes = {}
    removed = []
    async def close_public(**kwargs):
        removed.append(kwargs.get('eject'))
        nodes.pop('public', None)
    nodes['public'] = SimpleNamespace(identifier='public', uri='https://public.example',
                                     status=wavelink.NodeStatus.CONNECTED, close=close_public)
    monkeypatch.setattr(wavelink.Pool, '_Pool__nodes', nodes)
    manager = LavalinkServerManager()
    manager.get_best_server = AsyncMock(return_value=manager.servers[0])
    monkeypatch.setattr(music, 'lavalink_manager', manager)
    monkeypatch.setattr(music, 'local_lavalink', SimpleNamespace(ensure_started=AsyncMock(return_value=True)), raising=False)
    async def connect(*, nodes: list, **kwargs):
        node = nodes[0]
        node._status = wavelink.NodeStatus.CONNECTED
        wavelink.Pool._Pool__nodes[node.identifier] = node
        return wavelink.Pool.nodes
    monkeypatch.setattr(wavelink.Pool, 'connect', connect)
    async def run():
        cog = music.EnhancedMusic(SimpleNamespace())
        try:
            assert await cog.connect_to_lavalink() is True
            assert removed == [True]
            assert [node.uri for node in wavelink.Pool.nodes.values()] == ['http://127.0.0.1:2333']
        finally:
            await manager.close_session()
    asyncio.run(run())


def test_node_in_pool_is_not_success_until_websocket_ready(memory_db, monkeypatch):
    import wavelink
    import config
    import cogs.music as music
    from utils.lavalink_manager import LavalinkServerManager
    manager = LavalinkServerManager()
    manager.get_best_server = AsyncMock(return_value=manager.servers[0])
    monkeypatch.setattr(music, 'lavalink_manager', manager)
    monkeypatch.setattr(music, 'local_lavalink', SimpleNamespace(ensure_started=AsyncMock(return_value=True)))
    monkeypatch.setattr(config, 'LAVALINK_CONNECT_TIMEOUT', 0.05)
    monkeypatch.setattr(wavelink.Pool, '_Pool__nodes', {})
    async def connect(*, nodes, **kwargs):
        for node in nodes:
            wavelink.Pool._Pool__nodes[node.identifier] = node
        return wavelink.Pool.nodes
    monkeypatch.setattr(wavelink.Pool, 'connect', connect)
    async def run():
        try:
            cog = music.EnhancedMusic(SimpleNamespace())
            assert await cog.connect_to_lavalink() is False
            assert wavelink.Pool.nodes == {}
        finally:
            await manager.close_session()
    asyncio.run(run())


def test_reload_ejects_nodes_before_closing_shared_session(memory_db, monkeypatch):
    import cogs.music as music
    import wavelink
    events = []
    nodes = {}
    async def close_node(**kwargs):
        events.append('node')
        nodes.clear()
    async def close_session():
        events.append('session')
    nodes['local'] = SimpleNamespace(close=close_node)
    monkeypatch.setattr(wavelink.Pool, '_Pool__nodes', nodes)
    monkeypatch.setattr(music, 'lavalink_manager', SimpleNamespace(close_session=close_session))
    monkeypatch.setattr(music.importlib, 'reload', lambda module: SimpleNamespace(lavalink_manager=None))
    asyncio.run(music.EnhancedMusic(SimpleNamespace(is_ready=lambda: False)).cog_load())
    assert events == ['node', 'session']


@pytest.mark.parametrize('version, expected', [('1.8.0_451', False), ('11.0.28', False), ('17.0.16', True), ('21.0.12', True)])
def test_java_requires_supported_version(monkeypatch, version, expected):
    from utils.local_lavalink import java_is_supported
    import subprocess
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=0, stdout='', stderr=f'openjdk version "{version}"'))
    assert java_is_supported('java') is expected
