import asyncio
from aiohttp import web, ClientSession


def test_relay_handles_redirects_and_preserves_seek_ranges(monkeypatch):
    from utils import audio_relay
    async def run():
        app=web.Application()
        async def redirect(request): raise web.HTTPFound('/audio')
        async def audio(request):
            assert request.headers['Range']=='bytes=4-7'
            return web.Response(body=b'4567',status=206,headers={'Content-Type':'audio/webm','Content-Range':'bytes 4-7/10'})
        app.router.add_get('/redirect',redirect); app.router.add_get('/audio',audio)
        runner=web.AppRunner(app); await runner.setup()
        site=web.TCPSite(runner,'127.0.0.1',0); await site.start()
        monkeypatch.setattr(audio_relay,'validate_audio_url',lambda value:value)
        relay=audio_relay.AudioRelay()
        try:
            url=await relay.add(f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}/redirect')
            assert relay.session.timeout.total is None  # Long tracks must not have a fixed stream lifetime.
            async with ClientSession() as session:
                async with session.get(url,headers={'Range':'bytes=4-7'},allow_redirects=False) as response:
                    assert response.status==206
                    assert response.headers['Content-Range']=='bytes 4-7/10'
                    assert await response.read()==b'4567'
        finally:
            await relay.close(); await runner.cleanup()
    asyncio.run(run())


def test_relay_retries_transient_failure_before_giving_up(monkeypatch):
    from utils import audio_relay
    async def run():
        calls=[]
        async def audio(request):
            calls.append(1)
            if len(calls)==1:return web.Response(status=503)
            return web.Response(body=b'audio',headers={'Content-Type':'audio/webm'})
        app=web.Application();app.router.add_get('/audio',audio)
        runner=web.AppRunner(app);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
        monkeypatch.setattr(audio_relay,'validate_audio_url',lambda value:value)
        relay=audio_relay.AudioRelay()
        try:
            url=await relay.add(f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}/audio')
            async with ClientSession() as session:
                async with session.get(url) as response:
                    assert response.status==200 and await response.read()==b'audio'
            assert len(calls)==2
        finally:await relay.close();await runner.cleanup()
    asyncio.run(run())


def test_relay_refreshes_rejected_url_once_for_same_track(monkeypatch):
    from utils import audio_relay
    from unittest.mock import AsyncMock
    async def run():
        async def old(request):return web.Response(status=403)
        async def new(request):return web.Response(body=b'new-audio',headers={'Content-Type':'audio/webm'})
        app=web.Application();app.router.add_get('/old',old);app.router.add_get('/new',new)
        runner=web.AppRunner(app);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
        base=f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}'
        refresh=AsyncMock(return_value=base+'/new')
        monkeypatch.setattr(audio_relay,'validate_audio_url',lambda value:value)
        relay=audio_relay.AudioRelay()
        try:
            url=await relay.add(base+'/old',refresh=refresh)
            async with ClientSession() as session:
                async with session.get(url) as response:assert await response.read()==b'new-audio'
                async with session.get(url) as response:assert response.status==200
            refresh.assert_awaited_once()
        finally:await relay.close();await runner.cleanup()
    asyncio.run(run())


def test_permanent_upstream_failure_has_bounded_retry(monkeypatch):
    from utils import audio_relay
    async def run():
        calls=[]
        async def fail(request):calls.append(1);return web.Response(status=503)
        app=web.Application();app.router.add_get('/fail',fail)
        runner=web.AppRunner(app);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
        monkeypatch.setattr(audio_relay,'validate_audio_url',lambda value:value)
        relay=audio_relay.AudioRelay()
        try:
            url=await relay.add(f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}/fail')
            async with ClientSession() as session:
                async with session.get(url) as response:assert response.status==502
            assert len(calls)==3
        finally:await relay.close();await runner.cleanup()
    asyncio.run(run())
