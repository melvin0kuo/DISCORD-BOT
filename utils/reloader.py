import asyncio
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, PatternMatchingEventHandler

logger = logging.getLogger("discord")

class CodeReloader(PatternMatchingEventHandler):
    """
    監控文件變更並觸發機器人重載的處理器。
    """
    def __init__(self, bot, loop):
        super().__init__(patterns=["*.py"], ignore_directories=True, case_sensitive=False)
        self.bot = bot
        self.loop = loop
        self.debounce_task = None

    def on_modified(self, event):
        """當文件被修改時觸發"""
        if self.debounce_task and not self.debounce_task.done():
            self.debounce_task.cancel()
        
        logger.info(f"🔥 偵測到文件變更: {event.src_path}，準備熱重載...")
        # 使用 debounce 避免短時間內多次觸發
        self.debounce_task = self.loop.create_task(self.schedule_reload())

    async def schedule_reload(self):
        """安排重載任務，並加入延遲以避免短時間內重複觸發"""
        await asyncio.sleep(1.5) # 等待 1.5 秒，以防連續存檔
        try:
            logger.info("🚀 執行完整熱重載...")
            # 1. 重新載入配置
            config_success = await self.bot.reload_config()
            
            # 2. 重新載入所有 cogs
            loaded_cogs = list(self.bot.extensions.keys())
            for cog_name in loaded_cogs:
                try:
                    await self.bot.reload_extension(cog_name)
                    logger.info(f"✔️ Cog '{cog_name}' 重載成功。")
                except Exception as e:
                    logger.error(f"❌ Cog '{cog_name}' 重載失敗: {e}", exc_info=True)

            # 3. 更新機器人狀態
            import config
            await self.bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name=f"{config.PREFIX}help | 提及我來聊天"
                )
            )

            if config_success:
                logger.info("✅ 完整熱重載成功！")
            else:
                logger.warning("⚠️ 熱重載完成，但配置載入時出現問題。")
        except Exception as e:
            logger.error(f"❌ 熱重載過程中發生嚴重錯誤: {e}", exc_info=True)

def setup_reloader(bot, loop):
    """
    設定並啟動文件監控觀察者。
    """
    event_handler = CodeReloader(bot, loop)
    observer = Observer()
    # 監控當前工作目錄下的所有 .py 文件
    observer.schedule(event_handler, path='.', recursive=True)
    observer.start()
    logger.info("🔥 熱重載功能已啟動，監控 .py 文件變更...")
    return observer