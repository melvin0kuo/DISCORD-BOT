import asyncio
from unittest.mock import AsyncMock

import pytest


@pytest.mark.parametrize('primary', [[{'title':'Google店家','url':'https://example.com','snippet':'摘要'}], []])
def test_primary_and_fallback(monkeypatch, primary):
    from utils import web_search as web
    monkeypatch.setattr(web, '_serpapi_search', AsyncMock(return_value=primary))
    backup=AsyncMock(return_value=[{'title':'備援店家','url':'https://example.org','snippet':'摘要'}])
    monkeypatch.setattr(web,'_ddg_search',backup)
    answer=asyncio.run(web.execute_web_search('台北餐廳'))
    assert ('Google店家' if primary else '備援店家') in answer
    assert backup.await_count==(0 if primary else 1)


def test_missing_key_skips_serpapi(monkeypatch):
    from utils import web_search as web
    monkeypatch.setattr(web.config,'SERPAPI_API_KEY','')
    assert asyncio.run(web._serpapi_search('餐廳',5))==[]


def test_quota_cooldown_avoids_requests(monkeypatch):
    from utils import web_search as web
    monkeypatch.setattr(web.config,'SERPAPI_API_KEY','test-key')
    monkeypatch.setattr(web,'_serpapi_blocked_until',float('inf'))
    assert asyncio.run(web._serpapi_search('餐廳',5))==[]


def test_cached_result_does_not_consume_another_request(monkeypatch):
    from utils import web_search as web
    monkeypatch.setattr(web.config,'SERPAPI_API_KEY','test-key')
    monkeypatch.setattr(web,'_serpapi_blocked_until',0)
    monkeypatch.setattr(web,'_serpapi_cache',{})
    request=AsyncMock(return_value=(200,{'organic_results':[{'title':'A','link':'https://example.com','snippet':'B'}]}))
    monkeypatch.setattr(web,'_serpapi_request',request)
    async def run():
        first=await web._serpapi_search('台北咖啡',5)
        second=await web._serpapi_search('台北咖啡',5)
        assert first==second
        assert first[0]['title']=='A'
    asyncio.run(run())
    assert request.await_count==1


@pytest.mark.parametrize('status,data', [(429,{'error':'Quota exceeded'}),(401,{'error':'Invalid key'}),(200,{'error':'No results'}),(500,{})])
def test_api_failures_return_fallback_signal(monkeypatch,status,data):
    from utils import web_search as web
    monkeypatch.setattr(web.config,'SERPAPI_API_KEY','test-key')
    monkeypatch.setattr(web,'_serpapi_blocked_until',0)
    monkeypatch.setattr(web,'_serpapi_cache',{})
    monkeypatch.setattr(web,'_serpapi_request',AsyncMock(return_value=(status,data)))
    assert asyncio.run(web._serpapi_search('測試',5))==[]
    if status in (401,429):
        assert web._serpapi_blocked_until>0
