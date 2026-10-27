import asyncio
from unittest.mock import AsyncMock


def test_place_queries_use_maps_but_historical_queries_do_not():
    from utils.place_search import is_place_query
    assert is_place_query('台北車站 拉麵 推薦')
    assert is_place_query('小巷小象 營業時間 菜單')
    assert not is_place_query('2020 年倒閉餐廳 歷史')
    assert not is_place_query('Python 套件更新 新聞')


def test_maps_preserves_closed_and_currently_closed_difference():
    from utils.place_search import maps_results
    rows=maps_results({'local_results':[
        {'title':'永久店','place_id':'p1','open_state':'Permanently closed'},
        {'title':'整修店','place_id':'p2','temporarily_closed':True},
        {'title':'今日休息店','place_id':'p3','open_state':'Closed ⋅ Opens 11 AM','address':'台北市中正區測試路1號'},
    ]},5)
    assert len(rows)==3
    by_name={row['title']:row for row in rows}
    assert by_name['永久店']['excluded'] and by_name['整修店']['excluded']
    assert not by_name['今日休息店']['excluded']
    assert '目前休息' in by_name['今日休息店']['snippet']
    assert '台北市中正區測試路1號' in by_name['今日休息店']['snippet']
    assert 'maps' in rows[0]['url'] and 'api_key' not in str(rows)


def test_all_closed_maps_do_not_fallback_to_old_articles(monkeypatch):
    from utils import web_search as web
    monkeypatch.setattr(web.config,'SERPAPI_API_KEY','test-key')
    monkeypatch.setattr(web,'_serpapi_cache',{})
    monkeypatch.setattr(web,'_serpapi_blocked_until',0)
    monkeypatch.setattr(web,'_serpapi_request',AsyncMock(return_value=(200,{'local_results':[
        {'title':'舊餐廳','place_id':'p1','permanently_closed':True}]})))
    fallback=AsyncMock();monkeypatch.setattr(web,'_ddg_search',fallback)
    answer=asyncio.run(web.execute_web_search('台北餐廳 推薦'))
    assert '不可推薦' in answer
    fallback.assert_not_awaited()


def test_search_results_expose_date_and_unverified_status(monkeypatch):
    from utils import web_search as web
    monkeypatch.setattr(web,'_serpapi_search',AsyncMock(return_value=[
        {'title':'舊食記','url':'https://example.com','snippet':'推薦餐廳','date':'Jan 1, 2020'}]))
    answer=asyncio.run(web.execute_web_search('台北餐廳 推薦'))
    assert 'Jan 1, 2020' in answer
    assert '營業狀態未確認' in answer
