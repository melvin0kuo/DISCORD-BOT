"""Loopback-only relay for YouTube audio redirects and byte-range requests."""
import asyncio
import secrets
import time
from urllib.parse import urljoin

import aiohttp
from aiohttp import web


def validate_audio_url(url):
    from utils.youtube_fallback import validate_audio_url as validate
    return validate(url)


class AudioRelay:
    def __init__(self):
        self.runner = None
        self.session = None
        self.urls = {}
        self.lock = asyncio.Lock()

    async def add(self, url):
        validate_audio_url(url)
        async with self.lock:
            if self.runner is None:
                app = web.Application()
                app.router.add_get('/audio/{token}', self.serve)
                self.runner = web.AppRunner(app, access_log=None)
                await self.runner.setup()
                site = web.TCPSite(self.runner, '127.0.0.1', 0)
                await site.start()
                self.port = site._server.sockets[0].getsockname()[1]
                self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, connect=15, sock_read=30))
            now = time.monotonic()
            self.urls = {key: value for key, value in self.urls.items() if value[1] > now}
            if len(self.urls) >= 128:
                self.urls.pop(next(iter(self.urls)))
            token = secrets.token_urlsafe(24)
            self.urls[token] = (url, now + 6 * 3600)
            return f'http://127.0.0.1:{self.port}/audio/{token}'

    async def serve(self, request):
        entry = self.urls.get(request.match_info['token'])
        if entry is None or entry[1] < time.monotonic():
            raise web.HTTPNotFound()
        headers = {}
        if request.headers.get('Range'):
            headers['Range'] = request.headers['Range']
        url = entry[0]
        for _ in range(10):
            validate_audio_url(url)
            async with self.session.get(url, headers=headers, allow_redirects=False) as upstream:
                if upstream.status in (301, 302, 303, 307, 308):
                    url = urljoin(url, upstream.headers.get('Location', ''))
                    continue
                if upstream.status not in (200, 206, 416):
                    raise web.HTTPBadGateway()
                if upstream.status != 416 and not upstream.headers.get('Content-Type', '').startswith('audio/'):
                    raise web.HTTPBadGateway()
                forwarded = {key: value for key, value in upstream.headers.items()
                             if key.lower() in ('content-type', 'content-length', 'content-range', 'accept-ranges')}
                response = web.StreamResponse(status=upstream.status, headers=forwarded)
                await response.prepare(request)
                if request.method != 'HEAD':
                    async for chunk in upstream.content.iter_chunked(65536):
                        try:
                            await response.write(chunk)
                        except ConnectionError:
                            return response  # Normal when Lavalink seeks or skips.
                try:
                    await response.write_eof()
                except ConnectionError:
                    pass
                return response
        raise web.HTTPBadGateway()

    async def close(self):
        if self.runner:
            await self.runner.cleanup()
        if self.session:
            await self.session.close()
        self.runner = self.session = None
        self.urls.clear()


audio_relay = AudioRelay()
