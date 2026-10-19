"""本機 Lavalink 節點管理；不讀取或連線至公共節點清單。"""

import logging
import asyncio
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import aiohttp
import wavelink
import config

logger = logging.getLogger(__name__)


@dataclass
class LavalinkServer:
    uri: str
    password: str
    name: str = 'Local Lavalink'
    region: str = 'Local'
    status: str = 'unknown'
    last_check: float = 0
    response_time: float = 0
    error_count: int = 0
    version: str = '4.x'
    ssl: bool = False
    priority: int = 0


class LavalinkServerManager:
    def __init__(self):
        self.uri = config.LAVALINK_URI.rstrip('/')
        parsed = urlsplit(self.uri)
        if parsed.scheme not in ('http', 'https') or parsed.hostname not in ('127.0.0.1', 'localhost', '::1'):
            raise ValueError('本機 Lavalink 僅接受 loopback 網址')
        self.servers = [LavalinkServer(self.uri, config.LAVALINK_PASSWORD)]
        self.current_server = None
        self.session = None
        self.last_fetch_time = 0
        self.wavelink_version = self._detect_wavelink_version()
        self.preferred_lavalink_version = '4.x'

    def _detect_wavelink_version(self):
        try:
            return float('.'.join(wavelink.__version__.split('.')[:2]))
        except (ValueError, AttributeError):
            return 3.0

    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        return self.session

    async def close_session(self):
        if self.session is not None and not self.session.closed:
            await self.session.close()
        self.session = None

    async def update_server_list(self, force=False):
        # 不載入舊公共節點快取，也不抓取外部伺服器清單。
        self.servers = [LavalinkServer(self.uri, config.LAVALINK_PASSWORD)]
        self.last_fetch_time = time.time()

    async def fetch_server_list(self):
        return list(self.servers)

    async def test_server(self, server, timeout=3):
        if server.uri.rstrip('/') != self.uri:
            return False
        try:
            session = await self._get_session()
            start = time.monotonic()
            async with session.get(
                self.uri + '/v4/info', headers={'Authorization': server.password},
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                if response.status != 200:
                    raise ValueError(f'Lavalink HTTP {response.status}')
                info = await response.json()
                if not isinstance(info, dict) or info.get('version', {}).get('major') != 4:
                    raise ValueError('不是 Lavalink v4 API')
            server.response_time = time.monotonic() - start
            server.version = '4.x'
            server.status = 'online'
            server.error_count = 0
            return True
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, AttributeError, TypeError) as error:
            server.status = 'offline'
            server.error_count += 1
            logger.debug('本機 Lavalink 尚未就緒: %s', error)
            return False
        finally:
            server.last_check = time.time()

    def _get_compatible_servers(self):
        return [server for server in self.servers if server.uri.rstrip('/') == self.uri]

    def _sort_key(self, server):
        return (server.error_count, server.response_time)

    _server_sort_key = _sort_key

    async def get_best_server(self):
        for server in self._get_compatible_servers():
            if await self.test_server(server):
                return server
        return None

    async def get_next_server(self):
        # 舊切換指令現在重新連接同一個本機服務。
        return await self.get_best_server()

    def get_server_status_summary(self):
        counts = {'online': 0, 'offline': 0, 'error': 0, 'unknown': 0}
        for server in self.servers:
            counts[server.status] = counts.get(server.status, 0) + 1
        return {'total': len(self.servers), 'compatible': len(self._get_compatible_servers()),
                'wavelink_version': self.wavelink_version, 'preferred_lavalink_version': '4.x',
                'version_info': {'4.x': len(self.servers)}, 'last_update': self.last_fetch_time,
                'mode': 'local', **counts}


lavalink_manager = LavalinkServerManager()
