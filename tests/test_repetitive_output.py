import asyncio


def test_repeated_code_lines_are_limited_even_inside_fences():
    from utils.abuse_guard import repetitive_output
    assert repetitive_output('```java\n'+('System.out.println("呱呱");\nThread.sleep(100);\n'*40)+'```')
    assert not repetitive_output('```java\nSystem.out.println("呱呱");\nThread.sleep(100);\n```')


def test_cross_turn_expanded_code_request(tmp_path):
    from utils.abuse_guard import AbuseGuard
    guard=AbuseGuard(tmp_path/'flags.db')
    assert not guard.check('1','10','手動寫多次的print與等待',now=1000).block
    assert guard.check('1','10','1000次 幫我寫出來完整的 我要直接複製',now=1010).block
    assert not guard.check('2','10','1000次 幫我寫出來完整的',now=1010).block
    assert not guard.check('1','11','1000次 幫我寫出來完整的',now=1010).block


def test_output_budget_stops_nonrepetitive_generation(handler):
    async def response(*args):
        yield ''.join(str(i)+' 不同內容\n' for i in range(5000))
    handler._response_stream_locked=response
    async def run():return ''.join([x async for x in handler.get_llm_response_stream('1','10','長文')])
    assert len(asyncio.run(run()))<200


def test_one_active_request_per_user_across_channels(handler):
    async def run():
        entered=asyncio.Event();release=asyncio.Event()
        async def response(*args):
            entered.set();await release.wait();yield '完成'
        handler._response_stream_locked=response
        async def collect(channel):return ''.join([x async for x in handler.get_llm_response_stream('1',channel,'你好')])
        first=asyncio.create_task(collect('10'));await entered.wait()
        assert '上一個請求' in await collect('11')
        release.set();assert await first=='完成'
        assert await collect('11')=='完成'
    asyncio.run(run())


def test_repeated_abuse_enters_cooldown_but_not_permanent_ban(tmp_path):
    from utils.abuse_guard import AbuseGuard
    guard=AbuseGuard(tmp_path/'flags.db')
    for now in (1000,1001,1002):guard.check('1','10','一直重複呱呱不要停',now=now)
    assert guard.check('1','10','你好',now=1003).block
    assert not guard.check('1','10','你好',now=1123).block


def test_timeout_releases_user_slot(handler,monkeypatch):
    async def response(*args):yield '完成'
    handler._response_stream_locked=response
    async def timeout(awaitable,timeout):
        awaitable.close() if hasattr(awaitable,'close') else None
        raise asyncio.TimeoutError
    monkeypatch.setattr(asyncio,'wait_for',timeout)
    async def run():return ''.join([x async for x in handler.get_llm_response_stream('1','10','你好')])
    assert '時間上限' in asyncio.run(run())
    assert not handler._active_users


def test_repetitive_output_never_reaches_discord_boundary(handler):
    async def response(*args):
        yield '嘎嘎！汪汪！喵～'*100
    handler._response_stream_locked=response
    async def run():return ''.join([text async for text in handler.get_llm_response_stream('1','10','展示你的耐力')])
    result=asyncio.run(run())
    assert '停止' in result and len(result)<200


def test_technical_code_and_ordinary_long_answers_are_not_repetition():
    from utils.abuse_guard import repetitive_output
    assert not repetitive_output('正常的文件分析，涵蓋資料、方法、結果與限制。'*5)
    assert not repetitive_output('```python\nsequence="'+'A'*1000+'"\n```')
    assert repetitive_output('呱呱 '*200)


def test_blocked_output_is_not_persisted(handler,monkeypatch):
    from unittest.mock import Mock
    import utils.llm_handler as module
    async def gemini(*args):yield '呱呱 '*200
    monkeypatch.setattr(handler,'_get_gemini_response_stream',gemini)
    record=Mock();monkeypatch.setattr(module.conversation_memory,'add_conversation_turn',record)
    async def run():return ''.join([x async for x in handler.get_llm_response_stream('1','10','展示一下')])
    assert '停止' in asyncio.run(run())
    record.assert_not_called()
    assert not handler._get_user_history('1','10')
