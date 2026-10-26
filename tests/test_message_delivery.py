import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock


def test_failed_page_edit_is_sent_again_without_losing_text(memory_db):
    from cogs.conversation import Conversation
    async def run():
        cog=object.__new__(Conversation)
        initial=SimpleNamespace(content='',edit=AsyncMock(side_effect=RuntimeError('message deleted')))
        sent=[]
        async def send(content,**kwargs):
            message=SimpleNamespace(content=content)
            async def edit(content,**kwargs): message.content=content
            message.edit=edit; sent.append(message); return message
        channel=SimpleNamespace(send=send)
        async def stream(): yield '完整回答'*1000
        full=await cog._stream_with_pagination(channel,stream(),initial_msg=initial)
        visible=''.join(m.content for m in sent if m.content!='💬 思考中...')
        assert visible==full=='完整回答'*1000
    asyncio.run(run())
