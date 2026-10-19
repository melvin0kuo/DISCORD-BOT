import asyncio
import importlib
import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import numpy as np
import pytest


def test_memory_survives_restart_and_is_channel_scoped(memory_db):
    _, module = memory_db
    first = module.ConversationMemory()
    first.add_conversation_turn('1', '10', 'hello', 'world')
    first.add_conversation_turn('1', '20', 'private', 'other')
    restarted = module.ConversationMemory()
    assert [t['user_message'] for t in restarted._get_recent_conversations('1', '10', 5)] == ['hello']
    assert restarted._get_recent_conversations('1', '10', 0) == []


def test_cleanup_deletes_persisted_old_turns(memory_db):
    db, module = memory_db
    old = {'timestamp': (datetime.now() - timedelta(days=40)).isoformat(),
           'user_message': 'old', 'ai_response': 'answer', 'turn_id': 'old', 'context': {}}
    db.log_interaction('1', 'conversation_turn', json.dumps(old), {'channel_id': '10'})
    memory = module.ConversationMemory()
    memory.add_conversation_turn('1', '10', 'new', 'answer')
    assert memory.clear_old_conversations('1', '10', 7) == 1
    assert [t['user_message'] for t in module.ConversationMemory()._get_recent_conversations('1', '10', 10)] == ['new']


def test_vector_search_never_duplicates_missing_neighbors(tmp_path):
    from utils.vector_db import VectorDB
    db = VectorDB(str(tmp_path))
    db.add('1', '10', 'one', np.zeros(768, dtype=np.float32))
    assert [r['text'] for r in db.search('1', '10', np.zeros(768), 5)] == ['one']


def test_vector_search_filters_before_top_k(tmp_path):
    from utils.vector_db import VectorDB
    db = VectorDB(str(tmp_path))
    db.add('other', '10', 'other', np.zeros(768, dtype=np.float32))
    db.add('1', '10', 'mine', np.ones(768, dtype=np.float32))
    assert [r['text'] for r in db.search('1', '10', np.zeros(768), 1)] == ['mine']


def test_thinking_tags_split_across_chunks_are_hidden(handler):
    state = [False, '']
    result = ''.join(handler._filter_think_tags(c, state) for c in ['Hi <thi', 'nk>secret</th', 'ink> there'])
    assert result == 'Hi  there'


def test_local_backend_needs_no_gemini_or_local_api_key(handler, monkeypatch):
    module = importlib.import_module('utils.llm_handler')
    monkeypatch.setattr(module.config, 'GEMINI_API_KEY', '')
    monkeypatch.setattr(module.config, 'DEFAULT_LLM_TYPE', 'local')
    local = module.LLMHandler('Duck')
    assert local.get_current_model_info()['type'] == 'lmstudio'


def test_quota_fallback_saves_one_complete_turn(handler, monkeypatch):
    module = importlib.import_module('utils.llm_handler')

    async def quota(*args):
        raise RuntimeError('429 quota exceeded')
        yield

    async def local(*args):
        yield 'local answer'

    monkeypatch.setattr(handler, '_get_gemini_response_stream', quota)
    monkeypatch.setattr(handler, '_get_lmstudio_response_stream', local)
    result = asyncio.run(_collect(handler.get_llm_response_stream('1', '10', 'question')))
    assert result == 'local answer'
    assert handler._get_user_history('1', '10') == [
        {'role': 'user', 'content': 'question'}, {'role': 'assistant', 'content': 'local answer'}]
    assert module.conversation_memory._get_recent_conversations('1', '10', 5)[0]['ai_response'] == 'local answer'


def test_gemini_quota_does_not_retry_forever(handler, monkeypatch):
    import google.generativeai as genai
    chat = SimpleNamespace(send_message_async=AsyncMock(side_effect=RuntimeError('429 quota')))
    monkeypatch.setattr(genai, 'GenerativeModel', lambda **kwargs: SimpleNamespace(start_chat=lambda **kw: chat))
    async def no_sleep(*args):
        raise AssertionError('quota must reach fallback without a retry sleep')
    monkeypatch.setattr(asyncio, 'sleep', no_sleep)
    with pytest.raises(RuntimeError, match='429'):
        asyncio.run(_collect(handler._get_gemini_response_stream('1', '10', 'question')))


async def _collect(stream):
    return ''.join([chunk async for chunk in stream])


def test_stream_pagination_handles_one_huge_chunk(memory_db):
    from cogs.conversation import Conversation
    pages = []
    class Message:
        def __init__(self, text):
            self.content = text
        async def edit(self, *, content, **kwargs):
            assert 0 < len(content) <= 2000
            self.content = content
    class Channel:
        async def send(self, content, **kwargs):
            assert 0 < len(content) <= 2000
            msg = Message(content)
            pages.append(msg)
            return msg
    async def stream():
        yield 'x' * 6000
    result = asyncio.run(Conversation._stream_with_pagination(None, Channel(), stream()))
    assert result == 'x' * 6000
    assert ''.join(p.content for p in pages) == result


def test_reloader_schedules_on_event_loop_thread():
    from utils.reloader import CodeReloader
    import threading
    async def run():
        loop = asyncio.get_running_loop()
        loop.set_debug(True)
        reloader = CodeReloader(SimpleNamespace(), loop)
        errors = []
        def modified():
            try:
                reloader.on_modified(SimpleNamespace(src_path='config.py'))
            except Exception as error:
                errors.append(error)
        thread = threading.Thread(target=modified)
        thread.start()
        thread.join()
        await asyncio.sleep(0)
        if errors:
            pytest.fail(str(errors[0]))
        if reloader.debounce_task:
            reloader.debounce_task.cancel()
            await asyncio.gather(reloader.debounce_task, return_exceptions=True)
        assert errors == []
    asyncio.run(run())


def test_lavalink_rejects_wrong_password():
    from utils.lavalink_manager import LavalinkServerManager, LavalinkServer
    class Response:
        status = 401
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
    manager = LavalinkServerManager()
    manager._get_session = AsyncMock(return_value=SimpleNamespace(get=lambda *a, **kw: Response()))
    server = LavalinkServer('http://localhost:2333', 'wrong')
    assert asyncio.run(manager.test_server(server)) is False
    assert server.status != 'online'


def test_legacy_musicpanel_can_import():
    importlib.import_module('cogs.musicpanel')


def test_startup_import_has_no_torch_dependency(memory_db):
    importlib.import_module('main')


def test_prompt_with_literal_json_braces(handler, monkeypatch):
    module = importlib.import_module('utils.llm_handler')
    monkeypatch.setattr(module.config, 'LLM_SYSTEM_PROMPT', 'Hello {bot_name}: {"key": "value"}')
    assert module.LLMHandler('Duck').system_prompt == 'Hello Duck: {"key": "value"}'


def test_empty_gemini_fallback_does_not_duplicate_user_turn(handler, monkeypatch):
    async def empty(*args):
        if False: yield ''
    async def local(*args):
        yield 'answer'
    monkeypatch.setattr(handler, '_get_gemini_response_stream', empty)
    monkeypatch.setattr(handler, '_get_lmstudio_response_stream', local)
    assert asyncio.run(_collect(handler.get_llm_response_stream('1', '10', 'hello'))) == 'answer'
    assert len(handler._get_user_history('1', '10')) == 2


def test_fallback_disabled_does_not_switch_backend(handler, monkeypatch):
    module = importlib.import_module('utils.llm_handler')
    monkeypatch.setattr(module.config, 'ENABLE_FALLBACK', False)
    async def failed(*args):
        raise RuntimeError('429')
        yield
    monkeypatch.setattr(handler, '_get_gemini_response_stream', failed)
    response = asyncio.run(_collect(handler.get_llm_response_stream('1', '10', 'hello')))
    assert response.startswith('❌')
    assert handler._get_user_history('1', '10') == []


def test_set_memory_preserves_existing_profile(handler, memory_db):
    handler.set_user_memory('1', 'likes coffee')
    assert memory_db[0].get_user_info('1')['display_name'] == 'Alice'


def test_web_scraper_rejects_private_addresses():
    from utils.web_search import fetch_page_content
    from aiohttp import web
    async def run():
        app = web.Application()
        async def secret(request):
            return web.Response(text='private internal service data ' * 10)
        app.router.add_get('/', secret)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            assert await fetch_page_content(f'http://127.0.0.1:{port}') == ''
        finally:
            await runner.cleanup()
    asyncio.run(run())


def test_gemini_executes_streamed_function_calls(handler, monkeypatch):
    from google.generativeai import protos
    requests = []
    async def send_message(message, **kwargs):
        requests.append(message)
        async def response():
            if len(requests) == 1:
                yield SimpleNamespace(parts=[protos.Part(function_call=protos.FunctionCall(name='search_web', args={'query': 'weather'}))])
            else:
                yield SimpleNamespace(parts=[protos.Part(text='Weather result')])
        return response()
    chat = SimpleNamespace(send_message_async=send_message)
    monkeypatch.setattr(handler.gemini_client, 'GenerativeModel', lambda **kw: SimpleNamespace(start_chat=lambda **k: chat))
    handler.available_functions['search_web'] = AsyncMock(return_value='sunny')
    result = asyncio.run(_collect(handler._get_gemini_response_stream('1', '10', 'weather?')))
    assert result == 'Weather result'
    assert requests[1][0].function_response.response['result'] == 'sunny'


def test_all_active_extensions_load_without_network(memory_db, monkeypatch):
    import discord
    from discord.ext import commands
    import config
    monkeypatch.setattr(config, 'GEMINI_API_KEY', '')
    async def run():
        async with commands.Bot(command_prefix='!', intents=discord.Intents.none()) as bot:
            for name in ('conversation', 'music', 'slash_commands', 'user_management', 'conversation_memory_commands'):
                await bot.load_extension('cogs.' + name)
            assert len(bot.cogs) == 5
            assert bot.get_command('play') is not None
            assert bot.tree.get_command('導出對話記憶') is not None
    asyncio.run(run())


def test_lmstudio_load_uses_native_management_api(handler, monkeypatch):
    import config
    from aiohttp import web
    async def run():
        app = web.Application()
        async def load(request):
            assert await request.json() == {'model': 'new-model'}
            assert request.headers['Authorization'] == 'Bearer test-token'
            return web.json_response({'status': 'loaded', 'instance_id': 'new-instance'})
        app.router.add_post('/api/v1/models/load', load)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        monkeypatch.setattr(config, 'LMSTUDIO_API_URL', f'http://127.0.0.1:{port}')
        monkeypatch.setattr(config, 'LMSTUDIO_API_KEY', 'test-token')
        try:
            assert await handler.load_lmstudio_model('new-model') is True
        finally:
            await handler.close()
            await runner.cleanup()
    asyncio.run(run())


def test_attachment_context_is_not_saved_as_user_message(handler, monkeypatch):
    async def gemini(*args):
        yield 'image answer'
    monkeypatch.setattr(handler, '_get_gemini_response_stream', gemini)
    parts = [{'text': 'private context'}, {'inline_data': {'mime_type': 'image/png', 'data': b'png'}}]
    asyncio.run(_collect(handler.get_llm_response_stream('1', '10', parts, user_message='', user_context='private context')))
    assert handler._get_user_history('1', '10') == [
        {'role': 'user', 'content': '[附件]'}, {'role': 'assistant', 'content': 'image answer'}]


def test_explicit_local_model_is_not_replaced_by_first_model(handler, monkeypatch):
    import config
    monkeypatch.setattr(config, 'LMSTUDIO_MODEL', 'configured-chat-model')
    class Response:
        status = 200
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def json(self):
            return {'data': [{'id': 'embedding-model'}, {'id': 'configured-chat-model'}]}
    handler._http_session = SimpleNamespace(closed=False, get=lambda *a, **k: Response())
    assert asyncio.run(handler._get_lmstudio_model_id()) == 'configured-chat-model'
