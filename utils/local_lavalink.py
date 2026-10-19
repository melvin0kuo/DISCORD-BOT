"""本機 Lavalink 的可攜式安裝與程序生命週期。"""

import asyncio
import hashlib
import json
import logging
import os
import re
from pathlib import Path
import shutil
import subprocess
import urllib.request
from urllib.parse import urlsplit
import zipfile

import aiohttp
import config

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
LAVALINK_VERSION = '4.2.2'
YOUTUBE_VERSION = '1.18.2'


def extract_runtime(archive, destination):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as zipped:
        for item in zipped.infolist():
            target = (destination / item.filename).resolve()
            if not target.is_relative_to(destination):
                raise ValueError('Java 壓縮檔包含目錄外的路徑')
        zipped.extractall(destination)


def java_is_supported(executable):
    try:
        result = subprocess.run([str(executable), '-version'], capture_output=True, text=True,
                                timeout=10, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        match = re.search(r'version\s+"(\d+)(?:\.(\d+))?', result.stdout + result.stderr)
        if not match or result.returncode != 0:
            return False
        major = int(match[2]) if match[1] == '1' and match[2] else int(match[1])
        return major >= 17
    except (OSError, subprocess.SubprocessError):
        return False


def find_java(root=ROOT):
    root = Path(root)
    portable = sorted((root / '.runtime' / 'java').glob('*/bin/java.exe'))
    candidates = list(reversed(portable))
    if os.environ.get('JAVA_HOME'):
        executable = Path(os.environ['JAVA_HOME']) / 'bin' / ('java.exe' if os.name == 'nt' else 'java')
        if executable.is_file():
            candidates.append(executable)
    system_java = shutil.which('java')
    if system_java:
        candidates.append(system_java)
    return next((str(path) for path in candidates if java_is_supported(path)), None)


def _json_url(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Discord-Bot-Local-Lavalink'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def _download(url, destination, checksum=None):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + '.part')
    request = urllib.request.Request(url, headers={'User-Agent': 'Discord-Bot-Local-Lavalink'})
    with urllib.request.urlopen(request, timeout=120) as source, temporary.open('wb') as output:
        shutil.copyfileobj(source, output)
    if checksum and hashlib.sha256(temporary.read_bytes()).hexdigest() != checksum:
        raise ValueError(f'下載檔案 SHA-256 驗證失敗: {destination.name}')
    temporary.replace(destination)


def install_local_runtime(root=ROOT):
    """只在首次缺少檔案時下載；不安裝系統套件或修改 PATH。"""
    root = Path(root)
    if not find_java(root):
        if os.name != 'nt':
            raise RuntimeError('請先安裝 Java 17 以上，再重新執行啟動腳本')
        release = _json_url('https://api.github.com/repos/adoptium/temurin21-binaries/releases/latest')
        asset = next(item for item in release['assets']
                     if item['name'].startswith('OpenJDK21U-jre_x64_windows_hotspot_') and item['name'].endswith('.zip'))
        checksum = (asset.get('digest') or '').removeprefix('sha256:')
        if not checksum:
            request = urllib.request.Request(asset['browser_download_url'] + '.sha256.txt')
            with urllib.request.urlopen(request, timeout=30) as response:
                checksum = response.read().decode().split()[0]
        archive = root / '.runtime' / asset['name']
        print('下載並驗證可攜式 Java 21...', flush=True)
        _download(asset['browser_download_url'], archive, checksum)
        extract_runtime(archive, root / '.runtime' / 'java')
    jar = root / 'Lavalink' / 'Lavalink.jar'
    if not jar.is_file():
        print('下載 Lavalink...', flush=True)
        _download(f'https://github.com/lavalink-devs/Lavalink/releases/download/{LAVALINK_VERSION}/Lavalink.jar', jar)
    plugin = root / 'Lavalink' / 'plugins-local' / f'youtube-plugin-{YOUTUBE_VERSION}.jar'
    if not plugin.is_file():
        print('下載 YouTube 插件...', flush=True)
        release = _json_url(f'https://api.github.com/repos/lavalink-devs/youtube-source/releases/tags/{YOUTUBE_VERSION}')
        asset = next(item for item in release['assets'] if item['name'] == plugin.name)
        checksum = (asset.get('digest') or '').removeprefix('sha256:') or None
        _download(asset['browser_download_url'], plugin, checksum)
    print('本機 Lavalink 執行環境已就緒。', flush=True)


class LocalLavalinkRuntime:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.process = None
        self._lock = asyncio.Lock()

    async def is_ready(self):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2)) as session:
                async with session.get(config.LAVALINK_URI.rstrip('/') + '/v4/info',
                                       headers={'Authorization': config.LAVALINK_PASSWORD}) as response:
                    if response.status != 200:
                        return False
                    data = await response.json()
                    return isinstance(data, dict) and data.get('version', {}).get('major') == 4
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, TypeError, AttributeError):
            return False

    async def ensure_started(self):
        async with self._lock:
            if await self.is_ready():
                return True
            java = find_java(self.root)
            if not java:
                logger.error('找不到 Java；請先執行 start_with_lavalink.bat 安裝可攜式環境')
                return False
            endpoint = urlsplit(config.LAVALINK_URI)
            if endpoint.hostname not in ('127.0.0.1', 'localhost', '::1'):
                logger.error('本機 Lavalink 必須使用 loopback 網址')
                return False
            if self.process is None or self.process.poll() is not None:
                environment = os.environ.copy()
                environment.update({'SERVER_ADDRESS': endpoint.hostname, 'SERVER_PORT': str(endpoint.port or 2333),
                                    'LAVALINK_SERVER_PASSWORD': config.LAVALINK_PASSWORD})
                log = self.root / 'Lavalink' / 'local-runtime.log'
                with log.open('ab') as output:
                    self.process = subprocess.Popen(
                        [java, '-Xms128m', '-Xmx512m', '-jar', 'Lavalink.jar'],
                        cwd=self.root / 'Lavalink', env=environment, stdout=output, stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                    )
                logger.info('本機 Lavalink 啟動中，PID=%s', self.process.pid)
            deadline = asyncio.get_running_loop().time() + 45
            while asyncio.get_running_loop().time() < deadline:
                if self.process.poll() is not None:
                    break
                if await self.is_ready():
                    logger.info('本機 Lavalink 已就緒: %s', config.LAVALINK_URI)
                    return True
                await asyncio.sleep(0.5)
            logger.error('本機 Lavalink 啟動失敗，請查看 Lavalink/local-runtime.log')
            await self.close()
            return False

    async def close(self):
        # 不終止使用者原先啟動的 Lavalink，只關閉本程序建立的子程序。
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                await asyncio.to_thread(self.process.wait, timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                await asyncio.to_thread(self.process.wait)
        self.process = None


local_lavalink = LocalLavalinkRuntime()
