import asyncio


def test_length_limit_continues_without_tools_or_duplicate_prefix(handler, monkeypatch):
    calls = []
    async def stream(url, payload, headers, tag=''):
        calls.append(payload)
        if len(calls) == 1:
            yield ('第一段', None, None)
            yield ('', None, 'length')
        else:
            yield ('第二段', None, 'stop')
    monkeypatch.setattr(handler, '_stream_lmstudio_sse', stream)
    original = [{'role': 'user', 'content': '寫一篇文章'}]
    payload = {'messages': original, 'tools': [{'type': 'function'}], 'tool_choice': 'auto'}
    async def run():
        return ''.join([t async for t, _, _ in handler._stream_lmstudio_continued('', payload, {})])
    assert asyncio.run(run()) == '第一段第二段'
    assert len(calls) == 2
    assert calls[1]['tool_choice'] == 'none'
    assert 'tools' not in calls[1]
    assert calls[1]['messages'][-2]['content'] == '第一段'
    assert original == [{'role': 'user', 'content': '寫一篇文章'}]


def test_normal_stop_does_not_continue(handler, monkeypatch):
    calls = []
    async def stream(*args, **kwargs):
        calls.append(1)
        yield ('完成', None, 'stop')
    monkeypatch.setattr(handler, '_stream_lmstudio_sse', stream)
    async def run():
        return [event async for event in handler._stream_lmstudio_continued('', {'messages': []}, {})]
    assert asyncio.run(run()) == [('完成', None, 'stop')]
    assert len(calls) == 1


def test_repeated_length_is_bounded_and_explained(handler, monkeypatch):
    calls = []
    async def stream(*args, **kwargs):
        calls.append(1)
        yield ('長文', None, 'length')
    monkeypatch.setattr(handler, '_stream_lmstudio_sse', stream)
    async def run():
        return ''.join([t async for t, _, _ in handler._stream_lmstudio_continued('', {'messages': []}, {})])
    result = asyncio.run(run())
    assert len(calls) == 3
    assert '繼續' in result


def test_truncated_tool_call_is_never_continued_as_text(handler, monkeypatch):
    calls = []
    async def stream(*args, **kwargs):
        calls.append(1)
        yield ('', [{'index': 0, 'function': {'arguments': '{'}}], 'length')
    monkeypatch.setattr(handler, '_stream_lmstudio_sse', stream)
    async def run():
        return [event async for event in handler._stream_lmstudio_continued('', {'messages': []}, {})]
    import pytest
    with pytest.raises(RuntimeError, match='工具'):
        asyncio.run(run())
    assert len(calls) == 1


def test_continuation_context_overflow_retries_without_old_history(handler, monkeypatch):
    calls = []
    async def stream(url, payload, headers, tag=''):
        calls.append(payload)
        if len(calls) == 1:
            yield ('第一段', None, 'length')
        elif len(calls) == 2:
            raise RuntimeError('LM Studio HTTP 400')
        else:
            yield ('後續', None, 'stop')
    monkeypatch.setattr(handler, '_stream_lmstudio_sse', stream)
    payload = {'messages': [{'role': 'system', 'content': 'instructions'},
                            {'role': 'user', 'content': 'old'},
                            {'role': 'assistant', 'content': 'old answer'},
                            {'role': 'user', 'content': 'current question'}]}
    async def run():
        return ''.join([t async for t, _, _ in handler._stream_lmstudio_continued('', payload, {})])
    assert asyncio.run(run()) == '第一段後續'
    assert len(calls) == 3
    assert 'old' not in str(calls[-1]['messages'])
    assert calls[-1]['messages'][1]['content'] == 'current question'
    assert calls[-1]['max_tokens'] == 512


def test_continuation_cannot_inject_a_tool_call(handler, monkeypatch):
    calls = []
    async def stream(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            yield ('第一段', None, 'length')
        else:
            yield ('', [{'index': 0, 'function': {'name': 'control_music', 'arguments': '{}'}}], 'tool_calls')
    monkeypatch.setattr(handler, '_stream_lmstudio_sse', stream)
    async def run():
        return [event async for event in handler._stream_lmstudio_continued('', {'messages': []}, {})]
    import pytest
    with pytest.raises(RuntimeError, match='不允許執行工具'):
        asyncio.run(run())
