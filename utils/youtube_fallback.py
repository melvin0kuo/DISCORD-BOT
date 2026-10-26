"""只對原 YouTube 影片使用一次 yt-dlp 音訊備援。"""

import asyncio
import copy
import json
import os
import re
import subprocess
from urllib.parse import urlsplit

import aiohttp
import wavelink

from utils.local_lavalink import ROOT


def validate_audio_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or not (parsed.hostname or '').endswith('.googlevideo.com')
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError('備援音訊網址不是受支援的 YouTube CDN')
    return url


async def extract_audio_url(video_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
        raise ValueError('無效的 YouTube 影片識別碼')
    executable = ROOT / '.runtime' / 'yt-dlp' / ('yt-dlp.exe' if os.name == 'nt' else 'yt-dlp')
    deno = ROOT / '.runtime' / 'deno' / ('deno.exe' if os.name == 'nt' else 'deno')
    process = await asyncio.create_subprocess_exec(
        str(executable), '--ignore-config', '--no-playlist', '--skip-download', '--no-warnings',
        '--dump-single-json', '--format', 'bestaudio[protocol=https]', '--socket-timeout', '10',
        '--retries', '1', '--js-runtimes', f'deno:{deno}',
        f'https://www.youtube.com/watch?v={video_id}',
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=45)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        if process.returncode is None:
            process.kill()
        await process.communicate()
        raise
    if process.returncode:
        raise RuntimeError('yt-dlp 無法取得原影片音訊')
    result = json.loads(stdout)
    if result.get('id') != video_id or result.get('vcodec') != 'none':
        raise ValueError('備援結果與原影片不符，或不是純音訊')
    return validate_audio_url(result['url'])


async def resolve_youtube_fallback(original):
    url = await extract_audio_url(original.identifier)
    # 先驗證有實際音訊資料，避免把 HTML 錯誤頁當成成功。
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        async with session.get(url, headers={'Range': 'bytes=0-4095'}) as response:
            if response.status not in (200, 206) or not response.headers.get('Content-Type', '').startswith('audio/'):
                raise RuntimeError('備援音訊串流不可用')
            if not await response.content.read(4096):
                raise RuntimeError('備援音訊內容為空')
            # Lavalink's HTTP reader does not follow every CDN redirect. Pass
            # the validated final URL that actually returned audio bytes.
            url = validate_audio_url(str(response.url))
    from utils.audio_relay import audio_relay
    relay_url = await audio_relay.add(url)
    tracks = await wavelink.Playable.search(relay_url, source=None)
    if not tracks or isinstance(tracks, wavelink.Playlist):
        raise RuntimeError('Lavalink 無法載入備援音訊')
    raw = copy.deepcopy(tracks[0].raw_data)
    raw['info'].update(title=original.title, author=original.author, uri=original.uri,
                       artworkUrl=original.artwork, length=original.length)
    track = wavelink.Playable(raw)
    track.extras = {**dict(original.extras), '_youtube_fallback': True,
                    '_original_title': original.title, '_original_author': original.author}
    return track
