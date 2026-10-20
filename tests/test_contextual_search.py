import asyncio
import pytest
from unittest.mock import AsyncMock


def test_search_failure_never_tells_model_to_invent_places(monkeypatch):
    from utils import web_search
    monkeypatch.setattr(web_search, '_ddg_search', AsyncMock(return_value=[]))
    result = asyncio.run(web_search.execute_web_search('台北車站 午餐'))
    assert '自身的知識庫' not in result
    assert '不可編造' in result


def test_search_includes_sources_and_currentness_limits(monkeypatch):
    from utils import web_search
    monkeypatch.setattr(web_search, '_ddg_search', AsyncMock(return_value=[
        {'title': '餐廳官方網站', 'url': 'https://example.com/menu', 'snippet': '每日午餐菜單'}]))
    result = asyncio.run(web_search.execute_web_search('台北 午餐'))
    assert 'https://example.com/menu' in result
    assert '查詢時間' in result
    assert '營業' in result


def test_restaurant_policy_requires_search_or_location_question(handler):
    prompt = handler._get_request_system_prompt()
    assert '餐廳' in prompt and 'search_web' in prompt
    assert '地點' in prompt and '先詢問' in prompt
    assert '來源連結' in prompt


def test_empty_query_is_not_sent_to_search(monkeypatch):
    from utils import web_search
    search = AsyncMock(return_value=[])
    monkeypatch.setattr(web_search, '_ddg_search', search)
    result = asyncio.run(web_search.execute_web_search('  '))
    assert '關鍵字' in result
    search.assert_not_awaited()


@pytest.mark.parametrize('question,place_query', [('台北哪裡吃飯', True), ('查Python官方最新更新', False)])
def test_local_search_rounds_finish_with_answer_instead_of_tool_limit_error(handler, monkeypatch, question, place_query):
    calls = []
    async def search(query):
        calls.append(query)
        return '來源：https://example.com/restaurant\n餐廳資訊尚未確認價位。'
    handler.available_functions['search_web'] = search
    async def stream(url, payload, headers, tag=''):
        if payload.get('tool_choice') == 'none':
            assert ('店名' in payload['messages'][-1]['content']) == place_query
            yield ('已查得餐廳資料：https://example.com/restaurant；價位待確認。', None, 'stop')
        else:
            yield ('', [{'index':0,'id':str(len(calls)), 'function':{'name':'search_web','arguments':'{"query":"台北餐廳"}'}}], 'tool_calls')
    monkeypatch.setattr(handler, '_stream_lmstudio_sse', stream)
    handler.add_to_history('1','10','user',question)
    async def run():
        return ''.join([t async for t in handler._get_lmstudio_response_stream('1','10',question)])
    answer = asyncio.run(run())
    assert 'example.com/restaurant' in answer
    assert len(calls) == 3


def test_store_lookup_cannot_answer_without_searching(handler, monkeypatch):
    requests = []
    search = AsyncMock(return_value='來源：https://example.com/store\n地址資料')
    handler.available_functions['search_web'] = search
    async def stream(url, payload, headers, tag=''):
        requests.append(payload)
        if len(requests) == 1:
            yield ('未查證的地址 https://invented.example/', None, 'stop')
        elif len(requests) == 2:
            assert payload['tool_choice'] == 'required'
            assert [t['function']['name'] for t in payload['tools']] == ['search_web']
            yield ('', [{'index':0,'id':'search1','function':{'name':'search_web','arguments':'{"query":"鼎泰豐信義本店 地址 營業時間"}'}}], 'tool_calls')
        else:
            yield ('店家來源：https://example.com/store', None, 'stop')
    monkeypatch.setattr(handler, '_stream_lmstudio_sse', stream)
    async def run():
        return ''.join([t async for t in handler._get_lmstudio_response_stream('1','10','查一下鼎泰豐信義本店的地址與營業時間')])
    answer = asyncio.run(run())
    assert 'invented' not in answer
    assert 'example.com/store' in answer
    search.assert_awaited_once()


def test_location_clarification_does_not_force_search(handler, monkeypatch):
    requests = []
    async def stream(url, payload, headers, tag=''):
        requests.append(payload)
        yield ('請問您在哪個城市或區域呢？', None, 'stop')
    monkeypatch.setattr(handler, '_stream_lmstudio_sse', stream)
    async def run():
        return ''.join([t async for t in handler._get_lmstudio_response_stream('1','10','附近哪裡有餐廳？')])
    assert '城市' in asyncio.run(run())
    assert len(requests) == 1


def test_translation_and_memory_addresses_do_not_force_store_search(handler, monkeypatch):
    calls = []
    async def stream(url, payload, headers, tag=''):
        calls.append(payload)
        yield ('一般問題的回答', None, 'stop')
    monkeypatch.setattr(handler, '_stream_lmstudio_sse', stream)
    async def run():
        for question in ('請幫我翻譯「店家地址在哪」成英文', '指標與記憶體地址是什麼？'):
            answer = ''.join([t async for t in handler._get_lmstudio_response_stream('1','10',question)])
            assert answer == '一般問題的回答'
    asyncio.run(run())
    assert len(calls) == 2
