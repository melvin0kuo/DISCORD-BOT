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
        # 向量資料庫實例
        from utils.vector_db import VectorDB
        self.vector_db = VectorDB()
        self.bot = bot
        self.llm_handler = LLMHandler(bot_name=bot.user.name if bot.user else "助手")
        self.greetings = ["你好", "嗨", "哈囉", "安安", "嘿"]

    @commands.Cog.listener()
    async def on_ready(self):
        # 強制重新初始化 LLMHandler，確保 gemini_client 屬性存在
        self.llm_handler = LLMHandler(bot_name=self.bot.user.name if self.bot.user else "助手")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
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
        logger.info(
            f"[互動觸發] 用戶: {message.author}({message.author.id}) | "
            f"頻道: {getattr(message.channel, 'name', 'DM')}({message.channel.id}) | "
            f"私訊: {is_dm} | 提及: {is_mentioned} | 回覆: {is_reply_to_bot} | 內容: {message.content}"
        )

        # 滾動輸入：允許同時多訊息進入佇列，不等待 AI 回應
        if is_dm or is_mentioned or is_reply_to_bot:
            self.bot.loop.create_task(self.handle_conversation(message, is_dm, is_mentioned, is_reply_to_bot))

    async def _is_prompt_injection(self, msg: str) -> bool:
        """
        使用 LLM 進行智慧型 prompt injection 檢測
        """
        if not msg:
            return False
        return await self.llm_handler.is_prompt_injection_attack(msg)

    async def handle_conversation(self, message, is_dm=False, is_mentioned=False, is_reply_to_bot=False):
        try:
            content = message.content
            if is_mentioned:
                content = content.replace(f'<@{self.bot.user.id}>', '').replace(f'<@!{self.bot.user.id}>', '').strip()

            # --- 基於 LLM 的智慧型 prompt injection 過濾 ---
            if await self._is_prompt_injection(content):
                rejection_response = await self.llm_handler.get_injection_rejection_response(content)
                await message.channel.send(rejection_response)
                return

            if not content and not message.attachments:
                await message.channel.send(f"{random.choice(self.greetings)}，有什麼我能幫你的嗎？")
                return
            logger.info(f"用戶 {message.author.name} ({message.author.id}) 的訊息: {content}")

            # 偵測訊息中是否有提及其他用戶
            mentioned_memories = []
            for user in message.mentions:
                if user.id != self.bot.user.id:
                    mem = self.llm_handler.get_user_memory(str(user.id))
                    if mem:
                        mentioned_memories.append(f"【{user.display_name} 的個人記憶】{mem}")

            async with message.channel.typing():
                try:
                    channel_id = str(message.author.id) if is_dm else str(message.channel.id)
                    # 先送出一則訊息，後續用 edit 更新
                    sent_message = await message.channel.send("💬 思考中...")
                    response_text = ""
                    # 多模態：傳入文字與附件
                    # 先從向量資料庫取得相關前後文
                    context = await self.llm_handler.retrieve_context_from_vector_db(
                        str(message.author.id), channel_id, content, self.vector_db, top_k=3
                    )
                    parts = await self.llm_handler.build_gemini_parts(content, message.attachments)
                    # 將檢索到的 context 與被提及用戶記憶插入 parts 最前面
                    if context or mentioned_memories:
                        context_block = ""
                        if context:
                            context_block += f"【前後文補充】\n{context}\n"
                        if mentioned_memories:
                            context_block += "\n".join(mentioned_memories)
                        parts.insert(0, {"text": context_block})
                    async for chunk in self.llm_handler.get_llm_response_stream(str(message.author.id), channel_id, parts):
                        if chunk:
                            response_text += chunk
                            # 避免太頻繁編輯，僅每 0.5 秒編輯一次
                            if len(response_text) < 50 or len(response_text) % 20 == 0:
                                try:
                                    await sent_message.edit(content=response_text)
                                except Exception:
                                    pass
                    # 最後再編輯一次完整內容
                    # 嘗試自動偵測 Gemini 回應中的 base64 圖片或檔案
                    import re, base64, io
                    img_match = re.search(r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)', response_text)
                    if img_match:
                        img_bytes = base64.b64decode(img_match.group(1))
                        file = discord.File(io.BytesIO(img_bytes), filename="gemini_image.png")
                        await message.channel.send("Gemini 回傳圖片：", file=file)
                    file_match = re.search(r'data:text/plain;base64,([A-Za-z0-9+/=]+)', response_text)
                    if file_match:
                        file_bytes = base64.b64decode(file_match.group(1))
                        file = discord.File(io.BytesIO(file_bytes), filename="gemini_file.txt")
                        await message.channel.send("Gemini 回傳檔案：", file=file)
                    if response_text:
                        await sent_message.edit(content=response_text)
                    else:
                        await sent_message.edit(content="❌ 抱歉，我無法生成回應。請稍後再試。")
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
        if await self._is_prompt_injection(message):
            rejection_response = await self.llm_handler.get_injection_rejection_response(message)
            await ctx.send(rejection_response)
            return
            
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

    @commands.command(name="set_memory", help="設定您的個人記憶（如：!set_memory 我喜歡貓）")
    async def set_memory(self, ctx, *, memory: str):
        self.llm_handler.set_user_memory(str(ctx.author.id), memory)
        await ctx.send(f"已為您設定個人記憶：{memory}")

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