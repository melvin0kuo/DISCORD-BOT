import discord
from discord.ext import commands
import asyncio
import os
import logging
import config
from utils.helpers import setup_logging
from utils.gpu_monitor import GPUMonitor
from utils.model_loader import ModelLoader
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# 設置日誌
logger = setup_logging()
# logger.setLevel(logging.DEBUG)

# 設置意圖
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# 創建機器人
bot = commands.Bot(command_prefix=config.PREFIX, intents=intents, help_command=None)

@bot.event
async def on_ready():
    logger.info(f"機器人已登入為: {bot.user.name}")
    logger.info(f"機器人 ID: {bot.user.id}")
    logger.info(f"Discord.py 版本: {discord.__version__}")
    
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
    
    # 測試 GGUF 模型載入
    logger.debug("開始測試 GGUF 模型載入...")
    try:
        model_loader = ModelLoader.get_instance()
        
        # 檢查模型是否已經在載入中
        if model_loader.gguf_is_loading:
            logger.debug("GGUF 模型正在載入中，等待完成...")
            # 等待一段時間，讓模型有機會完成載入
            for i in range(10):  # 最多等待 10 秒
                await asyncio.sleep(1)
                if model_loader.gguf_is_ready:
                    logger.debug("GGUF 模型已成功載入！")
                    break
        
        # 如果模型還沒有載入，嘗試載入
        if not model_loader.gguf_is_ready:
            success = model_loader.load_gguf_model()
            if success:
                logger.debug("GGUF 模型載入成功!")
            else:
                logger.error("GGUF 模型載入失敗")
                return
        
        # 嘗試生成一些文本以確認模型正常工作
        test_output = model_loader.generate_with_gguf("你好，請簡單介紹一下自己。", {"max_new_tokens": 50})
        logger.debug(f"GGUF 模型測試輸出: {test_output}")
        
    except Exception as e:
        logger.error(f"測試 GGUF 模型時出錯: {e}", exc_info=True)
    
    logger.info("機器人已準備就緒!")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ 缺少必要參數: {error.param}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ 參數類型錯誤: {error}")
    else:
        logger.error(f"執行命令時出錯: {error}")
        await ctx.send(f"❌ 執行命令時出錯: {error}")

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
        name="命令",
        value=(
            f"`{config.PREFIX}chat <訊息>` - 與 AI 聊天\n"
            f"`{config.PREFIX}clear_chat` - 清除你的對話歷史\n"
            f"`{config.PREFIX}llm_info` - 顯示當前 LLM 模型資訊\n"
            f"`{config.PREFIX}models` - 列出所有可用的模型類型\n"
            f"`{config.PREFIX}switch_model <模型類型>` - 切換 LLM 模型\n"
            f"`{config.PREFIX}help` - 顯示此幫助訊息"
        ),
        inline=False
    )
    
    embed.add_field(
        name="可用的模型類型",
        value=(
            "`local_python` - 本地 Python 模型 (默認)\n"
            "`gemini` - Google Gemini API\n"
            "`openai` - OpenAI API\n"
            "`anthropic` - Anthropic API\n"
            "`local` - 本地 API 模型\n"
            "`local_gguf` - 本地 GGUF 模型"
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
        name="本地模型",
        value=(
            "`local_python` - 本地 Python 模型\n"
            "`local_gguf` - 本地 GGUF 模型\n"
            "`local` - 本地 API 模型"
        ),
        inline=False
    )
    
    embed.add_field(
        name="雲端 API 模型",
        value=(
            "`openai` - OpenAI API (GPT 系列)\n"
            "`anthropic` - Anthropic API (Claude 系列)\n"
            "`gemini` - Google Gemini API"
        ),
        inline=False
    )
    
    await ctx.send(embed=embed)

async def load_extensions():
    """載入所有擴展"""
    # 確保 cogs 目錄存在
    os.makedirs("cogs", exist_ok=True)
    
    # 載入對話 cog
    try:
        await bot.load_extension("cogs.conversation")
        logger.info("已載入 conversation cog")
    except Exception as e:
        logger.error(f"載入 conversation cog 時出錯: {e}", exc_info=True)

async def main():
    """主函數"""
    await load_extensions()
    
    # 啟動機器人
    try:
        await bot.start(config.TOKEN)
    except discord.LoginFailure:
        logger.error("登入失敗。請檢查 TOKEN 是否正確。")
    except Exception as e:
        logger.error(f"啟動機器人時出錯: {e}")

# 運行機器人
if __name__ == "__main__":
    asyncio.run(main())
