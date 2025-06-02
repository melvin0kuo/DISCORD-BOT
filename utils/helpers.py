import discord
from discord.ext import commands
import logging

# 設定日誌
def setup_logging():
    logger = logging.getLogger('discord')
    logger.setLevel(logging.INFO)
    
    handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    
    logger.addHandler(handler)
    return logger

# 檢查是否為管理員
def is_admin():
    async def predicate(ctx):
        return ctx.author.guild_permissions.administrator
    return commands.check(predicate)

# 創建嵌入訊息
def create_embed(title, description, color=discord.Color.blue()):
    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )
    return embed