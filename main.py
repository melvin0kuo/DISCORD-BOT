import discord
from discord.ext import commands
import asyncio
import os
import logging
import importlib
import sys
from dotenv import load_dotenv

# 重新配置編碼
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# 導入配置和工具
import config
from utils.helpers import setup_logging
from utils.gpu_monitor import GPUMonitor
from utils.model_loader import ModelLoader
from utils.reloader import setup_reloader

# 設置日誌
logger = setup_logging()

class EnhancedBot(commands.Bot):
    def __init__(self):
        # 設置意圖
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(
            command_prefix=config.PREFIX, 
            intents=intents, 
            help_command=None
        )
        
        # 配置相關屬性
        self.config_loaded = False
        self.llm_handler = None
        
    async def reload_config(self):
        """重新載入配置"""
        try:
            logger.info("🔄 開始重新載入配置...")

            # 確保專案根目錄在 sys.path
            import sys, os
            project_root = os.path.abspath(os.path.dirname(__file__))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)

            # 1. 重新載入 .env 檔案
            if os.path.exists('.env'):
                load_dotenv('.env', override=True)
                logger.info("📂 .env 檔案重新載入完成")
            
            # 2. 重新載入 config 模組
            importlib.reload(config)
            logger.info("⚙️ config 模組重新載入完成")
            
            # 3. 重新載入相關工具模組
            if 'utils.helpers' in sys.modules:
                importlib.reload(sys.modules['utils.helpers'])
                logger.info("🔧 helpers 模組重新載入完成")
            
            if 'llm_handler' in sys.modules:
                importlib.reload(sys.modules['llm_handler'])
                logger.info("🤖 LLM Handler 模組重新載入完成")
            
            # 4. 重新初始化 LLM Handler（如果存在 conversation cog）
            conversation_cog = self.get_cog('Conversation')
            if conversation_cog and hasattr(conversation_cog, 'llm_handler'):
                from utils.llm_handler import LLMHandler
                conversation_cog.llm_handler = LLMHandler(self.user.name if self.user else "Discord Bot")
                logger.info("🔄 LLM Handler 重新初始化完成")
            
            # 5. 更新 bot 前綴（如果改變了）
            self.command_prefix = config.PREFIX
            
            # 6. 重新設置日誌等級
            if hasattr(config, 'LOG_LEVEL'):
                logging.getLogger().setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
            
            self.config_loaded = True
            logger.info("✅ 配置重新載入完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 重新載入配置時出錯: {e}", exc_info=True)
            return False
    
    def get_config_summary(self):
        """獲取配置摘要"""
        summary = {
            "prefix": getattr(config, 'PREFIX', '!'),
            "token_set": bool(getattr(config, 'TOKEN', None)),
            "gemini_key_set": bool(getattr(config, 'GEMINI_API_KEY', None)),
            "openai_key_set": bool(getattr(config, 'OPENAI_API_KEY', None)),
            "anthropic_key_set": bool(getattr(config, 'ANTHROPIC_API_KEY', None)),
            "log_level": getattr(config, 'LOG_LEVEL', 'INFO'),
            "max_history": getattr(config, 'MAX_HISTORY_LENGTH', 20),
            "performance_logging": getattr(config, 'ENABLE_PERFORMANCE_LOGGING', False),
        }
        
        # 檢查模型相關配置
        if hasattr(config, 'GEMINI_MODEL'):
            summary["gemini_model"] = config.GEMINI_MODEL
        if hasattr(config, 'OPENAI_MODEL'):
            summary["openai_model"] = config.OPENAI_MODEL
        if hasattr(config, 'ANTHROPIC_MODEL'):
            summary["anthropic_model"] = config.ANTHROPIC_MODEL
            
        return summary

# 創建機器人實例
bot = EnhancedBot()

@bot.event
async def on_ready():
    logger.info(f"機器人已登入為: {bot.user.name}")
    logger.info(f"機器人 ID: {bot.user.id}")
    logger.info(f"Discord.py 版本: {discord.__version__}")
    
    # 同步斜線指令到 Discord
    try:
        # 先同步全域指令
        slash_commands = await bot.tree.sync()
        logger.info(f"✅ 全域斜線指令同步完成: {len(slash_commands)} 個")
        
        # 顯示已同步的指令清單
        if slash_commands:
            command_names = [cmd.name for cmd in slash_commands]
            logger.info(f"📋 已同步的斜線指令: {', '.join(command_names)}")
        else:
            logger.warning("⚠️ 沒有找到任何斜線指令")
            
    except Exception as e:
        logger.error(f"❌ 同步斜線指令失敗: {e}")
        # 嘗試清除並重新同步
        try:
            logger.info("🔄 嘗試清除並重新同步斜線指令...")
            bot.tree.clear_commands(guild=None)
            slash_commands = await bot.tree.sync()
            logger.info(f"✅ 重新同步完成: {len(slash_commands)} 個斜線指令")
        except Exception as retry_e:
            logger.error(f"❌ 重新同步也失敗了: {retry_e}")
    
    # 設置機器人狀態
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{config.PREFIX}help | 提及我來聊天"
        )
    )
    
    # 如果啟用了性能監控，啟動 GPU 監控
    if config.ENABLE_PERFORMANCE_LOGGING and hasattr(config, "LOCAL_MODEL_DEVICE") and config.LOCAL_MODEL_DEVICE == "cuda":
        gpu_monitor = GPUMonitor.get_instance()
        gpu_monitor.start_monitoring(interval=60)  # 每分鐘記錄一次
    
    # 顯示配置摘要
    summary = bot.get_config_summary()
    logger.info(f"當前配置摘要: {summary}")
    
    bot.config_loaded = True
    logger.info("機器人已準備就緒!")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return

    # 取得原始錯誤
    original_error = getattr(error, 'original', error)

    # 準備錯誤訊息
    if isinstance(error, commands.MissingRequiredArgument):
        message = f"❌ 缺少必要參數: {error.param.name}"
    elif isinstance(error, commands.BadArgument):
        message = f"❌ 參數類型錯誤: {error}"
    elif isinstance(error, commands.NotOwner):
        message = "❌ 此命令僅限機器人擁有者使用"
    elif isinstance(original_error, discord.errors.NotFound) and original_error.code == 10062:
        # 處理 "Unknown Interaction" 錯誤，通常是因為 defer() 後續處理太久
        logger.warning(f"命令 '{ctx.command}' 的互動已過期。可能是處理時間過長。")
        message = "⏳ 處理時間過長，請稍後再試。"
    else:
        logger.error(f"執行命令 '{ctx.command}' 時發生未處理的錯誤", exc_info=error)
        message = f"❌ 執行命令時發生未知錯誤。"

    try:
        # 檢查是否是斜線指令的互動
        if ctx.interaction:
            # 斜線指令錯誤處理
            if ctx.interaction.response.is_done():
                await ctx.followup.send(message, ephemeral=True)
            else:
                await ctx.send(message, ephemeral=True)
        else:
            # 傳統指令錯誤處理
            await ctx.send(message)
    except discord.errors.HTTPException as e:
        # 備用方案，以防萬一
        logger.error(f"在 on_command_error 中發送錯誤訊息失敗: {e}")
    except Exception as e:
        # 處理其他可能的錯誤
        logger.error(f"處理錯誤訊息時出現異常: {e}")

@bot.command(name="reload_config")
@commands.is_owner()
async def reload_config_command(ctx):
    """重新載入配置（僅限機器人擁有者）"""
    msg = await ctx.send("🔄 正在重新載入配置...")
    
    success = await bot.reload_config()
    
    if success:
        # 更新機器人狀態
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening, 
                name=f"{config.PREFIX}help | 提及我來聊天"
            )
        )
        await msg.edit(content="✅ 配置重新載入成功！機器人狀態已更新。")
    else:
        await msg.edit(content="❌ 配置重新載入失敗，請檢查日誌獲取詳細資訊。")

@bot.command(name="config_status")
async def config_status_command(ctx):
    """顯示當前配置狀態"""
    try:
        summary = bot.get_config_summary()
        
        embed = discord.Embed(
            title="📋 機器人配置狀態", 
            color=discord.Color.blue(),
            timestamp=ctx.message.created_at
        )
        
        # 基本設定
        embed.add_field(
            name="🔧 基本設定",
            value=(
                f"**前綴**: `{summary['prefix']}`\n"
                f"**日誌等級**: `{summary['log_level']}`\n"
                f"**歷史長度**: `{summary['max_history']}`\n"
                f"**性能監控**: {'✅' if summary['performance_logging'] else '❌'}"
            ),
            inline=False
        )
        
        # API 金鑰狀態
        api_status = []
        api_status.append(f"**Discord Token**: {'✅ 已設定' if summary['token_set'] else '❌ 未設定'}")
        api_status.append(f"**Gemini API**: {'✅ 已設定' if summary['gemini_key_set'] else '❌ 未設定'}")
        api_status.append(f"**OpenAI API**: {'✅ 已設定' if summary['openai_key_set'] else '❌ 未設定'}")
        api_status.append(f"**Anthropic API**: {'✅ 已設定' if summary['anthropic_key_set'] else '❌ 未設定'}")
        
        embed.add_field(
            name="🔑 API 金鑰狀態",
            value="\n".join(api_status),
            inline=False
        )
        
        # 模型配置
        model_info = []
        if 'gemini_model' in summary:
            model_info.append(f"**Gemini**: `{summary['gemini_model']}`")
        if 'openai_model' in summary:
            model_info.append(f"**OpenAI**: `{summary['openai_model']}`")
        if 'anthropic_model' in summary:
            model_info.append(f"**Anthropic**: `{summary['anthropic_model']}`")
        
        if model_info:
            embed.add_field(
                name="🤖 模型配置",
                value="\n".join(model_info),
                inline=False
            )
        
        # 系統資訊
        embed.add_field(
            name="💻 系統資訊",
            value=(
                f"**Python**: `{sys.version.split()[0]}`\n"
                f"**Discord.py**: `{discord.__version__}`\n"
                f"**配置狀態**: {'✅ 已載入' if bot.config_loaded else '❌ 未載入'}"
            ),
            inline=False
        )
        
        embed.set_footer(text=f"請求者: {ctx.author.display_name}")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f"獲取配置狀態時出錯: {e}")
        await ctx.send(f"❌ 獲取配置狀態失敗: {str(e)}")

@bot.command(name="reload_cogs")
@commands.is_owner()
async def reload_cogs_command(ctx):
    """重新載入所有 cogs（僅限機器人擁有者）"""
    msg = await ctx.send("🔄 正在重新載入所有 cogs...")
    
    try:
        # 重新載入所有 cogs
        cogs_to_reload = [
            ("cogs.conversation", "conversation cog"),
            ("cogs.music", "music cog"),
            ("cogs.slash_commands", "slash commands cog"),
            ("cogs.user_management", "user management cog"),
            ("cogs.conversation_memory_commands", "conversation memory commands cog")
        ]
        
        for cog_name, cog_desc in cogs_to_reload:
            try:
                if cog_name in bot.extensions:
                    await bot.reload_extension(cog_name)
                    logger.info(f"✅ {cog_desc} 重新載入完成")
                else:
                    await bot.load_extension(cog_name)
                    logger.info(f"✅ {cog_desc} 載入完成")
            except Exception as e:
                logger.error(f"❌ 載入 {cog_desc} 失敗: {e}")
        
        await msg.edit(content="✅ 所有 cogs 重新載入成功！")
        
    except Exception as e:
        logger.error(f"重新載入 cogs 時出錯: {e}")
        await msg.edit(content=f"❌ 重新載入 cogs 失敗: {str(e)}")

@bot.command(name="full_reload")
@commands.is_owner()
async def full_reload_command(ctx):
    """完整重新載入（配置 + cogs）（僅限機器人擁有者）"""
    msg = await ctx.send("🔄 正在進行完整重新載入...")
    
    try:
        # 1. 重新載入配置
        config_success = await bot.reload_config()
        
        # 2. 重新載入 cogs
        cogs_to_reload = [
            ("cogs.conversation", "conversation cog"),
            ("cogs.music", "music cog"),
            ("cogs.slash_commands", "slash commands cog"),
            ("cogs.user_management", "user management cog"),
            ("cogs.conversation_memory_commands", "conversation memory commands cog")
        ]
        
        for cog_name, cog_desc in cogs_to_reload:
            try:
                if cog_name in bot.extensions:
                    await bot.reload_extension(cog_name)
                else:
                    await bot.load_extension(cog_name)
            except Exception as e:
                logger.error(f"載入 {cog_desc} 失敗: {e}")
        
        # 3. 更新機器人狀態
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening, 
                name=f"{config.PREFIX}help | 提及我來聊天"
            )
        )
        
        if config_success:
            await msg.edit(content="✅ 完整重新載入成功！配置和 cogs 都已更新。")
        else:
            await msg.edit(content="⚠️ 部分重新載入成功，但配置載入時出現問題。")
        
    except Exception as e:
        logger.error(f"完整重新載入時出錯: {e}")
        await msg.edit(content=f"❌ 完整重新載入失敗: {str(e)}")

@bot.command(name="sync_commands")
@commands.is_owner()
async def sync_commands(ctx):
    """強制同步斜線指令（僅限機器人擁有者）"""
    msg = await ctx.send("🔄 正在同步斜線指令...")
    
    try:
        # 顯示當前載入的 extensions
        logger.info(f"📋 當前載入的擴展: {list(bot.extensions.keys())}")
        
        # 檢查並顯示當前註冊的指令
        current_commands = list(bot.tree.get_commands())
        logger.info(f"📋 當前註冊的指令數量: {len(current_commands)}")
        for cmd in current_commands:
            logger.info(f"  - {cmd.name}: {type(cmd).__name__}")
        
        # 清除現有指令並重新同步
        bot.tree.clear_commands(guild=None)  # None 表示清除全域指令
        logger.info("🗑️ 已清除所有現有指令")
        
        # 重新載入所有 cogs 以確保指令註冊
        extensions_to_reload = [
            "cogs.music",
            "cogs.slash_commands",
            "cogs.user_management",
            "cogs.conversation_memory_commands"
        ]
        
        for ext in extensions_to_reload:
            try:
                if ext in bot.extensions:
                    await bot.reload_extension(ext)
                    logger.info(f"✅ 重新載入 {ext}")
                else:
                    await bot.load_extension(ext)
                    logger.info(f"✅ 載入 {ext}")
                    
                # 檢查載入後的指令
                after_commands = list(bot.tree.get_commands())
                logger.info(f"📈 載入 {ext} 後的指令數量: {len(after_commands)}")
                    
            except Exception as e:
                logger.error(f"❌ 載入 {ext} 時出錯: {e}", exc_info=True)
        
        # 檢查最終註冊的指令
        final_commands = list(bot.tree.get_commands())
        logger.info(f"🎯 準備同步的指令數量: {len(final_commands)}")
        for cmd in final_commands:
            logger.info(f"  - 準備同步: {cmd.name} ({type(cmd).__name__})")
        
        # 同步指令到 Discord
        logger.info("🔄 開始同步到 Discord...")
        slash_commands = await bot.tree.sync()
        logger.info(f"✅ Discord 同步完成: {len(slash_commands)} 個指令")
        
        # 顯示結果
        command_names = [cmd.name for cmd in slash_commands]
        embed = discord.Embed(
            title="✅ 斜線指令同步完成",
            description=f"成功同步 {len(slash_commands)} 個斜線指令到 Discord",
            color=discord.Color.green()
        )
        
        # 顯示載入的擴展
        embed.add_field(
            name="📦 載入的擴展",
            value="```\n" + "\n".join(bot.extensions.keys()) + "\n```",
            inline=False
        )
        
        if command_names:
            embed.add_field(
                name="📋 已同步的指令",
                value="```\n" + "\n".join(f"/{cmd}" for cmd in sorted(command_names)) + "\n```",
                inline=False
            )
        else:
            embed.add_field(
                name="⚠️ 警告",
                value="沒有找到任何斜線指令！可能是 cogs 載入失敗",
                inline=False
            )
        
        embed.add_field(
            name="💡 提示",
            value="指令可能需要 1-15 分鐘才會在 Discord 中顯示\n如果仍未出現，請檢查機器人權限",
            inline=False
        )
        
        await msg.edit(content="", embed=embed)
        
    except Exception as e:
        logger.error(f"同步斜線指令失敗: {e}", exc_info=True)
        await msg.edit(content=f"❌ 同步斜線指令失敗: {str(e)}")

@bot.command(name="help")
async def help_command(ctx):
    """顯示幫助信息"""
    embed = discord.Embed(
        title="AI 助手幫助",
        description="我是一個 AI 助手，可以回答問題、提供資訊和進行對話。",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="基本對話",
        value="直接提及我 (@機器人) 或私信我來開始對話。",
        inline=False
    )
    
    embed.add_field(
        name="一般命令",
        value=(
            f"`{config.PREFIX}chat <訊息>` - 與 AI 聊天\n"
            f"`{config.PREFIX}clear_chat` - 清除你的對話歷史\n"
            f"`{config.PREFIX}llm_info` - 顯示當前 LLM 模型資訊\n"
            f"`{config.PREFIX}models` - 列出所有可用的模型類型\n"
            f"`{config.PREFIX}switch_model <模型類型>` - 切換 LLM 模型\n"
            f"`{config.PREFIX}config_status` - 顯示配置狀態\n"
            f"`{config.PREFIX}help` - 顯示此幫助訊息"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🗃️ 用戶資料管理（斜線指令）",
        value=(
            "`/設定個人資料` - 設置用戶資料\n"
            "`/個人資料` - 查看用戶資料\n"
            "`/刪除個人資料` - 刪除用戶資料\n"
            "`/添加標籤` - 新增用戶標籤\n"
            "`/檢視標籤` - 查看用戶標籤\n"
            "`/移除標籤` - 移除用戶標籤\n"
            "`/用戶完整資訊` - 查看完整資訊\n"
            "`/搜尋用戶` - 搜尋用戶"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🧠 記憶管理（斜線指令）",
        value=(
            "`/設置記憶` - 設置個人記憶\n"
            "`/查看記憶` - 查看個人記憶\n"
            "`/清除記憶` - 清除個人記憶\n"
            "`/記憶歷史` - 查看記憶歷史\n"
            "`/資料庫統計` - 資料庫統計（管理員）"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🗣️ 對話記憶（斜線指令）",
        value=(
            "`/檢視對話摘要` - 查看對話摘要\n"
            "`/獲取對話洞察` - 對話行為分析\n"
            "`/檢視互動歷史` - 查看互動記錄\n"
            "`/清理對話記憶` - 清理舊對話記憶\n"
            "`/導出對話記憶` - 導出記憶資料"
        ),
        inline=False
    )
    
    # 如果是機器人擁有者，顯示管理命令
    if await bot.is_owner(ctx.author):
        embed.add_field(
            name="🔧 管理命令（僅限擁有者）",
            value=(
                f"`{config.PREFIX}reload_config` - 重新載入配置\n"
                f"`{config.PREFIX}reload_cogs` - 重新載入 cogs\n"
                f"`{config.PREFIX}full_reload` - 完整重新載入\n"
                f"`{config.PREFIX}sync_commands` - 強制同步斜線指令"
            ),
            inline=False
        )
    
    embed.add_field(
        name="可用的模型類型",
        value=(
            "`gemini` - Google Gemini API (預設)\n"
            "`openai` - OpenAI API\n"
            "`anthropic` - Anthropic API\n"
            "`local` - 本地 API 模型\n"
            "`local_python` - 本地 Python 模型"
        ),
        inline=False
    )
    
    embed.set_footer(text=f"當前前綴: {config.PREFIX}")
    
    await ctx.send(embed=embed)

@bot.command(name="models")
async def list_models(ctx):
    """列出所有可用的模型類型"""
    embed = discord.Embed(
        title="可用的 LLM 模型類型",
        description="以下是可用的模型類型，可以使用 `!switch_model <類型>` 來切換",
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="雲端 API 模型",
        value=(
            "`gemini` - Google Gemini API (推薦)\n"
            "`openai` - OpenAI API (GPT 系列)\n"
            "`anthropic` - Anthropic API (Claude 系列)"
        ),
        inline=False
    )
    
    embed.add_field(
        name="本地模型",
        value=(
            "`local` - 本地 API 模型\n"
            "`local_python` - 本地 Python 模型"
        ),
        inline=False
    )
    
    await ctx.send(embed=embed)

async def load_extensions():
    """載入所有擴展"""
    # 確保 cogs 目錄存在
    os.makedirs("cogs", exist_ok=True)
    
    # 檢查是否已經載入，避免重複載入
    extensions_to_load = [
        ("cogs.conversation", "conversation cog"),
        ("cogs.music", "music cog"),
        ("cogs.slash_commands", "slash commands cog"),
        ("cogs.user_management", "user management cog"),
        ("cogs.conversation_memory_commands", "conversation memory commands cog")
    ]
    
    for ext_name, ext_desc in extensions_to_load:
        try:
            if ext_name in bot.extensions:
                logger.info(f"{ext_desc} 已經載入，跳過")
                continue
                
            await bot.load_extension(ext_name)
            logger.info(f"已載入 {ext_desc}")
        except Exception as e:
            logger.error(f"載入 {ext_desc} 時出錯: {e}", exc_info=True)

async def main():
    """主函數"""
    observer = None
    try:
        # 驗證必要的配置
        if not hasattr(config, 'TOKEN') or not config.TOKEN:
            logger.error("❌ Discord TOKEN 未設定，請檢查配置")
            return
        
        # 載入擴展
        await load_extensions()

        # 在開發模式下啟用熱重載
        if config.DEV_MODE:
            observer = setup_reloader(bot, asyncio.get_event_loop())
        
        # 啟動機器人
        logger.info("🚀 正在啟動機器人...")
        await bot.start(config.TOKEN)
        
    except discord.LoginFailure:
        logger.error("❌ 登入失敗。請檢查 TOKEN 是否正確。")
    except KeyboardInterrupt:
        logger.info("⏹️ 收到中斷信號，正在關閉...")
    except Exception as e:
        logger.error(f"❌ 啟動機器人時出錯: {e}", exc_info=True)
    finally:
        # 清理資源
        logger.info("🧹 正在清理資源...")
        
        # 清理 Lavalink 管理器的 HTTP session
        try:
            from utils.lavalink_manager import lavalink_manager
            if lavalink_manager:
                await lavalink_manager.close_session()
                logger.info("✅ Lavalink 管理器 session 已關閉")
        except Exception as e:
            logger.warning(f"⚠️ 清理 Lavalink 管理器時出錯: {e}")
        
        # 停止熱重載監控
        if observer:
            observer.stop()
            observer.join()
            logger.info("⏹️ 熱重載監控已停止")
        
        # 關閉機器人
        if not bot.is_closed():
            await bot.close()
            logger.info("🤖 機器人連接已關閉")
        
        logger.info("🔚 所有資源清理完成")

# 運行機器人
if __name__ == "__main__":
    asyncio.run(main())