import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock


def test_cipher_reuses_existing_service_without_owning_process(tmp_path):
    from utils.youtube_runtime import LocalCipherRuntime
    runtime = LocalCipherRuntime(tmp_path)
    runtime.is_ready = AsyncMock(return_value=True)
    assert asyncio.run(runtime.ensure_started()) is True
    assert runtime.process is None


def test_cipher_starts_on_loopback_without_bot_secrets(tmp_path, monkeypatch):
    import utils.youtube_runtime as runtime_module
    runtime = runtime_module.LocalCipherRuntime(tmp_path)
    runtime.is_ready = AsyncMock(side_effect=[False, True])
    (tmp_path / '.runtime' / 'deno').mkdir(parents=True)
    (tmp_path / '.runtime' / 'deno' / 'deno.exe').touch()
    (tmp_path / '.runtime' / 'yt-cipher').mkdir()
    (tmp_path / '.runtime' / 'yt-cipher' / 'server.ts').touch()
    monkeypatch.setenv('DISCORD_TOKEN', 'secret')
    spawn = Mock(return_value=SimpleNamespace(poll=lambda: None))
    monkeypatch.setattr(runtime_module.subprocess, 'Popen', spawn)
    assert asyncio.run(runtime.ensure_started()) is True
    env = spawn.call_args.kwargs['env']
    assert env['HOST'] == '127.0.0.1'
    assert 'DISCORD_TOKEN' not in env


def test_fresh_cipher_without_metrics_is_ready(tmp_path, monkeypatch):
    from aiohttp import web
    import utils.youtube_runtime as runtime_module
    async def run():
        app = web.Application()
        async def metrics(request):
            return web.Response(text='')
        async def schema(request):
            return web.Response(text='openapi: 3.0.0\ninfo:\n  title: yt-cipher API')
        app.router.add_get('/metrics', metrics)
        app.router.add_get('/swagger.yaml', schema)
        runner = web.AppRunner(app);await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0);await site.start()
        monkeypatch.setattr(runtime_module, 'CIPHER_URL', f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}', raising=False)
        try:
            assert await runtime_module.LocalCipherRuntime(tmp_path).is_ready()
        finally:
            await runner.cleanup()
    asyncio.run(run())
