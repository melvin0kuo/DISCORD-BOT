import asyncio
import json
from unittest.mock import AsyncMock


def test_unexecuted_play_ack_is_retried_before_showing_user(handler, monkeypatch):
    from utils.music_intents import MUSIC_TOOL_SCHEMA
    calls = []
    async def stream(url, payload, headers, tag=''):
        calls.append(payload['messages'][0]['content'])
        if len(calls) == 1:
            yield ('已為您播放歌曲', None, 'stop')
        elif len(calls) == 2:
            yield ('', [{'index': 0, 'id': 'play-1', 'function': {'name': 'control_music',
                          'arguments': json.dumps({'action': 'play', 'query': 'Loser'})}}], 'tool_calls')
        else:
            yield ('已送出播放請求', None, 'stop')
    callback = AsyncMock(return_value={'status': 'dispatched'})
    monkeypatch.setattr(handler, '_stream_lmstudio_sse', stream)
    handler.switch_model('local')
    async def run():
        return ''.join([c async for c in handler.get_llm_response_stream('1', '10', '播放 Loser', request_tools={
            'control_music': {'schema': MUSIC_TOOL_SCHEMA, 'callback': callback}})])
    result = asyncio.run(run())
    assert result == '已送出播放請求'
    callback.assert_awaited_once_with(action='play', query='Loser')


def test_model_cannot_claim_play_without_tool_execution(handler, monkeypatch):
    from utils.music_intents import MUSIC_TOOL_SCHEMA
    async def stream(*args, **kwargs):
        yield ('已為您播放歌曲', None, 'stop')
    callback = AsyncMock()
    monkeypatch.setattr(handler, '_stream_lmstudio_sse', stream)
    handler.switch_model('local')
    async def run():
        return ''.join([c async for c in handler.get_llm_response_stream('1', '10', '播放 Loser', request_tools={
            'control_music': {'schema': MUSIC_TOOL_SCHEMA, 'callback': callback}})])
    result = asyncio.run(run())
    assert '已為您播放' not in result
    callback.assert_not_awaited()


def test_verified_nowplaying_answer_is_not_mistaken_for_action(handler, monkeypatch):
    from utils.music_intents import MUSIC_TOOL_SCHEMA
    count = []
    async def stream(*args, **kwargs):
        count.append(1)
        yield ('正在播放 LOSER', None, 'stop')
    callback = AsyncMock()
    monkeypatch.setattr(handler, '_stream_lmstudio_sse', stream)
    handler.switch_model('local')
    async def run():
        return ''.join([c async for c in handler.get_llm_response_stream('1', '10', '現在播什麼？', request_tools={
            'control_music': {'schema': MUSIC_TOOL_SCHEMA, 'callback': callback,
                              'context': {'current_track': 'LOSER', 'bot_connected': True}}})])
    assert asyncio.run(run()) == '正在播放 LOSER'
    assert len(count) == 1
    callback.assert_not_awaited()
