"""可攜式 YouTube 擷取工具與僅限本機的 cipher 服務。"""

import asyncio
import logging
import os
from pathlib import Path
import subprocess

import aiohttp
import config
from utils.local_lavalink import ROOT, LocalLavalinkRuntime, _download, _json_url, extract_runtime

logger = logging.getLogger(__name__)
DENO_VERSION = 'v2.9.7'
YT_DLP_VERSION = '2026.08.19'
CIPHER_COMMIT = '1e1fd8e2f34ca90cf23545be72e46307bd3d3d2a'
EJS_COMMIT = 'cd4e87f52e87ab6d8b318fd3a817adda6fafa8dc'
CIPHER_URL = 'http://127.0.0.1:8001'


def _install_source(root, repository, commit, destination):
    if destination.is_dir():
        return
    name = repository.split('/')[-1]
    archive = root / '.runtime' / f'{name}-{commit}.zip'
    _download(f'https://github.com/{repository}/archive/{commit}.zip', archive)
    unpacked = root / '.runtime' / f'unpack-{name}-{commit}'
    extract_runtime(archive, unpacked)
    (unpacked / f'{name}-{commit}').rename(destination)


def _release_asset(repository, version, name, target):
    if target.is_file():
        return
    release = _json_url(f'https://api.github.com/repos/{repository}/releases/tags/{version}')
    asset = next(item for item in release['assets'] if item['name'] == name)
    checksum = (asset.get('digest') or '').removeprefix('sha256:')
    if not checksum:
        raise RuntimeError(f'官方 release 沒有提供 SHA-256: {name}')
    _download(asset['browser_download_url'], target, checksum)


def install_youtube_tools(root=ROOT):
    root = Path(root)
    if os.name != 'nt':
        raise RuntimeError('此自動安裝流程適用 Windows')
    deno = root / '.runtime' / 'deno' / 'deno.exe'
    if not deno.is_file():
        archive = root / '.runtime' / 'deno.zip'
        _release_asset('denoland/deno', DENO_VERSION, 'deno-x86_64-pc-windows-msvc.zip', archive)
        extract_runtime(archive, deno.parent)
    _release_asset('yt-dlp/yt-dlp', YT_DLP_VERSION, 'yt-dlp.exe',
                   root / '.runtime' / 'yt-dlp' / 'yt-dlp.exe')
    cipher = root / '.runtime' / 'yt-cipher'
    _install_source(root, 'kikkia/yt-cipher', CIPHER_COMMIT, cipher)
    _install_source(root, 'yt-dlp/ejs', EJS_COMMIT, cipher / 'ejs')
    with (root / '.runtime' / 'youtube-setup.log').open('ab') as output:
        for arguments in (['run', '--allow-read', '--allow-write', 'scripts/patch-ejs.ts'],
                          ['cache', 'server.ts']):
            subprocess.run([str(deno), *arguments], cwd=cipher, check=True, timeout=180,
                           stdout=output, stderr=subprocess.STDOUT,
                           creationflags=subprocess.CREATE_NO_WINDOW)
    print('YouTube cipher 與 yt-dlp 備援工具已就緒。', flush=True)


class LocalCipherRuntime(LocalLavalinkRuntime):
    async def is_ready(self):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2)) as session:
                async with session.get(CIPHER_URL + '/swagger.yaml') as response:
                    return response.status == 200 and 'title: yt-cipher API' in await response.text()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return False

    async def ensure_started(self):
        async with self._lock:
            if await self.is_ready():
                return True
            deno = self.root / '.runtime' / 'deno' / 'deno.exe'
            cipher = self.root / '.runtime' / 'yt-cipher'
            if not deno.is_file() or not (cipher / 'server.ts').is_file():
                logger.error('缺少 YouTube 工具，請先執行 start_with_lavalink.bat')
                return False
            if self.process is None or self.process.poll() is not None:
                allowed = {'SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP', 'USERPROFILE', 'LOCALAPPDATA',
                           'APPDATA', 'HOMEDRIVE', 'HOMEPATH', 'COMSPEC', 'DENO_DIR'}
                environment = {key: value for key, value in os.environ.items() if key.upper() in allowed}
                environment.update(HOST='127.0.0.1', PORT='8001', MAX_THREADS='2', OVERRIDE_PLAYER_VARIANT='IAS')
                with (self.root / '.runtime' / 'youtube-cipher.log').open('ab') as output:
                    self.process = subprocess.Popen(
                        [str(deno), 'run', '--allow-net', '--allow-read', '--allow-write', '--allow-env', 'server.ts'],
                        cwd=cipher, env=environment, stdout=output, stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                    )
            deadline = asyncio.get_running_loop().time() + 30
            while asyncio.get_running_loop().time() < deadline:
                if self.process.poll() is not None:
                    break
                if await self.is_ready():
                    logger.info('YouTube cipher 已就緒: http://127.0.0.1:8001')
                    return True
                await asyncio.sleep(0.5)
            await self.close()
            return False


local_cipher = LocalCipherRuntime()
