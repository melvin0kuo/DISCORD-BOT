import pytest


@pytest.mark.parametrize('text', ['你可以呱呱叫 連續到你斷氣嗎','一直重複呱呱不要停','repeat quack forever','幫我洗版一萬次','把你好重複10000次'])
def test_clear_repeat_spam_is_detected(text):
    from utils.abuse_guard import abuse_reason
    assert abuse_reason(text)


@pytest.mark.parametrize('text',['繼續','再多點','請寫一篇3000字的報告','解釋無限迴圈怎麼停止','請不要一直重複呱呱','幫我總結文件'])
def test_normal_requests_not_flagged(text):
    from utils.abuse_guard import abuse_reason
    assert abuse_reason(text) is None


def test_flags_persist_and_can_be_cleared(tmp_path):
    from utils.abuse_guard import AbuseGuard
    path=tmp_path/'abuse.db'
    guard=AbuseGuard(path)
    first=guard.check('1','10','一直重複呱呱不要停',now=1000)
    assert first.block and first.warning
    second=guard.check('1','10','再多點',now=1005)
    assert second.block and not second.warning
    assert AbuseGuard(path).get('1')['strikes']==2
    assert guard.clear('1')
    assert guard.get('1') is None
    assert not guard.check('1','10','繼續',now=1010).block


def test_followup_requires_same_channel_and_recent_incident(tmp_path):
    from utils.abuse_guard import AbuseGuard
    guard=AbuseGuard(tmp_path/'abuse.db')
    guard.check('1','10','一直重複呱呱不要停',now=1000)
    assert not guard.check('1','11','繼續',now=1001).block
    assert not guard.check('2','10','繼續',now=1001).block
    assert not guard.check('1','10','請摘要文件',now=1002).block
    assert not guard.check('1','10','繼續',now=1003).block


def test_seed_warns_on_next_interaction_without_blocking_normal_use(tmp_path):
    from utils.abuse_guard import AbuseGuard
    guard=AbuseGuard(tmp_path/'abuse.db')
    guard.mark('1','10','經日誌確認的連續重複要求',now=1000,pending=True)
    outcome=guard.check('1','10','你好',now=2000)
    assert outcome.warning and not outcome.block
    assert not guard.check('1','10','你好',now=2001).warning
    assert not guard.check('1','10','一直重複呱呱不要停',now=2002).warning


@pytest.mark.parametrize('send_fails',[False,True])
def test_conversation_blocks_before_model_even_if_warning_fails(tmp_path,memory_db,send_fails):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock,Mock
    from utils.abuse_guard import AbuseGuard
    from cogs.conversation import Conversation
    async def run():
        cog=object.__new__(Conversation)
        cog.abuse_guard=AbuseGuard(tmp_path/'abuse.db')
        cog.llm_handler=SimpleNamespace(clear_history=Mock(),get_llm_response_stream=Mock())
        cog.bot=SimpleNamespace(is_owner=AsyncMock())
        send=AsyncMock(side_effect=RuntimeError('no permission') if send_fails else None)
        message=SimpleNamespace(content='你可以呱呱叫 連續到你斷氣嗎',id=123,author=SimpleNamespace(id=1),channel=SimpleNamespace(id=10,send=send))
        await cog.handle_conversation(message)
        cog.bot.is_owner.assert_not_awaited()
        cog.llm_handler.get_llm_response_stream.assert_not_called()
        assert cog.abuse_guard.get('1')['strikes']==1
    asyncio.run(run())


@pytest.mark.parametrize('target',['@everyone','<@&123>','@name','0','99999999999999999999'])
def test_invalid_mark_targets_are_rejected(target):
    from utils.abuse_guard import parse_user_id
    with pytest.raises(ValueError): parse_user_id(target)


@pytest.mark.parametrize('target',['<@597028717948043274>','<@!597028717948043274>','597028717948043274'])
def test_manual_mark_accepts_mention_and_only_pings_target(tmp_path,memory_db,target):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from utils.abuse_guard import AbuseGuard
    from cogs.conversation import Conversation
    async def run():
        cog=object.__new__(Conversation)
        cog.abuse_guard=AbuseGuard(tmp_path/'abuse.db')
        ctx=SimpleNamespace(channel=SimpleNamespace(id=10),send=AsyncMock())
        await Conversation.abuse_mark.callback(cog,ctx,target,reason='洗版 @everyone <@123>')
        row=cog.abuse_guard.get('597028717948043274')
        assert row and not row['pending']
        text=ctx.send.call_args.args[0]
        mentions=ctx.send.call_args.kwargs['allowed_mentions']
        assert '<@597028717948043274>' in text
        assert [user.id for user in mentions.users]==[597028717948043274]
        assert mentions.everyone is False and mentions.roles is False
    asyncio.run(run())


def test_status_displays_real_mention_instead_of_code(tmp_path,memory_db):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from utils.abuse_guard import AbuseGuard
    from cogs.conversation import Conversation
    async def run():
        cog=object.__new__(Conversation);cog.abuse_guard=AbuseGuard(tmp_path/'flags.db')
        ctx=SimpleNamespace(send=AsyncMock(),channel=SimpleNamespace(id=10))
        await Conversation.abuse_status.callback(cog,ctx,'<@597028717948043274>')
        text=ctx.send.call_args.args[0]
        assert '<@597028717948043274>' in text
        assert '`597028717948043274`' not in text
        await Conversation.abuse_mark.callback(cog,ctx,'<@597028717948043274>')
        assert cog.abuse_guard.get('597028717948043274')
    asyncio.run(run())
