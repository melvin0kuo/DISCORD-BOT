import time
import discord
from discord.ext import commands
import random
import asyncio
import config
import logging
from utils.llm_handler import LLMHandler
from utils.user_database import user_db

logger = logging.getLogger("discord")

class Conversation(commands.Cog):
    def __init__(self, bot):
        # 向量資料庫實例
        from utils.vector_db import VectorDB
        self.vector_db = VectorDB()
        self.bot = bot
        self.llm_handler = LLMHandler(bot_name=bot.user.name if bot.user else "助手")
        self.greetings = ["你好", "嗨", "哈囉", "安安", "嘿"]
        self.processing_messages = set()  # 防止重複處理同一訊息

    @commands.Cog.listener()
    async def on_ready(self):
        # 強制重新初始化 LLMHandler，確保 gemini_client 屬性存在
        self.llm_handler = LLMHandler(bot_name=self.bot.user.name if self.bot.user else "助手")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        
        # 記錄所有訊息到日誌
        channel_name = getattr(message.channel, 'name', 'DM')
        channel_id = message.channel.id
        logger.info(
            f"[訊息記錄] 用戶: {message.author.display_name}({message.author.id}) | "
            f"頻道: {channel_name}({channel_id}) | "
            f"內容: {message.content}"
        )
        
        if message.content.startswith(config.PREFIX):
            return

        # 防止重複處理同一訊息
        message_key = f"{message.id}_{message.author.id}"
        if message_key in self.processing_messages:
            logger.warning(f"訊息 {message.id} 已在處理中，跳過重複處理")
            return
        
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mentioned = self.bot.user in message.mentions
        is_reply_to_bot = (
            message.reference and
            message.reference.message_id and
            message.reference.cached_message and
            message.reference.cached_message.author == self.bot.user
        )
        
        # 滾動輸入：允許同時多訊息進入佇列，不等待 AI 回應
        if is_dm or is_mentioned or is_reply_to_bot:
            self.processing_messages.add(message_key)
            logger.info(
                f"[互動觸發] 用戶: {message.author}({message.author.id}) | "
                f"頻道: {channel_name}({channel_id}) | "
                f"私訊: {is_dm} | 提及: {is_mentioned} | 回覆: {is_reply_to_bot} | 內容: {message.content}"
            )
            self.bot.loop.create_task(self.handle_conversation(message, is_dm, is_mentioned, is_reply_to_bot, message_key))

    async def _is_prompt_injection(self, msg: str) -> bool:
        """
        使用 LLM 進行智慧型 prompt injection 檢測
        """
        if not msg:
            return False
        return await self.llm_handler.is_prompt_injection_attack(msg)

    async def handle_conversation(self, message, is_dm=False, is_mentioned=False, is_reply_to_bot=False, message_key=None):
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
            
            # 確保用戶在新資料庫中存在
            user_db.add_or_update_user(
                user_id=str(message.author.id),
                username=message.author.name,
                display_name=message.author.display_name
            )
            
            # 記錄用戶互動
            user_db.log_interaction(
                user_id=str(message.author.id),
                interaction_type="message",
                content=content[:200] + "..." if len(content) > 200 else content,
                metadata={
                    "channel_id": str(message.channel.id),
                    "guild_id": str(message.guild.id) if message.guild else None,
                    "is_dm": is_dm,
                    "is_mentioned": is_mentioned,
                    "is_reply": is_reply_to_bot
                }
            )

            async with message.channel.typing():
                try:
                    channel_id = str(message.author.id) if is_dm else str(message.channel.id)
                    logger.info(f"開始處理對話 - 用戶: {message.author.id}, 頻道: {channel_id}")
                    
                    # 偵測訊息中是否有提及其他用戶，獲取他們的完整上下文
                    mentioned_contexts = []
                    for user in message.mentions:
                        if user.id != self.bot.user.id:
                            # 確保被提及的用戶也在資料庫中
                            user_db.add_or_update_user(
                                user_id=str(user.id),
                                username=user.name,
                                display_name=user.display_name
                            )
                            
                            # 獲取完整上下文
                            user_context = self.llm_handler.get_user_full_context(str(user.id), channel_id)
                            if user_context:
                                mentioned_contexts.append(f"【{user.display_name} 的資訊】{user_context}")
                    
                    # 立即發送「思考中」，確保使用者知道機器人已收到訊息
                    sent_message = await message.channel.send("💬 思考中...")

                    # 獲取發送訊息用戶的完整上下文（個人資料、標籤、記憶等）
                    logger.info("正在獲取用戶完整上下文...")
                    user_context = self.llm_handler.get_user_full_context(str(message.author.id), channel_id)
                    logger.info(f"用戶上下文獲取完成，長度: {len(user_context) if user_context else 0}")
                    
                    # 多模態：傳入文字與附件
                    # 先從向量資料庫取得相關前後文
                    logger.info("正在檢索向量資料庫...")
                    vector_context = await self.llm_handler.retrieve_context_from_vector_db(
                        str(message.author.id), channel_id, content, self.vector_db, top_k=3
                    )
                    logger.info(f"向量資料庫檢索完成，context: {bool(vector_context)}")
                    
                    parts = await self.llm_handler.build_gemini_parts(content, message.attachments)
                    
                    # 組合所有上下文資訊
                    context_blocks = []

                    # 1. 用戶個人上下文（最重要，放在最前面）
                    if user_context:
                        context_blocks.append(f"【用戶 {message.author.display_name} 的個人資訊】\n{user_context}")

                    # 2. 向量資料庫相關上下文
                    if vector_context:
                        context_blocks.append(f"【相關歷史對話】\n{vector_context}")

                    # 3. 被提及用戶的上下文
                    if mentioned_contexts:
                        context_blocks.extend(mentioned_contexts)

                    # 4. 頻道最近 20 條訊息（讓 LLM 掌握當前對話脈絡）
                    try:
                        history_lines = []
                        async for msg in message.channel.history(limit=5, before=message):
                            if msg.content.startswith(config.PREFIX):
                                continue
                            text = msg.content or "(附件或嵌入內容)"
                            history_lines.append(f"[{msg.author.display_name}]: {text}")
                        if history_lines:
                            history_lines.reverse()  # 由舊到新
                            context_blocks.append(
                                "【頻道最近訊息記錄（由舊到新）】\n" + "\n".join(history_lines)
                            )
                    except Exception as _hist_err:
                        logger.warning(f"獲取頻道訊息歷史失敗: {_hist_err}")
                    
                    # 將所有上下文插入到 parts 最前面
                    if context_blocks:
                        full_context = "\n\n".join(context_blocks)
                        parts.insert(0, {"text": full_context})
                        logger.info(f"已添加完整上下文，總長度: {len(full_context)}")
                    
                    logger.info("開始生成 LLM 回應...")
                    response_text = await self._stream_with_pagination(
                        message.channel,
                        self.llm_handler.get_llm_response_stream(str(message.author.id), channel_id, parts),
                        initial_msg=sent_message,
                    )
                    logger.info(f"LLM 回應生成完成，長度: {len(response_text)}")

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
                        logger.info("對話處理完成，已發送回應")
                        user_db.log_interaction(
                            user_id=str(message.author.id),
                            interaction_type="ai_response",
                            content=response_text[:200] + "..." if len(response_text) > 200 else response_text,
                            metadata={
                                "channel_id": str(message.channel.id),
                                "response_length": len(response_text)
                            }
                        )
                    else:
                        logger.warning("對話處理完成，但沒有生成回應")
                        await sent_message.edit(content="❌ 抱歉，我無法生成回應。請稍後再試。")
                except Exception as e:
                    logger.error(f"生成回應時出錯: {e}", exc_info=True)
                    try:
                        await message.channel.send(f"抱歉，生成回應時出現錯誤: {str(e)}")
                    except:
                        logger.error("無法發送錯誤訊息")
        except Exception as e:
            logger.error(f"處理對話時出錯: {e}", exc_info=True)
            await message.channel.send(f"❌ 處理訊息時出錯: {str(e)}")
        finally:
            # 處理完成後移除訊息標記
            if message_key and message_key in self.processing_messages:
                self.processing_messages.remove(message_key)

    async def _stream_with_pagination(self, channel, stream_gen, initial_msg=None) -> str:
        """串流 LLM 回應並自動分頁（Discord 單則訊息上限 2000 字元）"""
        LIMIT = 1900  # 留緩衝避免邊界錯誤
        sent_msg = initial_msg or await channel.send("💬 思考中...")
        current_page = ""
        full_response = ""
        last_edit = 0.0

        async for chunk in stream_gen:
            if not chunk:
                continue
            full_response += chunk

            # chunk 本身超長時直接切割
            while len(chunk) > LIMIT:
                piece, chunk = chunk[:LIMIT], chunk[LIMIT:]
                if current_page:
                    await sent_msg.edit(content=current_page)
                sent_msg = await channel.send(piece)
                current_page = piece
                last_edit = time.monotonic()

            if len(current_page) + len(chunk) > LIMIT:
                # 當前頁已滿：定稿並開新訊息
                await sent_msg.edit(content=current_page)
                sent_msg = await channel.send(chunk)
                current_page = chunk
                last_edit = time.monotonic()
            else:
                current_page += chunk
                now = time.monotonic()
                if now - last_edit >= 0.8:
                    try:
                        await sent_msg.edit(content=current_page)
                        last_edit = now
                    except Exception:
                        pass

        if current_page:
            await sent_msg.edit(content=current_page)

        return full_response

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
            
        # 確保用戶在資料庫中存在
        user_db.add_or_update_user(
            user_id=str(ctx.author.id),
            username=ctx.author.name,
            display_name=ctx.author.display_name
        )
        
        # 記錄用戶互動
        user_db.log_interaction(
            user_id=str(ctx.author.id),
            interaction_type="chat_command",
            content=message[:200] + "..." if len(message) > 200 else message,
            metadata={
                "channel_id": str(ctx.channel.id),
                "guild_id": str(ctx.guild.id) if ctx.guild else None
            }
        )
            
        async with ctx.typing():
            try:
                channel_id = str(ctx.author.id) if isinstance(ctx.channel, discord.DMChannel) else str(ctx.channel.id)
                
                # 獲取用戶完整上下文並使用增強的 LLM 回應方法
                user_context = self.llm_handler.get_user_full_context(str(ctx.author.id), channel_id)
                
                # 構建包含上下文的 parts
                parts = [{"text": message}]
                if user_context:
                    parts.insert(0, {"text": f"【用戶 {ctx.author.display_name} 的個人資訊】\n{user_context}"})
                
                response_text = await self._stream_with_pagination(
                    ctx.channel,
                    self.llm_handler.get_llm_response_stream(str(ctx.author.id), channel_id, parts),
                )

                if response_text:
                    # 記錄 AI 回應
                    user_db.log_interaction(
                        user_id=str(ctx.author.id),
                        interaction_type="ai_response",
                        content=response_text[:200] + "..." if len(response_text) > 200 else response_text,
                        metadata={
                            "channel_id": str(ctx.channel.id),
                            "command_triggered": True,
                            "response_length": len(response_text)
                        }
                    )
                else:
                    await ctx.send("❌ 抱歉，我無法生成回應。請稍後再試。")

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
        # 確保用戶在資料庫中存在
        user_db.add_or_update_user(
            user_id=str(ctx.author.id),
            username=ctx.author.name,
            display_name=ctx.author.display_name
        )
        
        # 使用新系統設置記憶
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

    @commands.command(name="switch_model", help="切換 LLM 模型類型 (gemini / local)")
    async def switch_model(self, ctx, model_type: str = None):
        if model_type is None:
            info = self.llm_handler.get_current_model_info()
            await ctx.send(
                f"目前使用: **{info['type']}** (`{info['name']}`)\n"
                f"可切換: `!switch_model gemini` 或 `!switch_model local`"
            )
            return
        try:
            success = self.llm_handler.switch_model(model_type)
            if success:
                info = self.llm_handler.get_current_model_info()
                await ctx.send(f"已切換至 **{info['type']}** (`{info['name']}`)")
            else:
                await ctx.send(
                    f"切換失敗。可用選項: `gemini` / `local`\n"
                    f"（切換至 local 需先在 .env 設定 LMSTUDIO_API_URL 和 LMSTUDIO_API_KEY）"
                )
        except Exception as e:
            logger.error(f"切換模型時出錯: {e}", exc_info=True)
            await ctx.send(f"切換模型時出錯: {str(e)}")

async def setup(bot):
    await bot.add_cog(Conversation(bot))