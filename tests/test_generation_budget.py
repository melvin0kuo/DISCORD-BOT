import asyncio


def test_budget_survives_restart_and_is_per_user(tmp_path):
    from utils.generation_budget import GenerationBudget
    path=tmp_path/'usage.db'
    budget=GenerationBudget(path)
    budget.record('1','10',1000,100,15000,'complete')
    allowance=GenerationBudget(path).allowance('1',now=1010)
    assert allowance.characters==1000
    assert allowance.seconds==80
    assert GenerationBudget(path).allowance('2',now=1010).characters==16000
    assert budget.allowance('1',now=1701).characters==16000


def test_request_limit_and_rejection_audit_are_bounded(tmp_path):
    from utils.generation_budget import GenerationBudget
    budget=GenerationBudget(tmp_path/'usage.db')
    for i in range(12):budget.record('1','10',1000+i,1,20,'complete')
    assert budget.allowance('1',now=1020).blocked
    budget.reject('1','11',now=1020)
    budget.reject('1','11',now=1021)
    with budget.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM generation_events').fetchone()[0]==1


def test_hourly_budget_outlives_short_window(tmp_path):
    from utils.generation_budget import GenerationBudget
    budget=GenerationBudget(tmp_path/'usage.db')
    for now in (1000,1700,2400):budget.record('1','10',now,200,15000,'complete')
    assert budget.allowance('1',now=3101).blocked
    assert not budget.allowance('1',now=6001).blocked


def test_exhausted_budget_never_starts_model(handler,tmp_path):
    from utils.generation_budget import GenerationBudget
    import time
    handler._generation_budget=GenerationBudget(tmp_path/'usage.db')
    handler._generation_budget.record('1','10',time.time(),180,0,'timeout')
    async def response(*args):raise AssertionError('model must not run');yield ''
    handler._response_stream_locked=response
    async def run():return ''.join([x async for x in handler.get_llm_response_stream('1','11','你好')])
    assert '累計' in asyncio.run(run())


def test_aborted_output_counts_and_records_event(handler,tmp_path):
    from utils.generation_budget import GenerationBudget
    import time
    handler._generation_budget=GenerationBudget(tmp_path/'usage.db')
    async def response(*args):yield '呱呱 '*200
    handler._response_stream_locked=response
    async def run():return ''.join([x async for x in handler.get_llm_response_stream('1','10','你好')])
    asyncio.run(run())
    assert handler._generation_budget.allowance('1',now=time.time()).characters<16000
    with handler._generation_budget.connect() as db:
        assert db.execute('SELECT reason FROM generation_events').fetchone()[0]=='repetition'
