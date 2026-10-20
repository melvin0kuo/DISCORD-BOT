import asyncio
import json


def test_document_request_prioritizes_file_over_old_conversation(handler, monkeypatch):
    captured = []
    handler.add_to_history('1', '10', 'user', 'OLD-DOCUMENT' * 3000)
    handler.add_to_history('1', '10', 'assistant', 'OLD-ANSWER' * 3000)
    question = '請摘要\n【附件：report.txt】\n' + '文件內容' * 3000
    handler.add_to_history('1', '10', 'user', question)
    async def stream(url, payload, headers, tag=''):
        captured.append(payload)
        yield ('摘要完成', None, 'stop')
    monkeypatch.setattr(handler, '_stream_lmstudio_sse', stream)
    async def run():
        return ''.join([t async for t in handler._get_lmstudio_response_stream('1', '10', question, 'MEMORY' * 3000)])
    assert asyncio.run(run()) == '摘要完成'
    messages = captured[0]['messages']
    assert messages[-1]['content'] == question
    assert 'OLD-DOCUMENT' not in str(messages)
    assert len(messages) == 2
    assert len(messages[0]['content']) < 6000


def test_stream_context_error_is_not_silently_ignored(handler):
    from aiohttp import web
    async def run():
        async def chat(request):
            data = {'error': {'type': 'exceed_context_size_error', 'message': 'request exceeds context size',
                              'n_prompt_tokens': 14436, 'n_ctx': 8192}}
            return web.Response(text='data: ' + json.dumps(data) + '\n\ndata: [DONE]\n\n', content_type='text/event-stream')
        app = web.Application(); app.router.add_post('/chat', chat)
        runner = web.AppRunner(app); await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0); await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            import pytest
            with pytest.raises(RuntimeError, match='上下文'):
                async for _ in handler._stream_lmstudio_sse(f'http://127.0.0.1:{port}/chat', {}, {}):
                    pass
        finally:
            await handler.close(); await runner.cleanup()
    asyncio.run(run())


def test_document_followup_keeps_file_once_and_bounds_memory(handler, monkeypatch):
    captured = []
    document = '【附件：report.txt】\n' + '內容' * 5000
    handler.add_to_history('1', '10', 'user', document)
    handler.add_to_history('1', '10', 'assistant', '文件摘要')
    handler.add_to_history('1', '10', 'user', '再用表格整理')
    async def stream(url, payload, headers, tag=''):
        captured.append(payload)
        yield ('整理完成', None, 'stop')
    monkeypatch.setattr(handler, '_stream_lmstudio_sse', stream)
    monkeypatch.setattr(__import__('config'), 'LMSTUDIO_CONTEXT_LENGTH', 32768)
    async def run():
        return [t async for t in handler._get_lmstudio_response_stream('1', '10', '再用表格整理', '舊記憶' * 10000)]
    asyncio.run(run())
    messages = captured[0]['messages']
    assert sum(m['content'].count('【附件：report.txt】') for m in messages) == 1
    assert len(messages[0]['content']) < 6000
    assert messages[-1]['content'] == '再用表格整理'
