import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from discord.ext import commands


@pytest.mark.parametrize('path,name',[
    ('main.py','config_status_command'),('main.py','list_models'),
    ('cogs/conversation.py','switch_model'),('cogs/conversation.py','llm_info'),
])
@pytest.mark.parametrize('owner',[False,True])
def test_sensitive_commands_verify_discord_owner(path,name,owner):
    root=Path(__file__).resolve().parents[1]
    tree=ast.parse((root/path).read_text(encoding='utf-8-sig'))
    node=next(n for n in ast.walk(tree) if isinstance(n,ast.AsyncFunctionDef) and n.name==name)
    bot=SimpleNamespace(command=commands.command,is_owner=AsyncMock(return_value=owner))
    namespace={'bot':bot,'commands':commands}
    exec(compile(ast.Module(body=[node],type_ignores=[]),path,'exec'),namespace)
    command=namespace[name]
    assert command.checks,'Sensitive command must have a permission check'
    ctx=SimpleNamespace(bot=bot,author=SimpleNamespace(id=1))
    async def run():
        if owner:
            for check in command.checks:assert await check(ctx)
        else:
            with pytest.raises(commands.NotOwner):
                for check in command.checks:await check(ctx)
    asyncio.run(run())
    bot.is_owner.assert_awaited_once_with(ctx.author)
