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
