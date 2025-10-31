import discord
from discord import app_commands
from discord.ext import commands
import logging
import os
import sys
import random
import asyncio
from typing import Optional, List

# 設置日誌
logger = logging.getLogger('discord')

class SlashCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("斜線指令 cog 已準備就緒")
        
        # 確保斜線指令已同步
        if not self.bot.synced:
            await self.bot.tree.sync()
            logger.info("斜線指令已同步")
            self.bot.synced = True

    # 基本指令
    @app_commands.command(name="ping", description="檢查機器人延遲")
    async def ping(self, interaction: discord.Interaction):
        """檢查機器人延遲"""
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"🏓 Pong! 延遲: {latency}ms")
    
    @app_commands.command(name="roll", description="擲骰子")
    @app_commands.describe(sides="骰子的面數", count="骰子數量")
    async def roll(self, interaction: discord.Interaction, sides: int = 6, count: int = 1):
        """擲骰子"""
        if sides < 1 or count < 1 or count > 10:
            await interaction.response.send_message("❌ 面數必須大於0，且骰子數量必須在1-10之間", ephemeral=True)
            return
            
        results = [random.randint(1, sides) for _ in range(count)]
        total = sum(results)
        
        embed = discord.Embed(
            title="🎲 擲骰子結果",
            description=f"擲出 {count}d{sides}",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="結果", value=f"{results}", inline=False)
        if count > 1:
            embed.add_field(name="總和", value=str(total), inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="random", description="產生隨機數")
    @app_commands.describe(min="最小值", max="最大值")
    async def random_number(self, interaction: discord.Interaction, min: int = 1, max: int = 100):
        """產生隨機數"""
        if min >= max:
            await interaction.response.send_message("❌ 最小值必須小於最大值", ephemeral=True)
            return
            
        number = random.randint(min, max)
        await interaction.response.send_message(f"🔢 隨機數 ({min}-{max}): **{number}**")
    
    @app_commands.command(name="choose", description="從多個選項中選擇一個")
    @app_commands.describe(choices="選項，用逗號分隔")
    async def choose(self, interaction: discord.Interaction, choices: str):
        """從多個選項中選擇一個"""
        options = [option.strip() for option in choices.split(",") if option.strip()]
        
        if not options:
            await interaction.response.send_message("❌ 請提供至少一個選項", ephemeral=True)
            return
        
        if len(options) == 1:
            await interaction.response.send_message(f"🤔 只有一個選項：**{options[0]}**")
            return
            
        chosen = random.choice(options)
        
        embed = discord.Embed(
            title="🎯 選擇結果",
            description=f"我選擇了：**{chosen}**",
            color=discord.Color.green()
        )
        
        embed.add_field(name="所有選項", value="\n".join(f"• {option}" for option in options), inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="poll", description="創建一個投票")
    @app_commands.describe(
        question="投票問題",
        options="選項，用逗號分隔 (最多10個)",
        time="投票時間（分鐘，預設5分鐘）"
    )
    async def poll(self, interaction: discord.Interaction, question: str, options: str, time: int = 5):
        """創建一個投票"""
        option_list = [option.strip() for option in options.split(",") if option.strip()]
        
        if not option_list:
            await interaction.response.send_message("❌ 請提供至少一個選項", ephemeral=True)
            return
            
        if len(option_list) > 10:
            await interaction.response.send_message("❌ 最多只能有10個選項", ephemeral=True)
            return
            
        if time < 1 or time > 60:
            await interaction.response.send_message("❌ 投票時間必須在1-60分鐘之間", ephemeral=True)
            return
        
        # 創建投票嵌入
        embed = discord.Embed(
            title=f"📊 投票：{question}",
            description="請點擊下方的反應來投票！",
            color=discord.Color.blue(),
            timestamp=interaction.created_at
        )
        
        # 使用表情符號作為選項
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        
        for i, option in enumerate(option_list):
            embed.add_field(name=f"{emojis[i]} 選項 {i+1}", value=option, inline=False)
        
        embed.set_footer(text=f"投票將在 {time} 分鐘後結束 • 由 {interaction.user.display_name} 發起")
        
        await interaction.response.send_message("📊 投票已創建！", embed=embed)
        message = await interaction.original_response()
        
        # 添加反應
        for i in range(len(option_list)):
            await message.add_reaction(emojis[i])
        
        # 等待投票結束
        await asyncio.sleep(time * 60)
        
        # 獲取最新的消息（包含反應）
        message = await interaction.channel.fetch_message(message.id)
        
        # 計算結果
        results = []
        for i, emoji in enumerate(emojis[:len(option_list)]):
            reaction = discord.utils.get(message.reactions, emoji=emoji)
            count = reaction.count - 1  # 減去機器人的反應
            results.append((option_list[i], count))
        
        # 創建結果嵌入
        result_embed = discord.Embed(
            title=f"📊 投票結果：{question}",
            color=discord.Color.gold(),
            timestamp=interaction.created_at
        )
        
        # 排序結果
        results.sort(key=lambda x: x[1], reverse=True)
        
        for i, (option, count) in enumerate(results):
            result_embed.add_field(name=f"{emojis[i]} {option}", value=f"{count} 票", inline=False)
        
        result_embed.set_footer(text=f"投票已結束 • 由 {interaction.user.display_name} 發起")
        
        await interaction.followup.send("📊 投票結果出爐！", embed=result_embed)
    
    @app_commands.command(name="userinfo", description="顯示用戶資訊")
    @app_commands.describe(user="要查詢的用戶（預設為自己）")
    async def userinfo(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """顯示用戶資訊"""
        target = user or interaction.user
        
        embed = discord.Embed(
            title=f"👤 用戶資訊: {target.display_name}",
            color=target.color
        )
        
        embed.set_thumbnail(url=target.display_avatar.url)
        
        embed.add_field(name="用戶名", value=str(target), inline=True)
        embed.add_field(name="ID", value=target.id, inline=True)
        embed.add_field(name="創建日期", value=target.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        
        if isinstance(target, discord.Member):
            embed.add_field(name="加入伺服器日期", value=target.joined_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
            embed.add_field(name="最高身分組", value=target.top_role.mention, inline=True)
            embed.add_field(name="身分組數量", value=len(target.roles) - 1, inline=True)  # 減去 @everyone
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="serverinfo", description="顯示伺服器資訊")
    async def serverinfo(self, interaction: discord.Interaction):
        """顯示伺服器資訊"""
        guild = interaction.guild
        
        embed = discord.Embed(
            title=f"ℹ️ 伺服器資訊: {guild.name}",
            color=discord.Color.blue()
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        # 基本資訊
        embed.add_field(name="ID", value=guild.id, inline=True)
        embed.add_field(name="擁有者", value=f"<@{guild.owner_id}>", inline=True)
        embed.add_field(name="創建日期", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        
        # 成員統計
        member_count = guild.member_count
        bot_count = len([m for m in guild.members if m.bot])
        human_count = member_count - bot_count
        
        embed.add_field(name="成員總數", value=member_count, inline=True)
        embed.add_field(name="人類", value=human_count, inline=True)
        embed.add_field(name="機器人", value=bot_count, inline=True)
        
        # 頻道統計
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        
        embed.add_field(name="文字頻道", value=text_channels, inline=True)
        embed.add_field(name="語音頻道", value=voice_channels, inline=True)
        embed.add_field(name="類別", value=categories, inline=True)
        
        # 其他資訊
        embed.add_field(name="表情符號數量", value=len(guild.emojis), inline=True)
        embed.add_field(name="身分組數量", value=len(guild.roles), inline=True)
        embed.add_field(name="加成等級", value=guild.premium_tier, inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="avatar", description="顯示用戶頭像")
    @app_commands.describe(user="要查看頭像的用戶（預設為自己）")
    async def avatar(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """顯示用戶頭像"""
        target = user or interaction.user
        
        embed = discord.Embed(
            title=f"{target.display_name} 的頭像",
            color=discord.Color.blue()
        )
        
        embed.set_image(url=target.display_avatar.url)
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(SlashCommands(bot))