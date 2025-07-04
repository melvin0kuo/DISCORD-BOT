import discord
from discord.ext import commands
import random
import asyncio
import config
import logging
from utils.llm_handler import LLMHandler

logger = logging.getLogger("discord")

class Conversation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.llm_handler = LLMHandler(bot_name=bot.user.name if bot.user else "助手")
        self.greetings = ["你好", "嗨", "哈囉", "安安", "嘿"]

    @commands.Cog.listener()
    async def on_ready(self):
        self.llm_handler = LLMHandler(bot_name=self.bot.user.name)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        # 指令交給指令系統
        if message.content.startswith(config.PREFIX):
            return
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mentioned = self.bot.user in message.mentions
        is_reply_to_bot = (
            message.reference and
            message.reference.message_id and
            message.reference.cached_message and
            message.reference.cached_message.author == self.bot.user
        )
        # 記錄互動情境
        logger.info(
            f"[互動觸發] 用戶: {message.author}({message.author.id}) | "
            f"頻道: {getattr(message.channel, 'name', 'DM')}({message.channel.id}) | "
            f"私訊: {is_dm} | 提及: {is_mentioned} | 回覆: {is_reply_to_bot} | 內容: {message.content}"
        )
        # 私訊、被標記、回覆機器人都觸發聊天
        if is_dm or is_mentioned or is_reply_to_bot:
            await self.handle_conversation(message, is_dm, is_mentioned, is_reply_to_bot)

    async def handle_conversation(self, message, is_dm=False, is_mentioned=False, is_reply_to_bot=False):
        try:
            content = message.content
            if is_mentioned:
                content = content.replace(f'<@{self.bot.user.id}>', '').replace(f'<@!{self.bot.user.id}>', '').strip()
            if not content:
                await message.channel.send(f"{random.choice(self.greetings)}，有什麼我能幫你的嗎？")
                return
            logger.info(f"用戶 {message.author.name} ({message.author.id}) 的訊息: {content}")
            async with message.channel.typing():
                try:
                    channel_id = str(message.author.id) if is_dm else str(message.channel.id)
                    response = await self.llm_handler.get_llm_response(str(message.author.id), channel_id, content)
                    if response:
                        if len(response) < 500:
                            await self._send_typing_effect(message.channel, response, message.author, is_dm)
                        else:
                            await self.send_long_message(message.channel, response, message.author, is_dm)
                    else:
                        await message.channel.send("❌ 抱歉，我無法生成回應。請稍後再試。")
                except Exception as e:
                    logger.error(f"生成回應時出錯: {e}", exc_info=True)
                    await message.channel.send(f"抱歉，生成回應時出現錯誤: {str(e)}")
        except Exception as e:
            logger.error(f"處理對話時出錯: {e}", exc_info=True)
            await message.channel.send(f"❌ 處理訊息時出錯: {str(e)}")

    async def _send_typing_effect(self, channel, text, user=None, is_dm=False):
        if len(text) > 1500:
            await self.send_long_message(channel, text, user, is_dm)
        else:
            if not is_dm and user:
                await channel.send(f"{user.mention} {text}")
            else:
                await channel.send(text)

    async def send_long_message(self, channel, content, user=None, is_dm=False):
        max_length = 1800
        if len(content) <= max_length:
            if not is_dm and user:
                await channel.send(f"{user.mention} {content}")
            else:
                await channel.send(content)
        else:
            parts = []
            current_part = ""
            sentences = content.replace('。', '。\n').replace('！', '！\n').replace('？', '？\n').split('\n')
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                test_length = len(current_part) + len(sentence) + 2
                if not is_dm and user:
                    test_length += len(user.mention) + 1
                if test_length <= max_length and current_part:
                    current_part += sentence
                else:
                    if current_part:
                        parts.append(current_part)
                    current_part = sentence
            if current_part:
                parts.append(current_part)
            for i, part in enumerate(parts):
                if not is_dm and user and i == 0:
                    await channel.send(f"{user.mention} {part}")
                else:
                    await channel.send(part)
                if i < len(parts) - 1:
                    await asyncio.sleep(1)

    @commands.command(name="chat", help="與 AI 助手聊天")
    async def chat(self, ctx, *, message: str):
        async with ctx.typing():
            try:
                channel_id = str(ctx.author.id) if isinstance(ctx.channel, discord.DMChannel) else str(ctx.channel.id)
                response = await self.llm_handler.get_llm_response(str(ctx.author.id), channel_id, message)
                is_dm = isinstance(ctx.channel, discord.DMChannel)
                await self.send_long_message(ctx.channel, response, ctx.author, is_dm)
            except Exception as e:
                logger.error(f"聊天命令出錯: {e}", exc_info=True)
                await ctx.send(f"抱歉，生成回應時出現錯誤: {str(e)}")

    @commands.command(name="clear_chat", help="清除與 AI 助手的對話歷史")
    async def clear_chat(self, ctx):
        channel_id = str(ctx.author.id) if isinstance(ctx.channel, discord.DMChannel) else str(ctx.channel.id)
        self.llm_handler.clear_history(str(ctx.author.id), channel_id)
        await ctx.send("已清除您的對話歷史。")

    @commands.command(name="llm_info", help="顯示目前使用的 LLM 模型資訊")
    async def llm_info(self, ctx):
        try:
            model_info = self.llm_handler.get_current_model_info()
            embed = discord.Embed(
                title="LLM 模型資訊",
                description=f"目前使用的 LLM 類型: **{model_info.get('type', '未知')}**",
                color=discord.Color.blue()
            )
            if 'name' in model_info:
                embed.add_field(name="模型", value=model_info['name'], inline=False)
            if 'api_endpoint' in model_info:
                embed.add_field(name="API 端點", value=model_info['api_endpoint'], inline=False)
            embed.add_field(name="對話歷史長度", value=f"每位用戶每頻道最多保存 {getattr(config, 'MAX_HISTORY_LENGTH', 10)} 條消息", inline=False)
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