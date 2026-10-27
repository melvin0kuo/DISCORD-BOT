import asyncio


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
