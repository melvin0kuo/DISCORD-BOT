import asyncio
from utils.context_budget import fit_context


def test_budget_summarizes_history_but_keeps_current_question():
    original=[{'role':'system','content':'rules'},{'role':'user','content':'OLD'*100},{'role':'assistant','content':'OLD'*100},{'role':'user','content':'CURRENT'}]
    async def count(messages): return sum(len(m['content']) for m in messages)
    async def summarize(text): return '過往重點'
    fitted=asyncio.run(fit_context(original,count,summarize,100))
    assert fitted[-1]['content']=='CURRENT'
    assert '過往重點' in str(fitted)
    assert len(original)==4


def test_current_question_is_never_silently_cut():
    import pytest
    async def count(messages): return 1000
    async def summarize(text): return ''
    with pytest.raises(RuntimeError,match='本輪'):
        asyncio.run(fit_context([{'role':'system','content':'rules'},{'role':'user','content':'important'}],count,summarize,100))
