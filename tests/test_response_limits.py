import asyncio
import pytest


@pytest.mark.parametrize('question',[
    '製作160個鏡頭，每行25字，主要呱嘎咕喔，不要摘要',
    '寫一篇10000字的故事',
    '輸出1000行print，我要完整複製',
])
def test_oversized_explicit_request_never_calls_model(handler,question):
    async def response(*args):raise AssertionError('must not run');yield ''
    handler._response_stream_locked=response
    async def run():return ''.join([x async for x in handler.get_llm_response_stream('1','10',question)])
    assert '分批' in asyncio.run(run())


def test_document_size_is_not_requested_output_size(handler):
    async def response(*args):yield '摘要內容'
    handler._response_stream_locked=response
    async def run():return ''.join([x async for x in handler.get_llm_response_stream('1','10','請摘要10000字的文件')])
    assert asyncio.run(run())=='摘要內容'


def test_varying_numbered_sound_lines_are_bounded(handler):
    async def response(*args):
        for i in range(120):yield f'{i:03} 呱嘎咕喔 {i*i}\n'
    handler._response_stream_locked=response
    async def run():return ''.join([x async for x in handler.get_llm_response_stream('1','10','鴨子配音字幕')])
    result=asyncio.run(run())
    assert '長度' in result and len(result)<200


def test_normal_and_technical_budgets_differ():
    from utils.response_limits import response_limits
    assert response_limits('講故事')==(4000,80)
    assert response_limits('請分析附件文件並提供摘要')==(8000,160)
