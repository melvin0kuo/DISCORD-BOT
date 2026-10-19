import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import discord
from discord.ext import commands
import pytest


async def make_router():
    from utils.music_intents import MusicIntentRouter

    events = []
    class EnhancedMusic(commands.Cog):
        def __init__(self):
            self.queue_state = SimpleNamespace(shuffle=False)

        def get_queue(self, guild_id):
            return self.queue_state

        @commands.command()
        @commands.cooldown(1, 30, commands.BucketType.user)
        async def play(self, ctx, *, search: str):
            events.append(('play', search, ctx.author.id, ctx.guild.id))

        @commands.command()
        async def volume(self, ctx, vol: int):
            events.append(('volume', vol))

        @commands.command()
        async def pause(self, ctx):
            events.append(('pause', ctx.author.id))

        @commands.command()
        async def shuffle(self, ctx):
            self.queue_state.shuffle = not self.queue_state.shuffle
            events.append(('shuffle', self.queue_state.shuffle))

    bot = commands.Bot(command_prefix='!', intents=discord.Intents.none())
    bot._connection.user = SimpleNamespace(id=999)
    await bot.add_cog(EnhancedMusic())
    channel = SimpleNamespace(id=50)
    guild = SimpleNamespace(id=10, voice_client=None)
    author = SimpleNamespace(id=1, bot=False, voice=SimpleNamespace(channel=channel))
    message = SimpleNamespace(
        id=100, content='<@999> 幫我放周杰倫的晴天', author=author, guild=guild,
        channel=SimpleNamespace(id=20), mentions=[bot.user], attachments=[],
        created_at=datetime.now(timezone.utc), edited_at=None, _state=bot._connection,
    )
    return bot, MusicIntentRouter(bot), message, events


def test_music_tool_requires_guild_voice_and_explicit_mention():
    async def run():
        bot, router, message, _ = await make_router()
        try:
            assert 'control_music' in router.tools_for(message)
            message.mentions = []
            assert router.tools_for(message) == {}
            message.mentions = [bot.user]
            message.author.voice = None
            assert router.tools_for(message) == {}
            message.author.voice = SimpleNamespace(channel=SimpleNamespace(id=50))
            message.guild = None
            assert router.tools_for(message) == {}
        finally:
            await bot.close()
    asyncio.run(run())


@pytest.mark.parametrize('state,reason', [
    ('ready', 'ready'), ('no_voice', 'not_in_voice'),
    ('dm', 'guild_required'), ('no_mention', 'mention_required'),
    ('no_music', 'music_unavailable'),
])
def test_music_context_reports_why_commands_are_unavailable(state, reason):
    async def run():
        bot, router, message, _ = await make_router()
        try:
            if state == 'no_voice': message.author.voice = None
            elif state == 'dm': message.guild = None
            elif state == 'no_mention': message.mentions = []
            elif state == 'no_music': await bot.remove_cog('EnhancedMusic')
            context = router.context_for(message)
            assert context['reason'] == reason
            assert context['available'] is (state == 'ready')
        finally:
            await bot.close()
    asyncio.run(run())


def test_voice_guidance_is_request_scoped_and_does_not_leak_into_other_users(handler, monkeypatch):
    prompts = {}
    async def gemini(user_id, channel_id, message):
        await asyncio.sleep(0)
        prompts[user_id] = handler._get_request_system_prompt()
        yield 'reply'
    monkeypatch.setattr(handler, '_get_gemini_response_stream', gemini)
    async def run():
        async def collect(user_id, instructions):
            return ''.join([chunk async for chunk in handler.get_llm_response_stream(
                user_id, '10', '播放 loser', request_instructions=instructions,
            )])
        await asyncio.gather(collect('1', 'user-one-not-in-voice'), collect('2', 'user-two-in-voice'))
        prompt = handler._get_request_system_prompt()
        assert 'user-one-not-in-voice' not in prompt
        assert 'user-two-in-voice' not in prompt
    asyncio.run(run())
    assert 'user-one-not-in-voice' in prompts['1']
    assert 'user-two-in-voice' not in prompts['1']
    assert 'user-two-in-voice' in prompts['2']
    assert 'user-one-not-in-voice' not in prompts['2']


def test_reloaded_conversation_replaces_cached_music_router(memory_db, monkeypatch):
    import cogs.conversation as conversation
    from cogs.conversation import Conversation
    from utils import music_intents
    class CachedOldRouter:
        def __init__(self, bot): pass
        def tools_for(self, message): return {}
    monkeypatch.setattr(music_intents, 'MusicIntentRouter', CachedOldRouter)
    monkeypatch.setattr(conversation, 'MusicIntentRouter', CachedOldRouter, raising=False)
    bot = SimpleNamespace(user=SimpleNamespace(name='呱呱', id=999), get_cog=lambda name: object())
    cog = Conversation(bot)
    message = SimpleNamespace(guild=SimpleNamespace(id=10),
                              author=SimpleNamespace(voice=None, bot=False), mentions=[bot.user])
    try:
        assert cog.music_intents.context_for(message)['reason'] == 'not_in_voice'
    finally:
        asyncio.run(cog.llm_handler.close())


def test_music_tool_executes_existing_command_once_and_keeps_original_message():
    async def run():
        bot, router, message, events = await make_router()
        try:
            tool = router.tools_for(message)['control_music']['callback']
            result = await tool(action='play', query='周杰倫 晴天')
            assert result['status'] == 'dispatched'
            assert events == [('play', '周杰倫 晴天', 1, 10)]
            assert message.content == '<@999> 幫我放周杰倫的晴天'
            assert await tool(action='play', query='周杰倫 晴天') == result
            await tool(action='play', query='another song')
            assert len(events) == 1
        finally:
            await bot.close()
    asyncio.run(run())


@pytest.mark.parametrize('change', ['left_voice', 'different_voice', 'bot_in_other_voice'])
def test_music_tool_rechecks_voice_state_before_execution(change):
    async def run():
        bot, router, message, events = await make_router()
        try:
            tool = router.tools_for(message)['control_music']['callback']
            if change == 'left_voice':
                message.author.voice = None
            elif change == 'different_voice':
                message.author.voice.channel = SimpleNamespace(id=60)
            else:
                message.guild.voice_client = SimpleNamespace(channel=SimpleNamespace(id=60))
            result = await tool(action='play', query='song')
            assert result['status'] == 'error'
            assert events == []
        finally:
            await bot.close()
    asyncio.run(run())


@pytest.mark.parametrize('arguments', [
    {'action': 'reload_config'}, {'action': 'play', 'query': ''},
    {'action': 'volume', 'volume': 101}, {'action': 'volume', 'volume': True},
    {'action': 'volume', 'volume': '50'}, {'action': 'skip', 'amount': 0},
    {'action': 'loop', 'mode': 'invalid'},
    {'action': 'volume', 'volume': 20, 'volume_delta': -10},
    {'action': 'volume', 'volume_delta': -101},
    {'action': 'shuffle', 'enabled': 'false'},
])
def test_music_tool_validates_model_arguments(arguments):
    async def run():
        bot, router, message, events = await make_router()
        try:
            result = await router.tools_for(message)['control_music']['callback'](**arguments)
            assert result['status'] == 'error'
            assert events == []
        finally:
            await bot.close()
    asyncio.run(run())


def test_music_tool_honors_command_cooldowns():
    async def run():
        bot, router, message, events = await make_router()
        try:
            await router.tools_for(message)['control_music']['callback'](action='play', query='first')
            result = await router.tools_for(message)['control_music']['callback'](action='play', query='second')
            assert result['status'] == 'error'
            assert len(events) == 1
        finally:
            await bot.close()
    asyncio.run(run())


@pytest.mark.parametrize('call_once', [True, False])
def test_music_tool_honors_global_command_checks(call_once):
    async def run():
        bot, router, message, events = await make_router()
        async def reject(ctx): return False
        bot.add_check(reject, call_once=call_once)
        try:
            result = await router.tools_for(message)['control_music']['callback'](action='pause')
            assert result['status'] == 'error'
            assert events == []
        finally:
            await bot.close()
    asyncio.run(run())


def test_music_tool_sets_shuffle_state_without_toggling_it_off_again():
    async def run():
        bot, router, message, events = await make_router()
        try:
            first = await router.tools_for(message)['control_music']['callback'](action='shuffle', enabled=True)
            second = await router.tools_for(message)['control_music']['callback'](action='shuffle', enabled=True)
            assert first['status'] == 'dispatched'
            assert second['status'] == 'unchanged'
            assert bot.get_cog('EnhancedMusic').get_queue(10).shuffle is True
            assert events == [('shuffle', True)]
        finally:
            await bot.close()
    asyncio.run(run())


@pytest.mark.parametrize('current,delta,expected', [(50, -10, 40), (95, 10, 100), (5, -10, 0)])
def test_music_tool_changes_volume_relative_to_current_player(current, delta, expected):
    async def run():
        bot, router, message, events = await make_router()
        message.guild.voice_client = SimpleNamespace(channel=message.author.voice.channel, volume=current)
        try:
            result = await router.tools_for(message)['control_music']['callback'](action='volume', volume_delta=delta)
            assert result['status'] == 'dispatched'
            assert events == [('volume', expected)]
        finally:
            await bot.close()
    asyncio.run(run())


def test_request_tools_are_isolated_between_concurrent_users(handler, monkeypatch):
    seen = {}
    async def gemini(user_id, channel_id, message):
        await asyncio.sleep(0)
        seen[user_id] = await handler._execute_tool('control_music', {'action': 'pause'})
        yield 'done'
    async def own(**kwargs): return 'user one tool'
    monkeypatch.setattr(handler, '_get_gemini_response_stream', gemini)
    async def run():
        async def collect(user_id, tools):
            return ''.join([c async for c in handler.get_llm_response_stream(
                user_id, '10', 'hello', request_tools=tools,
            )])
        await asyncio.gather(
            collect('1', {'control_music': {'callback': own, 'schema': {}}}),
            collect('2', {}),
        )
    asyncio.run(run())
    assert seen['1'] == 'user one tool'
    assert seen['2'] != 'user one tool'


def test_request_tools_are_reset_before_yield_and_generator_can_close_in_another_task(handler, monkeypatch):
    async def gemini(*args):
        yield 'first chunk'
        yield 'second chunk'
    async def own(**kwargs): return 'private music tool'
    monkeypatch.setattr(handler, '_get_gemini_response_stream', gemini)
    async def run():
        stream = handler.get_llm_response_stream('1', '10', 'hello', request_tools={
            'control_music': {'callback': own, 'schema': {}},
        })
        try:
            assert await anext(stream) == 'first chunk'
            assert await handler._execute_tool('control_music', {}) != 'private music tool'
        finally:
            await asyncio.create_task(stream.aclose())
    asyncio.run(run())


@pytest.mark.parametrize('tool_arguments,expected_event', [
    ({'action': 'play', 'query': '周杰倫 晴天'}, ('play', '周杰倫 晴天', 1, 10)),
    ({'action': 'volume', 'volume': 42}, ('volume', 42)),
])
def test_gemini_music_tool_round_trip(handler, monkeypatch, tool_arguments, expected_event):
    from google.generativeai import protos
    import google.generativeai as genai
    import config
    monkeypatch.setattr(config, 'ENABLE_FALLBACK', False)
    original_model = genai.GenerativeModel
    captured = []
    async def run():
        bot, router, message, events = await make_router()
        calls = []
        async def send_message(content, **kwargs):
            calls.append(content)
            async def response():
                if len(calls) == 1:
                    yield SimpleNamespace(parts=[protos.Part(function_call=protos.FunctionCall(
                        name='control_music', args=tool_arguments,
                    ))])
                else:
                    assert calls[-1][0].function_response.response['result']['status'] == 'dispatched'
                    yield SimpleNamespace(parts=[protos.Part(text='已處理點歌請求。')])
            return response()
        def model(**kwargs):
            # 使用真正 SDK 檢查完整工具宣告能轉換成 Gemini schema。
            original_model(**kwargs)
            captured.extend(kwargs['tools'][0]['function_declarations'])
            return SimpleNamespace(start_chat=lambda **kw: SimpleNamespace(send_message_async=send_message))
        monkeypatch.setattr(genai, 'GenerativeModel', model)
        try:
            text = ''.join([c async for c in handler.get_llm_response_stream(
                '1', '10', '幫我放晴天', request_tools=router.tools_for(message),
            )])
            assert text == '已處理點歌請求。'
            assert events == [expected_event]
            assert {s['name'] for s in captured} == {'search_web', 'scrape_web', 'control_music'}
        finally:
            await bot.close()
    asyncio.run(run())


def test_lmstudio_music_tool_round_trip(handler, monkeypatch):
    import json
    from aiohttp import web
    import config
    async def run():
        bot, router, message, events = await make_router()
        requests = []
        async def chat(request):
            body = await request.json()
            requests.append(body)
            assert 'control_music' in [tool['function']['name'] for tool in body['tools']]
            if len(requests) == 1:
                delta = {'tool_calls': [{'index': 0, 'id': 'music-1', 'type': 'function', 'function': {
                    'name': 'control_music', 'arguments': json.dumps({'action': 'play', 'query': '周杰倫 晴天'}),
                }}]}
                reason = 'tool_calls'
            else:
                assert body['messages'][-1]['role'] == 'tool'
                assert json.loads(body['messages'][-1]['content'])['status'] == 'dispatched'
                delta, reason = {'content': '已處理點歌請求。'}, 'stop'
            data = {'choices': [{'index': 0, 'delta': delta, 'finish_reason': reason}]}
            return web.Response(text='data: ' + json.dumps(data) + '\n\ndata: [DONE]\n\n', content_type='text/event-stream')
        app = web.Application()
        app.router.add_post('/v1/chat/completions', chat)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0)
        await site.start()
        monkeypatch.setattr(config, 'LMSTUDIO_API_URL', f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}')
        monkeypatch.setattr(config, 'LMSTUDIO_MODEL', 'test-chat')
        handler.switch_model('local')
        try:
            text = ''.join([c async for c in handler.get_llm_response_stream(
                '1', '10', '幫我放晴天', request_tools=router.tools_for(message),
            )])
            assert text == '已處理點歌請求。'
            assert events == [('play', '周杰倫 晴天', 1, 10)]
            assert len(requests) == 2
        finally:
            await handler.close()
            await runner.cleanup()
            await bot.close()
    asyncio.run(run())
