import discord
from discord.ext import commands
import random
import asyncio
import config
import logging
from utils.llm_handler import LLMHandler
        
# 設置日誌
logger = logging.getLogger("discord")

class Conversation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.llm_handler = LLMHandler(bot_name=bot.user.name if bot.user else "助手")
        self.typing_speed = 0.01  # 每個字符的打字延遲（秒）
        self.greetings = ["你好", "嗨", "哈囉", "安安", "嘿"]
        
    @commands.Cog.listener()
    async def on_ready(self):
        # 更新 LLM 處理器中的機器人名稱
        self.llm_handler = LLMHandler(bot_name=self.bot.user.name)
        
    @commands.Cog.listener()
    async def on_message(self, message):
        # 忽略機器人自己的消息和命令
        if message.author == self.bot.user or message.content.startswith('!'):
            return
                
        # 被提及時使用 LLM 回應
        if self.bot.user.mentioned_in(message):
            # 移除提及以獲取純文本內容
            content = message.content.replace(f'<@{self.bot.user.id}>', '').strip()
            
            # 如果沒有實際內容，使用預設問候語
            if not content:
                content = f"{random.choice(self.greetings)}，有什麼我能幫你的嗎？"
                await message.channel.send(content)
                return
            
            # 顯示打字指示器
            async with message.channel.typing():
                try:
                    # 調用 LLM 生成回應
                    response = await self.llm_handler.get_llm_response(str(message.author.id), content)
                
                    # 模擬打字效果（適用於較短回應）
                    if len(response) < 500:  # 只為短回應模擬打字
                        await self._send_typing_effect(message.channel, response)
                    else:
                        await message.channel.send(response)
                except Exception as e:
                    logger.error(f"生成回應時出錯: {e}", exc_info=True)
                    await message.channel.send(f"抱歉，生成回應時出現錯誤: {str(e)}")
                
    async def _send_typing_effect(self, channel, text):
        """模擬打字效果，分段發送較長的消息"""
        # 如果文本太長，分段發送
        if len(text) > 1500:
            parts = []
            current_part = ""
            
            # 按句子分割
            sentences = text.split('. ')
            for sentence in sentences:
                if len(current_part) + len(sentence) + 2 <= 1500:
                    if current_part:
                        current_part += '. ' + sentence
                    else:
                        current_part = sentence
                else:
                    parts.append(current_part + '.')
                    current_part = sentence
            
            if current_part:
                parts.append(current_part)
            
            # 發送每個部分
            for part in parts:
                await channel.send(part)
                await asyncio.sleep(1)  # 部分之間的延遲
        else:
            await channel.send(text)
                
    @commands.command(name="chat", help="與 AI 助手聊天")
    async def chat(self, ctx, *, message: str):
        async with ctx.typing():
            try:
                # 使用正確的方法名稱
                response = await self.llm_handler.get_llm_response(str(ctx.author.id), message)
                await ctx.send(response)
            except Exception as e:
                logger.error(f"聊天命令出錯: {e}", exc_info=True)
                await ctx.send(f"抱歉，生成回應時出現錯誤: {str(e)}")

    @commands.command(name="clear_chat", help="清除與 AI 助手的對話歷史")
    async def clear_chat(self, ctx):
        self.llm_handler.clear_history(str(ctx.author.id))
        await ctx.send("已清除您的對話歷史。")
    
    @commands.command(name="llm_info", help="顯示目前使用的 LLM 模型資訊")
    async def llm_info(self, ctx):
        try:
            # 獲取當前模型信息
            model_info = self.llm_handler.get_current_model_info()
            
            embed = discord.Embed(
                title="LLM 模型資訊",
                description=f"目前使用的 LLM 類型: **{model_info.get('type', '未知')}**",
                color=discord.Color.blue()
            )
            
            # 根據模型類型添加相關信息
            if 'name' in model_info:
                embed.add_field(name="模型", value=model_info['name'], inline=False)
            
            if 'api_endpoint' in model_info:
                embed.add_field(name="API 端點", value=model_info['api_endpoint'], inline=False)
                
            embed.add_field(name="對話歷史長度", value=f"每位用戶最多保存 {config.MAX_HISTORY_LENGTH} 條消息", inline=False)
            
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"獲取模型信息時出錯: {e}", exc_info=True)
            await ctx.send(f"抱歉，獲取模型信息時出現錯誤: {str(e)}")

    @commands.command(name="switch_model", help="切換 LLM 模型類型")
    async def switch_model(self, ctx, model_type: str):
        try:
            success = self.llm_handler.switch_model(model_type)
            if success:
                await ctx.send(f"已切換到 {model_type} 模型。")
            else:
                await ctx.send(f"切換到 {model_type} 模型失敗，請檢查模型類型是否正確。")
        except Exception as e:
            logger.error(f"切換模型時出錯: {e}", exc_info=True)
            await ctx.send(f"切換模型時出錯: {str(e)}")

async def setup(bot):
    await bot.add_cog(Conversation(bot))