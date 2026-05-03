"""
Lavalink 伺服器管理器
自動從多個來源抓取公開的 Lavalink 伺服器並實現智能切換
"""

import aiohttp
import asyncio
import logging
import json
import re
import os
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

import wavelink

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    logging.warning("beautifulsoup4 未安裝，將使用正則備用解析")

logger = logging.getLogger(__name__)


@dataclass
class LavalinkServer:
    """Lavalink 伺服器資訊"""
    uri: str
    password: str
    name: str = ""
    region: str = ""
    status: str = "unknown"
    last_check: float = 0
    response_time: float = 0
    error_count: int = 0
    version: str = "unknown"
    ssl: bool = True
    priority: int = 0


class LavalinkServerManager:
    """Lavalink 伺服器管理器"""

    # 已知可用的備用伺服器（按優先順序）
    FALLBACK_SERVERS: List[LavalinkServer] = [
        # 本機伺服器——最高優先，延遲最低，不受 Discord 語音閘道封鎖
        LavalinkServer(
            uri="http://localhost:2333",
            password="youshallnotpass",
            name="Local Lavalink", version="4.x", ssl=False, priority=-1
        ),
        LavalinkServer(
            uri="https://lava-v4.ajieblogs.eu.org:443",
            password="https://dsc.gg/ajidevserver",
            name="AjieDev V4", version="4.x", ssl=True, priority=0
        ),
        LavalinkServer(
            uri="https://lavalinkv4.serenetia.com:443",
            password="https://dsc.gg/ajidevserver",
            name="Serenetia V4", version="4.x", ssl=True, priority=1
        ),
        LavalinkServer(
            uri="https://lava-all.ajieblogs.eu.org:443",
            password="https://dsc.gg/ajidevserver",
            name="AjieDev All", version="4.x", ssl=True, priority=2
        ),
        LavalinkServer(
            uri="https://lavalink4.online:443",
            password="Attack_on_Lavalink",
            name="lavalink4.online", version="4.x", ssl=True, priority=3
        ),
        LavalinkServer(
            uri="http://lavalink.jirayu.net:13592",
            password="youshallnotpass",
            name="Jirayu Lavalink", version="4.x", ssl=False, priority=4
        ),
        LavalinkServer(
            uri="https://lavalink.oops.wtf:443",
            password="www.freelavalink.ga",
            name="Oops Lavalink", version="4.x", ssl=True, priority=5
        ),
        LavalinkServer(
            uri="https://lavalink.devz.cloud:443",
            password="mathiscool",
            name="DevZ Lavalink", version="4.x", ssl=True, priority=6
        ),
    ]

    # 抓取來源（依序嘗試）
    FETCH_SOURCES = [
        {"url": "https://lavalink.darrennathanael.com/SSL/Lavalink-SSL/",    "type": "html", "ssl_servers": True},
        {"url": "https://lavalink.darrennathanael.com/NoSSL/Lavalink-NonSSL/", "type": "html", "ssl_servers": False},
    ]

    def __init__(self):
        self.servers: List[LavalinkServer] = list(self.FALLBACK_SERVERS)
        self.current_server: Optional[LavalinkServer] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache_file = "data/lavalink_servers.json"
        self.last_fetch_time: float = 0
        self.fetch_interval = 3600  # 1 小時
        self.wavelink_version = self._detect_wavelink_version()
        self.preferred_lavalink_version = "4.x" if self.wavelink_version >= 3.0 else "3.x"

    # ──────────────────────── 工具方法 ────────────────────────

    def _detect_wavelink_version(self) -> float:
        try:
            parts = wavelink.__version__.split(".")[:2]
            return float(".".join(parts))
        except Exception:
            return 3.0

    def ensure_data_dir(self):
        os.makedirs("data", exist_ok=True)

    async def _get_session(self) -> aiohttp.ClientSession:
        """取得（或重建）共用 HTTP session，略過 SSL 驗證以相容自簽憑證"""
        if not self.session or self.session.closed:
            connector = aiohttp.TCPConnector(ssl=False)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={"User-Agent": "Mozilla/5.0 Discord Music Bot"}
            )
        return self.session

    async def close_session(self):
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    # ──────────────────────── 抓取伺服器清單 ────────────────────────

    async def fetch_server_list(self) -> List[LavalinkServer]:
        """從所有來源抓取伺服器清單"""
        all_servers: List[LavalinkServer] = []
        session = await self._get_session()

        for source in self.FETCH_SOURCES:
            try:
                servers = await self._fetch_one_source(session, source)
                logger.info(f"📡 {source['url']} → {len(servers)} 個伺服器")
                all_servers.extend(servers)
            except Exception as e:
                logger.warning(f"抓取 {source['url']} 失敗: {e}")

        return all_servers

    async def _fetch_one_source(self, session: aiohttp.ClientSession, source: dict) -> List[LavalinkServer]:
        url = source["url"]
        ssl_servers = source.get("ssl_servers", True)
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.warning(f"HTTP {resp.status} from {url}")
                    return []
                content = await resp.text()
                if source.get("type") == "json":
                    return self._parse_json(content, ssl_servers)
                return self._parse_html(content, ssl_servers)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout: {url}")
            return []

    # ──────────────────────── HTML 解析 ────────────────────────

    # darrennathanael.com 的固定格式:
    #   `Host : hostname  Port : port  Password : "pass"  Secure : true/false`
    _DARREN_RE = re.compile(
        r'Host\s*:\s*(\S+)\s+Port\s*:\s*(\d+)\s+Password\s*:\s*"([^"]+)"\s+Secure\s*:\s*(true|false)',
        re.IGNORECASE,
    )
    # 備用: Password 不帶引號
    _DARREN_RE_NOQUOTE = re.compile(
        r'Host\s*:\s*(\S+)\s+Port\s*:\s*(\d+)\s+Password\s*:\s*(\S+)\s+Secure\s*:\s*(true|false)',
        re.IGNORECASE,
    )

    def _parse_html(self, content: str, ssl: bool) -> List[LavalinkServer]:
        if BS4_AVAILABLE:
            servers = self._parse_html_bs4(content, ssl)
            if servers:
                return servers
        return self._parse_html_regex(content, ssl)

    def _parse_html_bs4(self, content: str, ssl: bool) -> List[LavalinkServer]:
        """使用 BS4 解析 darrennathanael.com 格式的伺服器清單頁面"""
        servers: List[LavalinkServer] = []
        try:
            soup = BeautifulSoup(content, "html.parser")
            current_name = "Unknown"
            current_version = "4.x"  # 該網站主要列的是 v4

            for element in soup.find_all(True):
                tag = element.name
                if not tag:
                    continue

                if tag in ("h1", "h2", "h3", "h4", "h5"):
                    text = element.get_text(" ").strip()
                    # 擷取 "Hosted by @ Name ..." 中的 Name（允許特殊字元如 &）
                    m = re.search(r"@\s*(.+?)(?:\s*\[|\s*\||\s*-|\s*$)", text)
                    if m:
                        current_name = m.group(1).strip()
                    if re.search(r"v4|version\s*4|4\.\d", text, re.I):
                        current_version = "4.x"
                    elif re.search(r"v3|version\s*3|3\.\d", text, re.I):
                        current_version = "3.x"
                    continue

                # 版本也可能出現在普通段落（如 "Version 4.0.8"）
                if tag in ("p", "li", "span", "td"):
                    text = element.get_text(" ").strip()
                    if re.search(r"version\s*4|v4\.\d", text, re.I):
                        current_version = "4.x"
                    elif re.search(r"version\s*3|v3\.\d", text, re.I):
                        current_version = "3.x"
                    continue

                if tag in ("code", "pre"):
                    text = element.get_text(" ").strip()
                    server = self._match_darren_line(text, current_name, current_version)
                    if server:
                        servers.append(server)

        except Exception as e:
            logger.debug(f"BS4 解析失敗: {e}")
        return servers

    def _parse_html_regex(self, content: str, ssl: bool) -> List[LavalinkServer]:
        """無 BS4 時，直接對 HTML 原始碼做正則匹配"""
        servers: List[LavalinkServer] = []
        try:
            current_name = "Unknown"
            current_version = "4.x"
            clean = re.sub(r"<[^>]+>", " ", content)
            for line in clean.splitlines():
                line = line.strip()
                # 從標題行更新名稱
                m = re.search(r"@\s*(.+?)(?:\s*\[|\s*\||\s*-|\s*$)", line)
                if m:
                    current_name = m.group(1).strip()
                if re.search(r"version\s*4|v4\.\d", line, re.I):
                    current_version = "4.x"
                elif re.search(r"version\s*3|v3\.\d", line, re.I):
                    current_version = "3.x"
                server = self._match_darren_line(line, current_name, current_version)
                if server:
                    servers.append(server)
        except Exception as e:
            logger.debug(f"Regex 解析失敗: {e}")
        return servers

    def _match_darren_line(self, text: str, name: str, version: str) -> Optional["LavalinkServer"]:
        """解析 darrennathanael.com 固定格式的一行伺服器資料"""
        m = self._DARREN_RE.search(text) or self._DARREN_RE_NOQUOTE.search(text)
        if not m:
            return None
        host, port_s, password, secure_s = m.group(1), m.group(2), m.group(3), m.group(4)
        secure = secure_s.lower() == "true"
        proto = "https" if secure else "http"
        uri = f"{proto}://{host}:{port_s}"
        return LavalinkServer(
            uri=uri, password=password.strip('"\''),
            name=name, version=version, ssl=secure, priority=10,
        )

    def _parse_json(self, content: str, ssl: bool) -> List[LavalinkServer]:
        servers: List[LavalinkServer] = []
        try:
            data = json.loads(content)
            entries = data if isinstance(data, list) else data.get("servers", data.get("nodes", []))
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                host = entry.get("host", entry.get("uri", ""))
                if not host:
                    continue
                port = entry.get("port", 443)
                password = str(entry.get("password", "youshallnotpass"))
                secure = entry.get("secure", ssl)
                proto = "https" if secure else "http"
                uri = host if "://" in host else f"{proto}://{host}:{port}"
                servers.append(LavalinkServer(
                    uri=uri, password=password,
                    name=entry.get("name", host),
                    region=entry.get("region", "Unknown"),
                    version=entry.get("version", "unknown"),
                    ssl=secure, priority=10
                ))
        except Exception as e:
            logger.debug(f"JSON 解析失敗: {e}")
        return servers

    # ──────────────────────── 伺服器測試 ────────────────────────

    async def test_server(self, server: LavalinkServer, timeout: int = 8) -> bool:
        """測試單一伺服器連通性（略過 SSL 驗證）"""
        try:
            session = await self._get_session()
            start = time.time()
            headers = {"Authorization": server.password}
            # v4 先、v3 後、通用最後
            endpoints = ["/v4/info", "/version", "/info"]

            for endpoint in endpoints:
                url = server.uri.rstrip("/") + endpoint
                try:
                    async with session.get(url, headers=headers,
                                           timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                        server.response_time = time.time() - start
                        server.last_check = time.time()

                        if resp.status in (200, 401):
                            if resp.status == 200:
                                try:
                                    data = await resp.json(content_type=None)
                                    ver = data.get("version", {})
                                    if isinstance(ver, dict):
                                        major = ver.get("major", 0)
                                        server.version = "4.x" if major >= 4 else "3.x"
                                    elif isinstance(ver, str):
                                        server.version = "4.x" if ver.startswith("4.") else "3.x"
                                except Exception:
                                    pass
                            server.status = "online"
                            server.error_count = 0
                            logger.debug(f"✅ {server.name} ({server.version}, {server.response_time:.2f}s)")
                            return True
                except (asyncio.TimeoutError, aiohttp.ClientError):
                    continue

            server.status = "offline"
            server.error_count += 1
            server.last_check = time.time()
            return False

        except Exception as e:
            server.status = "error"
            server.error_count += 1
            server.last_check = time.time()
            logger.debug(f"測試 {server.name} 失敗: {e}")
            return False

    # ──────────────────────── 伺服器選擇 ────────────────────────

    def _get_compatible_servers(self) -> List[LavalinkServer]:
        """篩選與當前 Wavelink 版本相容的伺服器"""
        compatible = []
        for s in self.servers:
            if s.version == "unknown":
                compatible.append(s)
            elif s.version == self.preferred_lavalink_version:
                compatible.append(s)
            elif self.wavelink_version >= 3.0 and s.version == "4.x":
                compatible.append(s)
        return compatible

    def _sort_key(self, server: LavalinkServer) -> tuple:
        ver_score = 0 if server.version == self.preferred_lavalink_version else \
                    1 if server.version in ("3.x", "4.x") else 2
        return (ver_score, server.priority, server.error_count * 10, server.response_time)

    async def get_best_server(self) -> Optional[LavalinkServer]:
        """並行測試候選伺服器，回傳最快/最佳的可用伺服器"""
        if not self.servers:
            await self.update_server_list(force=True)

        candidates = self._get_compatible_servers() or list(self.servers)

        # 只測試需要重新確認的伺服器
        to_test = [s for s in candidates
                   if time.time() - s.last_check > 300 or s.status != "online"]
        if to_test:
            logger.info(f"🔍 並行測試 {len(to_test)} 個候選伺服器...")
            await asyncio.gather(*[self.test_server(s) for s in to_test], return_exceptions=True)

        online = [s for s in candidates if s.status == "online"]

        # 若相容清單沒有可用的，改試全部
        if not online:
            logger.warning("⚠️ 相容伺服器無可用，擴大至全部伺服器...")
            all_to_test = [s for s in self.servers if time.time() - s.last_check > 60]
            if all_to_test:
                await asyncio.gather(*[self.test_server(s) for s in all_to_test], return_exceptions=True)
            online = [s for s in self.servers if s.status == "online"]

        if not online:
            return None

        best = min(online, key=self._sort_key)
        logger.info(f"🎯 最佳伺服器: {best.name} ({best.version}, {best.response_time:.2f}s)")
        return best

    async def get_next_server(self) -> Optional[LavalinkServer]:
        """取得下一個可用伺服器（跳過當前使用中的）"""
        if not self.servers:
            await self.update_server_list(force=True)

        candidates = self._get_compatible_servers() or list(self.servers)
        for server in sorted(candidates, key=self._sort_key):
            if self.current_server and server.uri == self.current_server.uri:
                continue
            if await self.test_server(server):
                self.current_server = server
                logger.info(f"🔄 切換至: {server.name} ({server.version})")
                return server
        return None

    # ──────────────────────── 清單管理 ────────────────────────

    async def update_server_list(self, force: bool = False):
        """更新伺服器清單（快取 + 抓取）"""
        if not force and time.time() - self.last_fetch_time < self.fetch_interval and self.servers:
            return

        logger.info("🔄 正在更新 Lavalink 伺服器清單...")

        await self.load_cached_servers()

        try:
            fetched = await self.fetch_server_list()
        except Exception as e:
            logger.error(f"抓取伺服器清單失敗: {e}")
            fetched = []

        # 合併：備用 + 抓取的，去重
        all_servers = list(self.FALLBACK_SERVERS) + fetched
        seen: set = set()
        unique: List[LavalinkServer] = []
        for s in all_servers:
            if s.uri not in seen:
                seen.add(s.uri)
                unique.append(s)

        self.servers = unique
        self.last_fetch_time = time.time()
        logger.info(f"✅ 伺服器清單更新完成，共 {len(self.servers)} 個")
        await self.save_cached_servers()

    async def load_cached_servers(self):
        try:
            self.ensure_data_dir()
            if not os.path.exists(self.cache_file):
                return
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            cached = [LavalinkServer(**s) for s in data.get("servers", [])]
            if cached:
                # 保留備用伺服器，將快取的加入
                base_uris = {s.uri for s in self.FALLBACK_SERVERS}
                extra = [s for s in cached if s.uri not in base_uris]
                self.servers = list(self.FALLBACK_SERVERS) + extra
                self.last_fetch_time = data.get("last_fetch_time", 0)
                logger.info(f"📂 載入快取: {len(cached)} 個伺服器")
        except Exception as e:
            logger.debug(f"載入快取失敗: {e}")

    async def save_cached_servers(self):
        try:
            self.ensure_data_dir()
            data = {
                "servers": [s.__dict__ for s in self.servers],
                "last_fetch_time": self.last_fetch_time,
            }
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"儲存快取失敗: {e}")

    def get_server_status_summary(self) -> Dict:
        status_count: Dict[str, int] = {"online": 0, "offline": 0, "error": 0, "unknown": 0}
        version_count: Dict[str, int] = {"3.x": 0, "4.x": 0, "unknown": 0}
        for s in self.servers:
            status_count[s.status] = status_count.get(s.status, 0) + 1
            version_count[s.version] = version_count.get(s.version, 0) + 1
        return {
            "total": len(self.servers),
            "compatible": len(self._get_compatible_servers()),
            "wavelink_version": self.wavelink_version,
            "preferred_lavalink_version": self.preferred_lavalink_version,
            **status_count,
            "version_info": version_count,
            "last_update": self.last_fetch_time,
        }


# 全域單例
lavalink_manager = LavalinkServerManager()
