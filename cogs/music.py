# Enhanced Music Cog with UI, Playlist, Autoplay, and More
import discord
from discord.ext import commands
import wavelink
import asyncio
import logging
import random
from typing import List, Optional
import time
import json
import os

# 添加 Wavelink 異常處理
from wavelink.exceptions import LavalinkException

# 導入 Lavalink 伺服器管理器
try:
    from utils.lavalink_manager import lavalink_manager
except ImportError:
    lavalink_manager = None
    logging.warning("⚠️ Lavalink 伺服器管理器導入失敗，將使用基本模式")

logger = logging.getLogger(__name__)

class MusicQueue:
    """音樂佇列管理"""
    def __init__(self):
        self.queue: List[wavelink.Playable] = []
        self.history: List[wavelink.Playable] = []
        self.loop_mode = "off"  # off, track, queue
        self.shuffle = False
        
    def add(self, track: wavelink.Playable):
        """添加音樂到佇列"""
        if self.shuffle:
            # 隨機插入位置
            pos = random.randint(0, len(self.queue))
            self.queue.insert(pos, track)
        else:
            self.queue.append(track)
    
    def add_to_history(self, track: wavelink.Playable):
        """將歌曲添加到歷史記錄"""
        if track not in self.history or (self.history and self.history[-1] != track):
            self.history.append(track)
            # 保持歷史記錄不超過 50 首
            if len(self.history) > 50:
                self.history = self.history[-50:]
            logger.info(f"📜 已添加到歷史記錄: {track.title} (總計: {len(self.history)} 首)")
    
    def get_next(self) -> Optional[wavelink.Playable]:
        """獲取下一首音樂"""
        if self.loop_mode == "track":
            # 單曲循環：返回歷史記錄中的最後一首（當前播放的歌曲）
            return self.history[-1] if self.history else None
        
        if not self.queue:
            return None
            
        # 從佇列中取出下一首歌曲
        next_track = self.queue.pop(0)
        
        # 使用新的添加歷史記錄方法
        self.add_to_history(next_track)
        
        # 在佇列循環模式下，將歌曲重新加入佇列末尾
        if self.loop_mode == "queue":
            self.queue.append(next_track)
            
        return next_track
    
    def clear(self):
        """清空佇列"""
        self.queue.clear()
    
    def remove(self, index: int) -> bool:
        """移除指定位置的音樂"""
        if 0 <= index < len(self.queue):
            self.queue.pop(index)
            return True
        return False
    
    def toggle_shuffle(self):
        """切換隨機播放"""
        self.shuffle = not self.shuffle
        if self.shuffle:
            random.shuffle(self.queue)
    
    def set_loop_mode(self, mode: str):
        """設置循環模式"""
        if mode in ["off", "track", "queue"]:
            self.loop_mode = mode

class MusicControlView(discord.ui.View):
    """音樂控制面板"""
    def __init__(self, player: wavelink.Player, music_cog):
        super().__init__(timeout=300)  # 5分鐘超時
        self.player = player
        self.music_cog = music_cog
        
    @discord.ui.button(emoji="⏯️", style=discord.ButtonStyle.primary)
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        """播放/暫停按鈕"""
        if self.player.paused:
            await self.player.pause(False)
            await interaction.response.send_message("▶️ 繼續播放", ephemeral=True)
        else:
            await self.player.pause(True)
            await interaction.response.send_message("⏸️ 已暫停", ephemeral=True)
    
    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        """跳過按鈕"""
        if self.player.current:
            await self.player.stop()
            await interaction.response.send_message("⏭️ 已跳過", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 沒有正在播放的音樂", ephemeral=True)
    
    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        """停止按鈕"""
        queue = self.music_cog.get_queue(interaction.guild.id)
        queue.clear()
        await self.player.stop()
        await interaction.response.send_message("⏹️ 已停止播放並清空佇列", ephemeral=True)
    
    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary)
    async def shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        """隨機播放按鈕"""
        queue = self.music_cog.get_queue(interaction.guild.id)
        queue.toggle_shuffle()
        status = "開啟" if queue.shuffle else "關閉"
        await interaction.response.send_message(f"🔀 隨機播放已{status}", ephemeral=True)
    
    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary)
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        """循環播放按鈕"""
        queue = self.music_cog.get_queue(interaction.guild.id)
        modes = {"off": "queue", "queue": "track", "track": "off"}
        new_mode = modes[queue.loop_mode]
        queue.set_loop_mode(new_mode)
        
        mode_text = {"off": "關閉", "queue": "佇列循環", "track": "單曲循環"}
        await interaction.response.send_message(f"🔁 循環模式: {mode_text[new_mode]}", ephemeral=True)

class VolumeView(discord.ui.View):
    """音量控制面板"""
    def __init__(self, player: wavelink.Player):
        super().__init__(timeout=60)
        self.player = player
    
    @discord.ui.button(emoji="🔇", style=discord.ButtonStyle.secondary)
    async def mute(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.set_volume(0)
        await interaction.response.send_message("🔇 已靜音", ephemeral=True)
    
    @discord.ui.button(emoji="🔉", style=discord.ButtonStyle.secondary)
    async def low(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.set_volume(25)
        await interaction.response.send_message("🔉 音量: 25%", ephemeral=True)
    
    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary)
    async def medium(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.set_volume(50)
        await interaction.response.send_message("🔊 音量: 50%", ephemeral=True)
    
    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.primary)
    async def high(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.set_volume(75)
        await interaction.response.send_message("🔊 音量: 75%", ephemeral=True)
    
    @discord.ui.button(emoji="📢", style=discord.ButtonStyle.danger)
    async def max_vol(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.set_volume(100)
        await interaction.response.send_message("📢 音量: 100%", ephemeral=True)

class PlaylistView(discord.ui.View):
    """播放列表管理面板"""
    def __init__(self, music_cog, guild_id: int):
        super().__init__(timeout=300)
        self.music_cog = music_cog
        self.guild_id = guild_id
        self.current_page = 0
    
    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            embed = self.music_cog.create_queue_embed(self.guild_id, self.current_page)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("已經是第一頁了", ephemeral=True)
    
    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue = self.music_cog.get_queue(self.guild_id)
        max_pages = (len(queue.queue) - 1) // 10 + 1 if queue.queue else 1
        if self.current_page < max_pages - 1:
            self.current_page += 1
            embed = self.music_cog.create_queue_embed(self.guild_id, self.current_page)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("已經是最後一頁了", ephemeral=True)
    
    @discord.ui.button(emoji="🗑️", style=discord.ButtonStyle.danger)
    async def clear_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue = self.music_cog.get_queue(self.guild_id)
        queue.clear()
        embed = self.music_cog.create_queue_embed(self.guild_id, 0)
        self.current_page = 0
        await interaction.response.edit_message(embed=embed, view=self)

class SavedPlaylistView(discord.ui.View):
    """儲存播放列表管理面板"""
    def __init__(self, music_cog, user_id: int):
        super().__init__(timeout=300)
        self.music_cog = music_cog
        self.user_id = user_id
        self.current_page = 0
    
    @discord.ui.button(label="載入播放列表", emoji="📥", style=discord.ButtonStyle.success)
    async def load_playlist(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LoadPlaylistModal(self.music_cog))
    
    @discord.ui.button(label="儲存目前佇列", emoji="💾", style=discord.ButtonStyle.primary)
    async def save_current_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SavePlaylistModal(self.music_cog, interaction.guild.id))

class SavePlaylistModal(discord.ui.Modal):
    """儲存播放列表對話框"""
    def __init__(self, music_cog, guild_id: int):
        super().__init__(title="儲存播放列表")
        self.music_cog = music_cog
        self.guild_id = guild_id
        
        self.name_input = discord.ui.TextInput(
            label="播放列表名稱",
            placeholder="輸入播放列表名稱...",
            max_length=50
        )
        self.add_item(self.name_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        queue = self.music_cog.get_queue(self.guild_id)
        if not queue.queue:
            await interaction.response.send_message("❌ 目前佇列是空的", ephemeral=True)
            return
        
        playlist_name = self.name_input.value
        user_id = str(interaction.user.id)
        
        if user_id not in self.music_cog.saved_playlists:
            self.music_cog.saved_playlists[user_id] = {}
        
        # 儲存播放列表
        playlist_data = []
        for track in queue.queue:
            playlist_data.append({
                "title": track.title,
                "uri": track.uri,
                "author": getattr(track, 'author', 'Unknown')
            })
        
        self.music_cog.saved_playlists[user_id][playlist_name] = playlist_data
        self.music_cog.save_playlists()
        
        await interaction.response.send_message(f"✅ 播放列表 '{playlist_name}' 已儲存 ({len(playlist_data)} 首歌曲)", ephemeral=True)

class LoadPlaylistModal(discord.ui.Modal):
    """載入播放列表對話框"""
    def __init__(self, music_cog):
        super().__init__(title="載入播放列表")
        self.music_cog = music_cog
        
        self.name_input = discord.ui.TextInput(
            label="播放列表名稱",
            placeholder="輸入要載入的播放列表名稱...",
            max_length=50
        )
        self.add_item(self.name_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        playlist_name = self.name_input.value
        user_id = str(interaction.user.id)
        
        if user_id not in self.music_cog.saved_playlists or playlist_name not in self.music_cog.saved_playlists[user_id]:
            await interaction.response.send_message(f"❌ 找不到播放列表 '{playlist_name}'", ephemeral=True)
            return
        
        playlist_data = self.music_cog.saved_playlists[user_id][playlist_name]
        queue = self.music_cog.get_queue(interaction.guild.id)
        
        loaded_count = 0
        for track_data in playlist_data:
            try:
                # 嘗試重新搜索歌曲
                tracks = await wavelink.Playable.search(track_data["uri"])
                if tracks:
                    queue.add(tracks[0])
                    loaded_count += 1
            except:
                continue
        
        await interaction.response.send_message(f"✅ 已載入播放列表 '{playlist_name}' ({loaded_count}/{len(playlist_data)} 首歌曲)", ephemeral=True)

class EnhancedMusic(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}  # guild_id -> MusicQueue
        self.autoplay_enabled = {}  # guild_id -> bool
        self.playlists_file = "data/playlists.json"
        self.autoplay_config_file = "data/autoplay_config.json"
        self.autoplay_stats = {}  # guild_id -> {'attempts': int, 'successes': int, 'last_attempt': float}
        self._connect_lock = asyncio.Lock()  # 防止 connect_to_lavalink 被同時呼叫兩次
        self._voice_connect_times: dict = {}   # guild_id -> timestamp，用於偵測快速斷線
        self._user_stopped: set = set()        # guild_id，記錄是使用者主動停止的
        self.ensure_data_dir()
        self.load_playlists()
        self.load_autoplay_config()
        
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """處理語音狀態更新，偵測 Lavalink 語音連線失敗"""
        try:
            if member != self.bot.user:
                return

            before_ch = before.channel.name if before.channel else "無"
            after_ch  = after.channel.name  if after.channel  else "無"
            guild_id  = member.guild.id

            logger.info(
                f"[語音狀態] 機器人: {before_ch} → {after_ch} | "
                f"guild={guild_id} | nodes={list(wavelink.Pool.nodes.keys())}"
            )

            if not before.channel and after.channel:
                # 剛加入語音頻道 — 記錄時間
                self._voice_connect_times[guild_id] = time.time()

            elif before.channel and not after.channel:
                # 離開語音頻道
                for node_id, node in wavelink.Pool.nodes.items():
                    logger.info(
                        f"[語音狀態] node={node_id} status={node.status} "
                        f"players={len(node.players)}"
                    )

                join_time = self._voice_connect_times.pop(guild_id, None)
                user_stopped = guild_id in self._user_stopped
                self._user_stopped.discard(guild_id)

                elapsed = time.time() - join_time if join_time else 999

                if not user_stopped and join_time and elapsed < 10:
                    # 快速斷線 (< 10 秒) 且非使用者主動停止
                    # → Lavalink 伺服器無法連接 Discord 語音
                    logger.warning(
                        f"⚡ 快速斷線偵測 (guild={guild_id}, elapsed={elapsed:.1f}s) "
                        f"→ 目前 Lavalink 伺服器無法連接 Discord 語音，嘗試切換..."
                    )
                    if lavalink_manager and lavalink_manager.current_server:
                        lavalink_manager.current_server.status = "voice_fail"
                        lavalink_manager.current_server.error_count += 5
                    asyncio.create_task(self.switch_lavalink_server())
                else:
                    if guild_id in self.queues:
                        self.queues[guild_id].clear()
                        logger.info(f"🔧 已清理伺服器 {guild_id} 的音樂佇列")

        except Exception as e:
            logger.error(f"❌ 處理語音狀態更新時出錯: {e}", exc_info=True)
        
    def ensure_data_dir(self):
        """確保數據目錄存在"""
        os.makedirs("data", exist_ok=True)
        
    def load_playlists(self):
        """載入播放列表"""
        try:
            if os.path.exists(self.playlists_file):
                with open(self.playlists_file, 'r', encoding='utf-8') as f:
                    self.saved_playlists = json.load(f)
            else:
                self.saved_playlists = {}
        except Exception as e:
            logger.error(f"載入播放列表失敗: {e}")
            self.saved_playlists = {}
    
    def save_playlists(self):
        """儲存播放列表"""
        try:
            with open(self.playlists_file, 'w', encoding='utf-8') as f:
                json.dump(self.saved_playlists, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"儲存播放列表失敗: {e}")
    
    def load_autoplay_config(self):
        """載入自動播放設定"""
        try:
            if os.path.exists(self.autoplay_config_file):
                with open(self.autoplay_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.autoplay_enabled = config.get('autoplay_enabled', {})
                    logger.info(f"📂 載入自動播放設定: {len(self.autoplay_enabled)} 個伺服器")
            else:
                # 預設所有伺服器啟用自動播放
                self.autoplay_enabled = {}
                logger.info("🎵 自動播放設定檔案不存在，使用預設設定（預設啟用）")
        except Exception as e:
            logger.error(f"載入自動播放設定失敗: {e}")
            self.autoplay_enabled = {}
    
    def save_autoplay_config(self):
        """儲存自動播放設定"""
        try:
            config = {
                'autoplay_enabled': self.autoplay_enabled
            }
            with open(self.autoplay_config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.debug(f"💾 已儲存自動播放設定: {len(self.autoplay_enabled)} 個伺服器")
        except Exception as e:
            logger.error(f"儲存自動播放設定失敗: {e}")
    
    def get_autoplay_status(self, guild_id: int) -> bool:
        """獲取伺服器的自動播放狀態（預設開啟）"""
        return self.autoplay_enabled.get(guild_id, True)  # 預設為 True（啟用）
    
    def set_autoplay_status(self, guild_id: int, enabled: bool):
        """設置伺服器的自動播放狀態並保存"""
        self.autoplay_enabled[guild_id] = enabled
        self.save_autoplay_config()
        logger.info(f"🤖 伺服器 {guild_id} 自動播放狀態: {'啟用' if enabled else '停用'}")
    
    def get_queue(self, guild_id: int) -> MusicQueue:
        """獲取伺服器的音樂佇列"""
        if guild_id not in self.queues:
            self.queues[guild_id] = MusicQueue()
        return self.queues[guild_id]
    
    def format_duration(self, milliseconds: int) -> str:
        """格式化時間"""
        seconds = milliseconds // 1000
        minutes = seconds // 60
        hours = minutes // 60
        
        if hours > 0:
            return f"{hours}:{minutes%60:02d}:{seconds%60:02d}"
        else:
            return f"{minutes}:{seconds%60:02d}"
    
    def create_progress_bar(self, current: int, total: int, length: int = 20) -> str:
        """創建進度條"""
        if total == 0:
            return "▱" * length
        
        progress = current / total
        filled = int(progress * length)
        bar = "▰" * filled + "▱" * (length - filled)
        return bar
    
    def create_now_playing_embed(self, player: wavelink.Player, guild_id: int) -> discord.Embed:
        """創建正在播放的嵌入"""
        if not player.current:
            return discord.Embed(title="❌ 沒有正在播放的音樂", color=discord.Color.red())
        
        track = player.current
        queue = self.get_queue(guild_id)
        
        # 計算進度
        position = player.position
        duration = track.length
        progress_bar = self.create_progress_bar(position, duration)
        
        embed = discord.Embed(
            title="🎵 正在播放",
            description=f"**[{track.title}]({track.uri})**",
            color=discord.Color.green()
        )
        
        if hasattr(track, 'author') and track.author:
            embed.add_field(name="👤 作者", value=track.author, inline=True)
        
        embed.add_field(
            name="⏱️ 進度", 
            value=f"{self.format_duration(position)} / {self.format_duration(duration)}\n{progress_bar}",
            inline=False
        )
        
        embed.add_field(name="🔊 音量", value=f"{player.volume}%", inline=True)
        embed.add_field(name="📋 佇列中", value=f"{len(queue.queue)} 首歌曲", inline=True)
        
        # 循環和隨機狀態
        loop_emoji = {"off": "🔁", "queue": "🔂", "track": "🔂"}
        shuffle_emoji = "🔀" if queue.shuffle else "➡️"
        embed.add_field(
            name="🎛️ 模式", 
            value=f"{loop_emoji[queue.loop_mode]} {shuffle_emoji}", 
            inline=True
        )
        
        # 自動播放狀態 - 使用新的方法
        autoplay_status = "✅" if self.get_autoplay_status(guild_id) else "❌"
        embed.add_field(name="🤖 自動播放", value=autoplay_status, inline=True)
        
        if hasattr(track, 'thumbnail'):
            embed.set_thumbnail(url=track.thumbnail)
        
        embed.set_footer(text=f"由 {track.source} 提供")
        
        return embed
    
    def create_queue_embed(self, guild_id: int, page: int = 0) -> discord.Embed:
        """創建佇列嵌入"""
        queue = self.get_queue(guild_id)
        
        if not queue.queue:
            return discord.Embed(
                title="📋 播放佇列", 
                description="佇列是空的", 
                color=discord.Color.orange()
            )
        
        items_per_page = 10
        start = page * items_per_page
        end = start + items_per_page
        page_items = queue.queue[start:end]
        
        embed = discord.Embed(
            title="📋 播放佇列",
            color=discord.Color.blue()
        )
        
        description = ""
        for i, track in enumerate(page_items, start + 1):
            duration = self.format_duration(track.length) if hasattr(track, 'length') else "未知"
            description += f"`{i}.` **{track.title}** ({duration})\n"
        
        embed.description = description
        
        total_pages = (len(queue.queue) - 1) // items_per_page + 1
        embed.set_footer(text=f"頁面 {page + 1}/{total_pages} • 總共 {len(queue.queue)} 首歌曲")
        
        return embed

    @commands.Cog.listener()
    async def on_ready(self):
        """當 cog 準備就緒時初始化 Wavelink"""
        if not wavelink.Pool.nodes:
            await self.connect_to_lavalink()
        
        logger.info("✅ Enhanced Music cog 已準備就緒")

    @staticmethod
    def _make_node(uri: str, password: str, identifier: str) -> wavelink.Node:
        """統一建立 wavelink Node，確保參數與最新 API 一致"""
        return wavelink.Node(
            uri=uri,
            password=password,
            identifier=identifier,
            resume_timeout=60,
            inactive_player_timeout=300,   # 靜止 300 秒觸發 inactive 事件
            inactive_channel_tokens=3,     # 空頻道播完 3 首後觸發
        )

    async def connect_to_lavalink(self):
        """連接到 Lavalink 伺服器（加鎖防競態、智能選擇 + 逐一備用）"""
        # 防止同時有兩個 on_ready / 重連流程同時搶著建立節點
        if self._connect_lock.locked():
            logger.info("⏳ 已有另一個連線程序進行中，跳過重複呼叫")
            return False

        async with self._connect_lock:
            # 再次確認是否已有可用節點（等待期間可能已連線）
            if wavelink.Pool.nodes:
                logger.info("✅ 節點已存在，跳過重複連線")
                return True

            if lavalink_manager:
                try:
                    logger.info("🔍 正在搜尋最佳 Lavalink 伺服器...")
                    await lavalink_manager.update_server_list()
                    best_server = await lavalink_manager.get_best_server()
                    if best_server:
                        node = self._make_node(best_server.uri, best_server.password, f"node_{int(time.time())}")
                        await wavelink.Pool.connect(nodes=[node], client=self.bot, cache_capacity=100)
                        lavalink_manager.current_server = best_server
                        logger.info(f"✅ 已連接到 Lavalink 伺服器: {best_server.name} ({best_server.version})")
                        return True
                    else:
                        logger.warning("⚠️ 智能選擇未找到可用伺服器，逐一嘗試備用清單...")
                except Exception as e:
                    logger.error(f"❌ 智能連接失敗: {e}，逐一嘗試備用清單...")

            # 逐一嘗試備用伺服器
            for fallback in (lavalink_manager.FALLBACK_SERVERS if lavalink_manager else []):
                try:
                    node = self._make_node(fallback.uri, fallback.password, f"node_{int(time.time())}")
                    await wavelink.Pool.connect(nodes=[node], client=self.bot, cache_capacity=100)
                    lavalink_manager.current_server = fallback
                    logger.info(f"✅ 備用連接成功: {fallback.name}")
                    return True
                except Exception as e:
                    logger.warning(f"備用伺服器 {fallback.name} 連接失敗: {e}")
                    continue

            logger.error("❌ 所有 Lavalink 伺服器均無法連接")
            return False

    async def switch_lavalink_server(self):
        """切換 Lavalink 伺服器"""
        if not lavalink_manager:
            return False

        try:
            logger.info("🔄 正在切換 Lavalink 伺服器...")

            # eject=True 讓 wavelink 在 close 時從 Pool 內部 __nodes 移除該節點
            for node in list(wavelink.Pool.nodes.values()):
                try:
                    await node.close(eject=True)
                except Exception as e:
                    logger.warning(f"關閉節點 {node.identifier} 時出錯: {e}")

            # 取得下一個可用伺服器
            next_server = await lavalink_manager.get_next_server()
            if next_server:
                new_node = self._make_node(next_server.uri, next_server.password, f"node_{int(time.time())}")
                await wavelink.Pool.connect(nodes=[new_node], client=self.bot, cache_capacity=100)
                lavalink_manager.current_server = next_server
                logger.info(f"✅ 已切換到: {next_server.name} ({next_server.version})")
                return True
            else:
                logger.error("❌ 沒有可用的替代伺服器，嘗試重新連接...")
                return await self.connect_to_lavalink()

        except Exception as e:
            logger.error(f"❌ 切換伺服器失敗: {e}")
            return False

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        node = payload.node
        logger.info(
            f"✅ Wavelink 節點就緒: {node.identifier} | "
            f"resumed={payload.resumed} | players={len(node.players)}"
        )

    @commands.Cog.listener()
    async def on_wavelink_node_closed(self, node: wavelink.Node, disconnected: list):
        logger.warning(
            f"⚠️ Wavelink 節點關閉: {node.identifier} | "
            f"斷線 players={len(disconnected)} | "
            f"剩餘 nodes={list(wavelink.Pool.nodes.keys())}"
        )
        await asyncio.sleep(3)
        if not wavelink.Pool.nodes:
            logger.info("🔄 節點全滅，嘗試自動重新連接...")
            success = await self.connect_to_lavalink()
            if not success:
                logger.error("❌ 自動重連失敗，音樂功能暫時不可用")

    @commands.Cog.listener()
    async def on_wavelink_inactive_player(self, player: wavelink.Player):
        """播放器閒置事件——只記 log，不自動斷線"""
        logger.info(
            f"[閒置] guild={player.guild.id} | "
            f"current={player.current} | "
            f"channel={getattr(player, 'channel', None)}"
        )

    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, payload: wavelink.TrackExceptionEventPayload):
        logger.error(
            f"[Track exception] guild={payload.player.guild.id} | "
            f"track={payload.track.title if payload.track else '?'} | "
            f"error={payload.exception}"
        )

    @commands.Cog.listener()
    async def on_wavelink_track_stuck(self, payload: wavelink.TrackStuckEventPayload):
        logger.warning(
            f"[Track stuck] guild={payload.player.guild.id} | "
            f"track={payload.track.title if payload.track else '?'} | "
            f"threshold={payload.threshold}ms"
        )

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        """當音軌結束時自動播放下一首（改進穩定性）"""
        try:
            player = payload.player
            guild_id = player.guild.id
            queue = self.get_queue(guild_id)
            
            logger.info(f"🎵 音軌結束事件觸發 - 原因: {payload.reason} | 伺服器: {guild_id}")
            logger.info(f"📊 當前佇列狀態: {len(queue.queue)} 首歌曲 | 自動播放: {self.autoplay_enabled.get(guild_id, False)}")
            
            # 防止重複處理：檢查播放器狀態
            if not player or player.guild.id != guild_id:
                logger.warning("⚠️ 播放器狀態異常，跳過處理")
                return
            
            # 處理各種結束原因（wavelink 3.x reason 為小寫字串）
            should_auto_play = False
            reason = str(payload.reason).lower()

            if reason == "finished":
                logger.info("✅ 音軌正常播放完畢，處理自動播放...")
                should_auto_play = True
            elif reason == "stopped":
                logger.info("⏹️ 音軌被手動停止，檢查是否為跳過操作...")
                should_auto_play = len(queue.queue) > 0
            elif reason == "replaced":
                logger.info("🔄 音軌被替換，跳過自動播放")
                return
            elif reason in ("loadfailed", "load_failed"):
                logger.warning("❌ 音軌載入失敗，嘗試播放下一首")
                should_auto_play = True
            elif reason == "cleanup":
                logger.info("🧹 播放器清理，跳過自動播放")
                return
            else:
                logger.info(f"❓ 其他結束原因: {payload.reason}，嘗試自動播放")
                should_auto_play = True
            
            if not should_auto_play:
                logger.info("🚫 不符合自動播放條件，結束處理")
                return
            
            # 添加小延遲避免競爭條件
            await asyncio.sleep(0.1)
            
            # 再次檢查播放器狀態
            if player.current is not None:
                logger.info("🎵 播放器已在播放其他音樂，跳過自動播放")
                return
            
            # 獲取下一首歌曲
            next_track = queue.get_next()
            logger.info(f"📋 獲取下一首歌曲: {next_track.title if next_track else '無'}")
            logger.info(f"🔁 循環模式: {queue.loop_mode} | 佇列剩餘: {len(queue.queue)} 首")
            
            # 檢查自動播放狀態 - 使用新的方法
            autoplay_status = self.get_autoplay_status(guild_id)
            logger.info(f"🤖 自動播放狀態: {'啟用' if autoplay_status else '停用'} | 伺服器: {guild_id}")
            
            # 如果沒有下一首歌曲且啟用自動播放，則添加推薦歌曲
            autoplay_attempts = 0
            max_autoplay_attempts = 3
            
            while not next_track and autoplay_status and autoplay_attempts < max_autoplay_attempts:
                autoplay_attempts += 1
                logger.info(f"🤖 自動播放嘗試 {autoplay_attempts}/{max_autoplay_attempts}：正在搜尋推薦歌曲...")
                
                try:
                    await self.auto_recommend_and_play(player)
                    # 重新獲取下一首歌曲
                    next_track = queue.get_next()
                    logger.info(f"🎯 自動播放嘗試 {autoplay_attempts} 結果: {next_track.title if next_track else '無'}")
                    
                    if next_track:
                        break
                        
                    # 如果第一次失敗，等待後重試
                    if autoplay_attempts < max_autoplay_attempts:
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    logger.error(f"❌ 自動播放嘗試 {autoplay_attempts} 失敗: {e}")
                    await asyncio.sleep(1)
            
            # 播放下一首歌曲
            if next_track:
                logger.info(f"▶️ 準備播放下一首: {next_track.title}")
                
                # 最後一次檢查播放器狀態
                if player.current is not None:
                    logger.warning("⚠️ 播放器狀態變更，已有其他音樂在播放")
                    # 將歌曲重新加入佇列前面
                    queue.queue.insert(0, next_track)
                    return
                
                try:
                    await player.play(next_track)
                    # get_next() 已經將歌曲添加到歷史記錄，這裡不需要重複添加
                    logger.info(f"✅ 成功開始播放: {next_track.title}")
                    
                    # 發送正在播放的消息到最後一個使用音樂命令的頻道
                    if hasattr(player, 'last_channel') and player.last_channel:
                        try:
                            # 短暫延遲確保播放狀態穩定
                            await asyncio.sleep(0.5)
                            embed = self.create_now_playing_embed(player, guild_id)
                            view = MusicControlView(player, self)
                            await player.last_channel.send(embed=embed, view=view)
                            logger.info("📢 已發送正在播放訊息")
                        except Exception as e:
                            logger.warning(f"⚠️ 發送正在播放訊息失敗: {e}")
                            
                except Exception as e:
                    logger.error(f"❌ 播放下一首歌曲失敗: {e}")
                    # 如果播放失敗，將歌曲重新加入佇列前面
                    queue.queue.insert(0, next_track)
                    if hasattr(player, 'last_channel') and player.last_channel:
                        try:
                            await player.last_channel.send(f"❌ 播放 **{next_track.title}** 失敗，已重新加入佇列")
                        except:
                            pass
            else:
                logger.info("🔚 佇列播放完畢，沒有更多歌曲")
                if hasattr(player, 'last_channel') and player.last_channel:
                    try:
                        embed = discord.Embed(
                            title="🔚 播放完畢",
                            description="佇列中的所有歌曲都已播放完畢",
                            color=discord.Color.orange()
                        )
                        if self.get_autoplay_status(guild_id):
                            if autoplay_attempts > 0:
                                embed.add_field(
                                    name="🤖 自動播放",
                                    value=f"已嘗試 {autoplay_attempts} 次推薦歌曲，但無法找到適合的音樂",
                                    inline=False
                                )
                            else:
                                embed.add_field(
                                    name="💡 提示",
                                    value="自動播放已啟用，但目前沒有播放歷史可用於推薦",
                                    inline=False
                                )
                        await player.last_channel.send(embed=embed)
                    except Exception as e:
                        logger.warning(f"⚠️ 發送播放完畢訊息失敗: {e}")
                        
        except Exception as e:
            logger.error(f"❌ 處理音軌結束事件時出錯: {e}", exc_info=True)
            # 嘗試恢復播放狀態
            try:
                if 'player' in locals() and 'guild_id' in locals():
                    queue = self.get_queue(guild_id)
                    if queue.queue and not player.current:
                        logger.info("🔄 嘗試恢復播放狀態...")
                        next_track = queue.get_next()
                        if next_track:
                            await player.play(next_track)
                            logger.info("✅ 播放狀態恢復成功")
            except Exception as recovery_error:
                logger.error(f"❌ 播放狀態恢復失敗: {recovery_error}")

    async def auto_recommend_and_play(self, player: wavelink.Player):
        """自動推薦並將音樂加入佇列（改進穩定性）"""
        try:
            guild_id = player.guild.id
            queue = self.get_queue(guild_id)
            
            # 更新統計
            if guild_id not in self.autoplay_stats:
                self.autoplay_stats[guild_id] = {'attempts': 0, 'successes': 0, 'last_attempt': 0}
            
            self.autoplay_stats[guild_id]['attempts'] += 1
            self.autoplay_stats[guild_id]['last_attempt'] = time.time()
            
            logger.info(f"🤖 開始自動推薦 (嘗試 #{self.autoplay_stats[guild_id]['attempts']}) - 歷史記錄: {len(queue.history)} 首")
            
            # 優化推薦策略
            recommended_track = None
            
            # 策略 1: 基於最近播放的歌曲推薦
            if queue.history and len(queue.history) >= 1:
                # 取最近 3 首歌曲進行推薦
                recent_tracks = queue.history[-3:]
                
                for track in reversed(recent_tracks):  # 從最新的開始
                    if not track.author or not track.title:
                        continue
                        
                    # 多種搜尋策略
                    search_strategies = [
                        f"{track.author}",  # 同一作者
                        f"{track.title.split()[0]} music",  # 標題關鍵字
                        f"{track.author} best songs",  # 作者熱門歌曲
                    ]
                    
                    for strategy in search_strategies:
                        try:
                            logger.info(f"🔍 搜尋策略: {strategy}")
                            tracks = await wavelink.Playable.search(strategy)
                            
                            if tracks and len(tracks) > 0:
                                # 過濾已播放的歌曲
                                played_titles = {h.title.lower() for h in queue.history[-20:]}
                                available_tracks = [
                                    t for t in tracks[:15]
                                    if t.title.lower() not in played_titles and
                                    t.length < 600000  # 限制在 10 分鐘內
                                ]
                                
                                if available_tracks:
                                    recommended_track = random.choice(available_tracks)
                                    logger.info(f"✅ 找到推薦歌曲: {recommended_track.title} (策略: {strategy})")
                                    break
                        except Exception as e:
                            logger.warning(f"⚠️ 搜尋策略 '{strategy}' 失敗: {e}")
                            continue
                    
                    if recommended_track:
                        break
            
            # 策略 2: 如果基於歷史的推薦失敗，使用通用熱門音樂
            if not recommended_track:
                logger.info("🎯 使用熱門音樂推薦")
                popular_searches = [
                    "pop music 2024",
                    "trending songs",
                    "Billboard Hot 100",
                    "popular hits",
                    "radio music"
                ]
                
                for search_term in popular_searches:
                    try:
                        tracks = await wavelink.Playable.search(search_term)
                        if tracks and len(tracks) > 0:
                            # 選擇較短的歌曲避免過長
                            suitable_tracks = [
                                t for t in tracks[:20]
                                if hasattr(t, 'length') and t.length < 480000  # 8 分鐘內
                            ]
                            
                            if suitable_tracks:
                                recommended_track = random.choice(suitable_tracks)
                                logger.info(f"✅ 找到熱門推薦: {recommended_track.title}")
                                break
                    except Exception as e:
                        logger.warning(f"⚠️ 熱門搜尋 '{search_term}' 失敗: {e}")
                        continue
            
            # 策略 3: 最後備用方案 - 簡單的音樂搜尋
            if not recommended_track:
                logger.info("🎲 使用備用推薦方案")
                backup_searches = ["music", "songs", "hits"]
                
                for term in backup_searches:
                    try:
                        tracks = await wavelink.Playable.search(term)
                        if tracks:
                            recommended_track = random.choice(tracks[:5])
                            logger.info(f"✅ 備用推薦: {recommended_track.title}")
                            break
                    except:
                        continue
            
            # 將推薦歌曲加入佇列
            if recommended_track:
                queue.add(recommended_track)
                logger.info(f"📋 已將推薦歌曲加入佇列: {recommended_track.title}")
                
                # 發送推薦通知（非阻塞）
                if hasattr(player, 'last_channel') and player.last_channel:
                    try:
                        # 根據推薦來源顯示不同訊息
                        if queue.history:
                            base_track = queue.history[-1]
                            description = f"基於「**{base_track.title}**」為你推薦: **{recommended_track.title}**"
                        else:
                            description = f"為你推薦熱門音樂: **{recommended_track.title}**"
                        
                        embed = discord.Embed(
                            title="🤖 自動播放推薦",
                            description=description,
                            color=discord.Color.purple()
                        )
                        
                        if hasattr(recommended_track, 'author') and recommended_track.author:
                            embed.add_field(name="👤 作者", value=recommended_track.author, inline=True)
                        
                        if hasattr(recommended_track, 'length'):
                            duration = self.format_duration(recommended_track.length)
                            embed.add_field(name="⏱️ 長度", value=duration, inline=True)
                        
                        # 非同步發送，避免阻塞
                        asyncio.create_task(player.last_channel.send(embed=embed))
                        
                    except Exception as e:
                        logger.warning(f"⚠️ 發送推薦通知失敗: {e}")
                
                return True
            else:
                logger.warning("❌ 所有推薦策略都失敗了")
                return False
                
        except Exception as e:
            logger.error(f"❌ 自動播放推薦失敗: {e}", exc_info=True)
            return False

    @commands.hybrid_command()
    async def join(self, ctx):
        """讓機器人加入語音頻道"""
        await ctx.defer()

        if not ctx.author.voice:
            await ctx.send("❌ 你必須先加入語音頻道。")
            return

        channel = ctx.author.voice.channel

        # ── Lavalink 健康檢查 ──────────────────────────────────────
        connected_nodes = [
            n for n in wavelink.Pool.nodes.values()
            if n.status == wavelink.NodeStatus.CONNECTED
        ]
        logger.info(
            f"[join] guild={ctx.guild.id} | target={channel.name} | "
            f"nodes_total={len(wavelink.Pool.nodes)} | nodes_ok={len(connected_nodes)}"
        )
        if not connected_nodes:
            await ctx.send("⚠️ Lavalink 尚未就緒，正在重新連接，請稍後再試...")
            await self.connect_to_lavalink()
            return
        # ─────────────────────────────────────────────────────────────

        if ctx.voice_client:
            logger.info(f"[join] 已在頻道，移動到 {channel.name}")
            await ctx.voice_client.move_to(channel)
            await ctx.send(f"✅ 已移動到語音頻道：{channel.name}")
        else:
            for attempt in range(3):
                server_before = lavalink_manager.current_server if lavalink_manager else None
                try:
                    logger.info(
                        f"[join] 嘗試 #{attempt+1} 連線到 {channel.name} "
                        f"(guild={ctx.guild.id}, node={list(wavelink.Pool.nodes.keys())})"
                    )
                    player: wavelink.Player = await channel.connect(
                        cls=wavelink.Player, self_deaf=True, timeout=10.0
                    )
                    player.last_channel = ctx.channel
                    logger.info(f"[join] 連線成功: {channel.name} | node={player.node.identifier}")
                    await ctx.send(f"✅ 已加入語音頻道：{channel.name}")
                    return
                except Exception as e:
                    logger.error(f"[join] 嘗試 #{attempt+1} 失敗: {e}", exc_info=True)
                    if attempt < 2:
                        # 檢查快速斷線處理器是否已切換伺服器
                        already_switched = (
                            lavalink_manager and
                            lavalink_manager.current_server is not None and
                            lavalink_manager.current_server != server_before
                        )
                        if already_switched:
                            logger.info("[join] 快速斷線已切換伺服器，直接重試...")
                            await asyncio.sleep(1)
                        else:
                            if lavalink_manager and lavalink_manager.current_server:
                                lavalink_manager.current_server.status = "voice_fail"
                                lavalink_manager.current_server.error_count += 5
                            switched = await self.switch_lavalink_server()
                            if not switched:
                                await ctx.send("❌ 找不到其他可用的 Lavalink 伺服器，無法連接。")
                                return
                            await asyncio.sleep(1)
                    else:
                        await ctx.send(
                            f"❌ 三次嘗試均失敗，請稍後再試。\n"
                            f"最後錯誤: `{e}`"
                        )

    @commands.hybrid_command()
    async def play(self, ctx, *, search: str):
        """播放音樂"""
        await ctx.defer()
        
        try:
            # 檢查 Wavelink 節點連接
            if not wavelink.Pool.nodes:
                await ctx.send("❌ 音樂服務暫時不可用，正在嘗試重新連接...")
                if await self.connect_to_lavalink():
                    await ctx.send("✅ 音樂服務已恢復，請重試")
                return
                
            if not ctx.author.voice:
                await ctx.send("❌ 你必須先加入語音頻道。")
                return

            if not ctx.voice_client:
                vc_channel = ctx.author.voice.channel
                connected = False
                for attempt in range(3):
                    server_before = lavalink_manager.current_server if lavalink_manager else None
                    try:
                        logger.info(
                            f"[play] 嘗試 #{attempt+1} 連線到 {vc_channel.name} "
                            f"(node={list(wavelink.Pool.nodes.keys())})"
                        )
                        player = await vc_channel.connect(
                            cls=wavelink.Player, self_deaf=True, timeout=10.0
                        )
                        player.last_channel = ctx.channel
                        logger.info(f"[play] 語音連線成功 | node={player.node.identifier}")
                        connected = True
                        break
                    except Exception as e:
                        logger.error(f"[play] 嘗試 #{attempt+1} 失敗: {e}", exc_info=True)
                        if attempt < 2:
                            already_switched = (
                                lavalink_manager and
                                lavalink_manager.current_server is not None and
                                lavalink_manager.current_server != server_before
                            )
                            if already_switched:
                                logger.info("[play] 快速斷線已切換伺服器，直接重試...")
                                await asyncio.sleep(1)
                            else:
                                if lavalink_manager and lavalink_manager.current_server:
                                    lavalink_manager.current_server.status = "voice_fail"
                                    lavalink_manager.current_server.error_count += 5
                                switched = await self.switch_lavalink_server()
                                if not switched:
                                    await ctx.send("❌ 無法切換 Lavalink 伺服器，請稍後再試。")
                                    return
                                await asyncio.sleep(1)
                        else:
                            await ctx.send(f"❌ 無法連接到語音頻道（三次嘗試均失敗）: `{e}`")
                            return
                if not connected:
                    return
            else:
                player: wavelink.Player = ctx.voice_client
                player.last_channel = ctx.channel

            # 增強的搜尋邏輯，支援自動重試和伺服器切換
            max_retries = 3
            tracks = None
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"🔍 嘗試搜尋音樂 (第 {attempt + 1} 次): {search}")
                    tracks = await wavelink.Playable.search(search)
                    if tracks:
                        logger.info(f"✅ 成功找到 {len(tracks)} 首歌曲")
                        break
                    else:
                        logger.warning(f"⚠️ 第 {attempt + 1} 次搜尋未找到結果")
                        
                except Exception as e:
                    logger.warning(f"⚠️ 第 {attempt + 1} 次搜尋失敗: {e}")
                    
                    # 如果是 Lavalink 相關錯誤，嘗試切換伺服器
                    if "Failed to Load Tracks" in str(e) or "FriendlyException" in str(e):
                        logger.info("🔄 檢測到 Lavalink 搜尋錯誤，嘗試切換伺服器...")
                        if await self.switch_lavalink_server():
                            logger.info("✅ 已切換伺服器，將重試搜尋")
                            await asyncio.sleep(1)  # 等待連接穩定
                            continue
                        else:
                            logger.error("❌ 伺服器切換失敗")
                    
                    # 如果是最後一次嘗試，拋出異常
                    if attempt == max_retries - 1:
                        raise
                    
                    # 短暫等待後重試
                    await asyncio.sleep(2)
            
            if not tracks:
                await ctx.send("❌ 找不到相關音樂。可能是搜尋服務暫時不可用，請稍後再試。")
                return

            # 若多於1首，顯示搜尋選單
            if len(tracks) > 1:
                class SearchResultSelect(discord.ui.Select):
                    def __init__(self, tracks, music_cog, ctx):
                        options = [
                            discord.SelectOption(
                                label=track.title[:100],
                                description=(getattr(track, 'author', 'Unknown') + f" | {music_cog.format_duration(track.length)}")[:100],
                                value=str(i)
                            )
                            for i, track in enumerate(tracks[:10])
                        ]
                        super().__init__(placeholder="請選擇要播放的音樂", min_values=1, max_values=1, options=options)
                        self.tracks = tracks
                        self.music_cog = music_cog
                        self.ctx = ctx

                    async def callback(self, interaction: discord.Interaction):
                        index = int(self.values[0])
                        track = self.tracks[index]
                        player: wavelink.Player = self.ctx.voice_client
                        if not player:
                            await interaction.response.send_message("❌ 機器人未在語音頻道中。", ephemeral=True)
                            return
                        queue = self.music_cog.get_queue(self.ctx.guild.id)
                        if player.current:
                            queue.add(track)
                            await interaction.response.send_message(f"✅ 已加入佇列: **{track.title}**")
                        else:
                            await player.play(track)
                            # 將直接播放的歌曲添加到歷史記錄
                            queue.add_to_history(track)
                            embed = self.music_cog.create_now_playing_embed(player, self.ctx.guild.id)
                            view = MusicControlView(player, self.music_cog)
                            await interaction.response.send_message(embed=embed, view=view)

                class SearchResultView(discord.ui.View):
                    def __init__(self, tracks, music_cog, ctx):
                        super().__init__(timeout=60)
                        self.add_item(SearchResultSelect(tracks, music_cog, ctx))

                embed = discord.Embed(
                    title="🔍 搜索結果",
                    description=f"請從下方選單選擇要播放的音樂\n\n搜索關鍵字: **{search}**",
                    color=discord.Color.blue()
                )
                for i, track in enumerate(tracks[:10], 1):
                    duration = self.format_duration(track.length) if hasattr(track, 'length') else "未知"
                    author = getattr(track, 'author', 'Unknown')
                    embed.add_field(
                        name=f"{i}. {track.title}",
                        value=f"👤 {author} | ⏱️ {duration}",
                        inline=False
                    )
                view = SearchResultView(tracks, self, ctx)
                await ctx.send(embed=embed, view=view)
                return

            # 僅一首，維持原本流程
            track = tracks[0]
            queue = self.get_queue(ctx.guild.id)

            if player.current:
                queue.add(track)
                embed = discord.Embed(
                    title="📋 已加入佇列",
                    description=f"**{track.title}**",
                    color=discord.Color.blue()
                )
                embed.add_field(name="位置", value=f"第 {len(queue.queue)} 首", inline=True)
                await ctx.send(embed=embed)
            else:
                try:
                    await player.play(track)
                    # 將直接播放的歌曲添加到歷史記錄
                    queue.add_to_history(track)
                    embed = self.create_now_playing_embed(player, ctx.guild.id)
                    view = MusicControlView(player, self)
                    await ctx.send(embed=embed, view=view)
                except Exception as e:
                    logger.error(f"播放音樂失敗: {e}")
                    # 將歌曲加入佇列而不是直接播放
                    queue.add(track)
                    embed = discord.Embed(
                        title="⚠️ 播放失敗",
                        description=f"無法直接播放 **{track.title}**，已加入佇列",
                        color=discord.Color.orange()
                    )
                    embed.add_field(
                        name="📋 佇列狀態",
                        value=f"目前佇列中有 {len(queue.queue)} 首歌曲",
                        inline=True
                    )
                    embed.add_field(
                        name="💡 下一步",
                        value="使用 `/next` 命令開始播放佇列中的歌曲",
                        inline=True
                    )
                    await ctx.send(embed=embed)

        except LavalinkException as e:
            logger.error(f"Lavalink 錯誤: {e}")
            # 嘗試切換伺服器
            if await self.switch_lavalink_server():
                await ctx.send("🔄 已切換到新的音樂伺服器，請重試播放命令")
            else:
                await ctx.send("❌ 音樂服務錯誤: 無法播放此音樂，請稍後再試")
        except Exception as e:
            await ctx.send(f"❌ 播放音樂時出錯: {e}")
            logger.error(f"播放音樂時出錯: {e}")

    @commands.hybrid_command()
    async def nowplaying(self, ctx):
        """顯示當前播放的音樂"""
        player: wavelink.Player = ctx.voice_client
        if not player:
            await ctx.send("❌ 機器人未在語音頻道中。")
            return
            
        embed = self.create_now_playing_embed(player, ctx.guild.id)
        view = MusicControlView(player, self)
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command()
    async def queue(self, ctx, page: int = 1):
        """顯示播放佇列"""
        embed = self.create_queue_embed(ctx.guild.id, page - 1)
        view = PlaylistView(self, ctx.guild.id)
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command()
    async def volume(self, ctx, vol: int = None):
        """調整音量或顯示音量控制面板"""
        player: wavelink.Player = ctx.voice_client
        if not player:
            await ctx.send("❌ 機器人未在語音頻道中。")
            return
            
        if vol is None:
            embed = discord.Embed(
                title="🔊 音量控制",
                description=f"當前音量: **{player.volume}%**",
                color=discord.Color.blue()
            )
            view = VolumeView(player)
            await ctx.send(embed=embed, view=view)
        else:
            if not 0 <= vol <= 100:
                await ctx.send("❌ 音量必須在 0-100 之間。")
                return
                
            await player.set_volume(vol)
            await ctx.send(f"🔊 音量已設置為: {vol}%")

    @commands.hybrid_command()
    async def autoplay(self, ctx, enable: bool = None):
        """開啟/關閉自動播放"""
        if enable is None:
            current = self.get_autoplay_status(ctx.guild.id)
            self.set_autoplay_status(ctx.guild.id, not current)
            status = "開啟" if not current else "關閉"
        else:
            self.set_autoplay_status(ctx.guild.id, enable)
            status = "開啟" if enable else "關閉"
        
        embed = discord.Embed(
            title="🤖 自動播放",
            description=f"自動播放已{status}",
            color=discord.Color.green() if self.get_autoplay_status(ctx.guild.id) else discord.Color.red()
        )
        if self.get_autoplay_status(ctx.guild.id):
            embed.add_field(
                name="功能說明",
                value="當佇列播放完畢時，會自動根據播放歷史推薦相似音樂",
                inline=False
            )
        await ctx.send(embed=embed)

    @commands.hybrid_command()
    async def next(self, ctx):
        """播放佇列中的下一首歌曲"""
        player: wavelink.Player = ctx.voice_client
        if not player:
            await ctx.send("❌ 機器人未在語音頻道中。")
            return
        
        queue = self.get_queue(ctx.guild.id)
        if not queue.queue:
            await ctx.send("❌ 播放佇列是空的。")
            return
        
        try:
            next_track = queue.get_next()
            if next_track:
                await player.play(next_track)
                # get_next() 已經將歌曲添加到歷史記錄，這裡不需要重複添加
                embed = self.create_now_playing_embed(player, ctx.guild.id)
                view = MusicControlView(player, self)
                await ctx.send(embed=embed, view=view)
            else:
                await ctx.send("❌ 佇列中沒有可播放的音樂。")
        except Exception as e:
            logger.error(f"播放下一首失敗: {e}")
            await ctx.send(f"❌ 播放失敗: {e}")

    @commands.hybrid_command()
    async def skip(self, ctx, amount: int = 1):
        """跳過音樂"""
        player: wavelink.Player = ctx.voice_client
        if not player or not player.current:
            await ctx.send("❌ 沒有正在播放的音樂。")
            return
        
        queue = self.get_queue(ctx.guild.id)
        
        if amount > 1:
            # 跳過多首
            skipped = 0
            for _ in range(amount - 1):
                if queue.queue:
                    queue.queue.pop(0)
                    skipped += 1
                else:
                    break
            
            await player.stop()
            await ctx.send(f"⏭️ 已跳過 {skipped + 1} 首歌曲")
        else:
            await player.stop()
            await ctx.send("⏭️ 已跳過當前音樂")
            
        # 確保停止後能自動播放下一首
        logger.info(f"🔧 Skip 命令執行完成，停止當前播放器以觸發自動播放")

    @commands.hybrid_command()
    async def back(self, ctx):
        """播放上一首歌曲"""
        player: wavelink.Player = ctx.voice_client
        if not player:
            await ctx.send("❌ 機器人未在語音頻道中。")
            return
        
        queue = self.get_queue(ctx.guild.id)
        if len(queue.history) < 2:
            await ctx.send("❌ 沒有上一首歌曲。")
            return
        
        # 獲取上一首歌曲（倒數第二首）
        previous_track = queue.history[-2]
        
        # 將當前歌曲和上一首歌曲重新加入佇列前面
        if player.current:
            queue.queue.insert(0, player.current)
        queue.queue.insert(0, previous_track)
        
        # 移除歷史記錄中的最後一首
        queue.history.pop()
        
        await player.stop()
        await ctx.send("⏮️ 已返回上一首歌曲")

    @commands.hybrid_command()
    async def remove(self, ctx, index: int):
        """從佇列中移除指定音樂"""
        queue = self.get_queue(ctx.guild.id)
        
        if queue.remove(index - 1):
            await ctx.send(f"✅ 已移除佇列中第 {index} 首歌曲")
        else:
            await ctx.send(f"❌ 佇列中沒有第 {index} 首歌曲")

    @commands.hybrid_command()
    async def move(self, ctx, from_pos: int, to_pos: int):
        """移動佇列中歌曲的位置"""
        queue = self.get_queue(ctx.guild.id)
        
        if not (1 <= from_pos <= len(queue.queue) and 1 <= to_pos <= len(queue.queue)):
            await ctx.send("❌ 位置超出佇列範圍")
            return
        
        # 移動歌曲
        track = queue.queue.pop(from_pos - 1)
        queue.queue.insert(to_pos - 1, track)
        
        await ctx.send(f"✅ 已將第 {from_pos} 首歌曲移動到第 {to_pos} 位")

    @commands.hybrid_command()
    async def clear(self, ctx):
        """清空播放佇列"""
        queue = self.get_queue(ctx.guild.id)
        queue.clear()
        await ctx.send("🗑️ 已清空播放佇列")

    @commands.hybrid_command()
    async def shuffle(self, ctx):
        """切換隨機播放"""
        queue = self.get_queue(ctx.guild.id)
        queue.toggle_shuffle()
        status = "開啟" if queue.shuffle else "關閉"
        await ctx.send(f"🔀 隨機播放已{status}")

    @commands.hybrid_command()
    async def loop(self, ctx, mode: str = None):
        """設置循環模式 (off/track/queue)"""
        queue = self.get_queue(ctx.guild.id)
        
        if mode is None:
            modes = {"off": "queue", "queue": "track", "track": "off"}
            new_mode = modes[queue.loop_mode]
        else:
            if mode.lower() not in ["off", "track", "queue"]:
                await ctx.send("❌ 循環模式必須是 off、track 或 queue")
                return
            new_mode = mode.lower()
        
        queue.set_loop_mode(new_mode)
        mode_text = {"off": "關閉", "queue": "佇列循環", "track": "單曲循環"}
        await ctx.send(f"🔁 循環模式: {mode_text[new_mode]}")

    @commands.hybrid_command()
    async def pause(self, ctx):
        """暫停播放"""
        player: wavelink.Player = ctx.voice_client
        if not player or not player.current:
            await ctx.send("❌ 沒有正在播放的音樂。")
            return
        
        if player.paused:
            await ctx.send("⏸️ 音樂已經暫停了。")
        else:
            await player.pause(True)
            await ctx.send("⏸️ 已暫停播放")

    @commands.hybrid_command()
    async def resume(self, ctx):
        """繼續播放"""
        player: wavelink.Player = ctx.voice_client
        if not player or not player.current:
            await ctx.send("❌ 沒有正在播放的音樂。")
            return
        
        if not player.paused:
            await ctx.send("▶️ 音樂沒有暫停。")
        else:
            await player.pause(False)
            await ctx.send("▶️ 已繼續播放")

    @commands.hybrid_command()
    async def stop(self, ctx):
        """停止播放並離開語音頻道"""
        player: wavelink.Player = ctx.voice_client
        if not player:
            await ctx.send("❌ 機器人未在語音頻道中。")
            return

        queue = self.get_queue(ctx.guild.id)
        queue.clear()
        self._user_stopped.add(ctx.guild.id)   # 標記為使用者主動停止，避免快速斷線誤判

        try:
            await player.disconnect()
            await ctx.send("⏹️ 已停止播放並離開語音頻道")
        except LavalinkException as e:
            logger.warning(f"⚠️ 斷線時 Lavalink 錯誤 (可忽略): {e}")
            await ctx.send("⏹️ 已停止播放並離開語音頻道")
        except Exception as e:
            logger.error(f"❌ 斷線時出錯: {e}")
            await ctx.send("⚠️ 已嘗試停止播放，可能需要手動離開語音頻道")

    @commands.hybrid_command()
    async def seek(self, ctx, position: str):
        """跳轉到指定時間位置 (格式: mm:ss 或 秒數)"""
        player: wavelink.Player = ctx.voice_client
        if not player or not player.current:
            await ctx.send("❌ 沒有正在播放的音樂。")
            return
        
        try:
            # 解析時間格式
            if ":" in position:
                parts = position.split(":")
                if len(parts) == 2:
                    minutes, seconds = map(int, parts)
                    seek_ms = (minutes * 60 + seconds) * 1000
                elif len(parts) == 3:
                    hours, minutes, seconds = map(int, parts)
                    seek_ms = (hours * 3600 + minutes * 60 + seconds) * 1000
                else:
                    raise ValueError
            else:
                seek_ms = int(position) * 1000
            
            if seek_ms < 0 or seek_ms > player.current.length:
                await ctx.send("❌ 時間位置超出歌曲長度")
                return
            
            await player.seek(seek_ms)
            formatted_time = self.format_duration(seek_ms)
            await ctx.send(f"⏩ 已跳轉到 {formatted_time}")
            
        except ValueError:
            await ctx.send("❌ 時間格式錯誤，請使用 mm:ss 或秒數格式")

    @commands.hybrid_command()
    async def lyrics(self, ctx, *, query: str = None):
        """搜索歌詞"""
        player: wavelink.Player = ctx.voice_client
        
        if query is None:
            if not player or not player.current:
                await ctx.send("❌ 請提供歌曲名稱或確保有音樂正在播放")
                return
            query = f"{player.current.title} {getattr(player.current, 'author', '')}"
        
        # 這裡可以整合歌詞 API，目前只是示例
        embed = discord.Embed(
            title="🎤 歌詞搜索",
            description=f"正在搜索 '{query}' 的歌詞...",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="提示",
            value="歌詞功能需要整合第三方 API，目前暫未實現",
            inline=False
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command()
    async def playlist(self, ctx, action: str = None, *, name: str = None):
        """播放列表管理"""
        if action is None:
            # 顯示播放列表管理面板
            user_id = str(ctx.author.id)
            embed = discord.Embed(
                title="📚 播放列表管理",
                color=discord.Color.blue()
            )
            
            if user_id in self.saved_playlists and self.saved_playlists[user_id]:
                playlist_list = ""
                for playlist_name, tracks in self.saved_playlists[user_id].items():
                    playlist_list += f"• **{playlist_name}** ({len(tracks)} 首歌曲)\n"
                embed.add_field(name="你的播放列表", value=playlist_list, inline=False)
            else:
                embed.add_field(name="你的播放列表", value="暫無播放列表", inline=False)
            
            embed.add_field(
                name="使用方法",
                value=(
                    f"`{ctx.prefix}playlist save <名稱>` - 儲存目前佇列\n"
                    f"`{ctx.prefix}playlist load <名稱>` - 載入播放列表\n"
                    f"`{ctx.prefix}playlist delete <名稱>` - 刪除播放列表\n"
                    f"`{ctx.prefix}playlist list` - 列出所有播放列表"
                ),
                inline=False
            )
            
            view = SavedPlaylistView(self, ctx.author.id)
            await ctx.send(embed=embed, view=view)
            
        elif action.lower() == "save":
            if not name:
                await ctx.send("❌ 請提供播放列表名稱")
                return
            
            queue = self.get_queue(ctx.guild.id)
            if not queue.queue:
                await ctx.send("❌ 目前佇列是空的")
                return
            
            user_id = str(ctx.author.id)
            if user_id not in self.saved_playlists:
                self.saved_playlists[user_id] = {}
            
            # 儲存播放列表
            playlist_data = []
            for track in queue.queue:
                playlist_data.append({
                    "title": track.title,
                    "uri": track.uri,
                    "author": getattr(track, 'author', 'Unknown')
                })
            
            self.saved_playlists[user_id][name] = playlist_data
            self.save_playlists()
            
            await ctx.send(f"✅ 播放列表 '{name}' 已儲存 ({len(playlist_data)} 首歌曲)")
            
        elif action.lower() == "load":
            if not name:
                await ctx.send("❌ 請提供播放列表名稱")
                return
            
            user_id = str(ctx.author.id)
            if user_id not in self.saved_playlists or name not in self.saved_playlists[user_id]:
                await ctx.send(f"❌ 找不到播放列表 '{name}'")
                return
            
            playlist_data = self.saved_playlists[user_id][name]
            queue = self.get_queue(ctx.guild.id)
            
            loading_msg = await ctx.send(f"📥 正在載入播放列表 '{name}'...")
            
            loaded_count = 0
            for track_data in playlist_data:
                try:
                    tracks = await wavelink.Playable.search(track_data["uri"])
                    if tracks:
                        queue.add(tracks[0])
                        loaded_count += 1
                except:
                    continue
            
            await loading_msg.edit(content=f"✅ 已載入播放列表 '{name}' ({loaded_count}/{len(playlist_data)} 首歌曲)")
            
        elif action.lower() == "delete":
            if not name:
                await ctx.send("❌ 請提供播放列表名稱")
                return
            
            user_id = str(ctx.author.id)
            if user_id not in self.saved_playlists or name not in self.saved_playlists[user_id]:
                await ctx.send(f"❌ 找不到播放列表 '{name}'")
                return
            
            del self.saved_playlists[user_id][name]
            self.save_playlists()
            await ctx.send(f"🗑️ 已刪除播放列表 '{name}'")
            
        elif action.lower() == "list":
            user_id = str(ctx.author.id)
            embed = discord.Embed(
                title="📚 你的播放列表",
                color=discord.Color.blue()
            )
            
            if user_id in self.saved_playlists and self.saved_playlists[user_id]:
                for playlist_name, tracks in self.saved_playlists[user_id].items():
                    embed.add_field(
                        name=playlist_name,
                        value=f"{len(tracks)} 首歌曲",
                        inline=True
                    )
            else:
                embed.description = "你還沒有任何播放列表"
            
            await ctx.send(embed=embed)

    @commands.hybrid_command()
    async def search(self, ctx, *, query: str):
        """搜索音樂並顯示結果"""
        if not wavelink.Pool.nodes:
            await ctx.send("❌ 音樂服務暫時不可用")
            return

        class SearchResultSelect(discord.ui.Select):
            def __init__(self, tracks, music_cog, ctx):
                options = [
                    discord.SelectOption(
                        label=track.title[:100],
                        description=(getattr(track, 'author', 'Unknown') + f" | {music_cog.format_duration(track.length)}")[:100],
                        value=str(i)
                    )
                    for i, track in enumerate(tracks[:10])
                ]
                super().__init__(placeholder="請選擇要播放的音樂", min_values=1, max_values=1, options=options)
                self.tracks = tracks
                self.music_cog = music_cog
                self.ctx = ctx

            async def callback(self, interaction: discord.Interaction):
                index = int(self.values[0])
                track = self.tracks[index]
                player: wavelink.Player = self.ctx.voice_client
                if not player:
                    await interaction.response.send_message("❌ 機器人未在語音頻道中。", ephemeral=True)
                    return
                queue = self.music_cog.get_queue(self.ctx.guild.id)
                if player.current:
                    queue.add(track)
                    await interaction.response.send_message(f"✅ 已加入佇列: **{track.title}**", ephemeral=True)
                else:
                    await player.play(track)
                    # 將直接播放的歌曲添加到歷史記錄
                    queue.add_to_history(track)
                    embed = self.music_cog.create_now_playing_embed(player, self.ctx.guild.id)
                    view = MusicControlView(player, self.music_cog)
                    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        class SearchResultView(discord.ui.View):
            def __init__(self, tracks, music_cog, ctx):
                super().__init__(timeout=60)
                self.add_item(SearchResultSelect(tracks, music_cog, ctx))

        try:
            tracks = await wavelink.Playable.search(query)
            if not tracks:
                await ctx.send("❌ 找不到相關音樂")
                return

            embed = discord.Embed(
                title="🔍 搜索結果",
                description=f"請從下方選單選擇要播放的音樂\n\n搜索關鍵字: **{query}**",
                color=discord.Color.blue()
            )
            for i, track in enumerate(tracks[:10], 1):
                duration = self.format_duration(track.length) if hasattr(track, 'length') else "未知"
                author = getattr(track, 'author', 'Unknown')
                embed.add_field(
                    name=f"{i}. {track.title}",
                    value=f"👤 {author} | ⏱️ {duration}",
                    inline=False
                )
            view = SearchResultView(tracks, self, ctx)
            await ctx.send(embed=embed, view=view)
        except Exception as e:
            await ctx.send(f"❌ 搜索時出錯: {e}")

    @commands.hybrid_command()
    async def history(self, ctx, page: int = 1):
        """顯示播放歷史"""
        queue = self.get_queue(ctx.guild.id)
        
        if not queue.history:
            await ctx.send("📜 播放歷史是空的")
            return
        
        items_per_page = 10
        start = (page - 1) * items_per_page
        end = start + items_per_page
        page_items = list(reversed(queue.history))[start:end]  # 最新的在前面
        
        embed = discord.Embed(
            title="📜 播放歷史",
            color=discord.Color.purple()
        )
        
        description = ""
        for i, track in enumerate(page_items, start + 1):
            duration = self.format_duration(track.length) if hasattr(track, 'length') else "未知"
            description += f"`{i}.` **{track.title}** ({duration})\n"
        
        embed.description = description
        
        total_pages = (len(queue.history) - 1) // items_per_page + 1
        embed.set_footer(text=f"頁面 {page}/{total_pages} • 總共 {len(queue.history)} 首歌曲")
        
        await ctx.send(embed=embed)

    @commands.hybrid_command()
    async def stats(self, ctx):
        """顯示音樂統計"""
        try:
            queue = self.get_queue(ctx.guild.id)
            player: wavelink.Player = ctx.voice_client
            
            embed = self.create_stats_embed(queue, player, ctx.guild.id)
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"執行 stats 指令時出錯: {e}")
            try:
                await ctx.send("❌ 無法顯示音樂統計，請稍後再試")
            except:
                logger.error(f"無法發送 stats 指令的錯誤訊息: {e}")
    
    def create_stats_embed(self, queue, player, guild_id):
        """創建統計嵌入"""
        embed = discord.Embed(
            title="📊 音樂統計",
            color=discord.Color.gold()
        )
        
        # 基本統計
        embed.add_field(name="📋 佇列中歌曲", value=len(queue.queue), inline=True)
        embed.add_field(name="📜 歷史記錄", value=len(queue.history), inline=True)
        embed.add_field(name="🔁 循環模式", value=queue.loop_mode, inline=True)
        
        # 播放器狀態
        if player:
            embed.add_field(name="🔊 音量", value=f"{player.volume}%", inline=True)
            embed.add_field(name="⏸️ 暫停狀態", value="是" if player.paused else "否", inline=True)
            
            if player.current:
                progress = (player.position / player.current.length) * 100
                embed.add_field(name="⏱️ 播放進度", value=f"{progress:.1f}%", inline=True)
        
        # 設置狀態
        embed.add_field(name="🔀 隨機播放", value="開啟" if queue.shuffle else "關閉", inline=True)
        embed.add_field(name="🤖 自動播放", value="開啟" if self.get_autoplay_status(guild_id) else "關閉", inline=True)
        
        # 計算總播放時間
        if queue.history:
            total_duration = sum(getattr(track, 'length', 0) for track in queue.history)
            embed.add_field(name="⏰ 總播放時間", value=self.format_duration(total_duration), inline=True)
        
        return embed


    @commands.hybrid_command()
    @commands.is_owner()
    async def switch_server(self, ctx):
        """手動切換 Lavalink 伺服器（僅限擁有者）"""
        msg = await ctx.send("🔄 正在切換 Lavalink 伺服器...")
        
        if await self.switch_lavalink_server():
            await msg.edit(content="✅ 已成功切換到新的 Lavalink 伺服器")
        else:
            await msg.edit(content="❌ 切換伺服器失敗，請檢查日誌獲取詳細資訊")

    @commands.hybrid_command()
    @commands.is_owner()
    async def update_servers(self, ctx):
        """更新 Lavalink 伺服器清單（僅限擁有者）"""
        if not lavalink_manager:
            await ctx.send("❌ Lavalink 伺服器管理器未啟用")
            return
        
        msg = await ctx.send("📡 正在更新 Lavalink 伺服器清單...")
        
        try:
            await lavalink_manager.update_server_list(force=True)
            status = lavalink_manager.get_server_status_summary()
            await msg.edit(content=f"✅ 伺服器清單更新完成！找到 {status['total']} 個伺服器")
        except Exception as e:
            logger.error(f"更新伺服器清單失敗: {e}")
            await msg.edit(content=f"❌ 更新失敗: {e}")

    @commands.hybrid_command()
    async def preview_next(self, ctx):
        """預覽自動播放會推薦的下一首歌曲"""
        try:
            guild_id = ctx.guild.id
            queue = self.get_queue(guild_id)
            
            # 檢查是否啟用自動播放
            if not self.get_autoplay_status(guild_id):
                embed = discord.Embed(
                    title="🤖 自動播放預覽",
                    description="自動播放功能已關閉，無法預覽推薦歌曲",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="💡 提示",
                    value="使用 `/autoplay true` 開啟自動播放功能",
                    inline=False
                )
                await ctx.send(embed=embed)
                return
            
            # 檢查佇列狀態 - 如果有歌曲在佇列中，不會觸發自動推薦
            player: wavelink.Player = ctx.voice_client
            if queue.queue:
                embed = discord.Embed(
                    title="🤖 自動播放預覽",
                    description="佇列中還有歌曲，不會觸發自動推薦",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="📋 佇列狀態",
                    value=f"還有 {len(queue.queue)} 首歌曲待播放",
                    inline=True
                )
                embed.add_field(
                    name="🔮 預覽時機",
                    value="當佇列播放完畢時才會觸發自動推薦",
                    inline=True
                )
                await ctx.send(embed=embed)
                return
            
            # 檢查機器人是否正在播放音樂
            if player and player.current:
                embed = discord.Embed(
                    title="🤖 自動播放預覽",
                    description="目前正在播放音樂，自動推薦會在歌曲結束後觸發",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="🎵 當前播放",
                    value=f"**{player.current.title}**",
                    inline=True
                )
                embed.add_field(
                    name="🔮 預覽時機",
                    value="當前歌曲播放完畢後會觸發自動推薦",
                    inline=True
                )
                await ctx.send(embed=embed)
                return
            
            # 檢查播放歷史
            if not queue.history:
                embed = discord.Embed(
                    title="🤖 自動播放預覽",
                    description="沒有播放歷史，無法生成個人化推薦",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="🎯 推薦策略",
                    value="將使用熱門音樂推薦",
                    inline=True
                )
                embed.add_field(
                    name="💡 建議",
                    value="播放幾首歌曲後再使用此功能可獲得更好的推薦",
                    inline=True
                )
                await ctx.send(embed=embed)
                return
            
            # 生成推薦預覽
            await ctx.defer()
            
            embed = discord.Embed(
                title="🔮 自動播放推薦預覽",
                description="正在分析你的播放歷史並生成推薦...",
                color=discord.Color.purple()
            )
            preview_msg = await ctx.send(embed=embed)
            
            # 模擬推薦過程
            recommendations = await self.generate_recommendation_preview(queue)
            
            if recommendations:
                embed = discord.Embed(
                    title="🔮 自動播放推薦預覽",
                    description="基於你的播放歷史，以下是可能的推薦歌曲：",
                    color=discord.Color.purple()
                )
                
                # 顯示基準歌曲
                if queue.history:
                    base_track = queue.history[-1]
                    embed.add_field(
                        name="🎵 基於歌曲",
                        value=f"**{base_track.title}**\n👤 {getattr(base_track, 'author', 'Unknown')}",
                        inline=False
                    )
                
                # 顯示推薦歌曲
                for i, track in enumerate(recommendations[:5], 1):
                    duration = self.format_duration(track.length) if hasattr(track, 'length') else "未知"
                    author = getattr(track, 'author', 'Unknown')
                    embed.add_field(
                        name=f"🎯 推薦 {i}",
                        value=f"**{track.title}**\n👤 {author} | ⏱️ {duration}",
                        inline=True
                    )
                
                embed.add_field(
                    name="📝 說明",
                    value="這只是預覽，實際推薦可能會有所不同",
                    inline=False
                )
                
                # 添加統計資訊
                embed.set_footer(text=f"基於 {len(queue.history)} 首歷史記錄生成 | 找到 {len(recommendations)} 個推薦")
                
                await preview_msg.edit(embed=embed)
            else:
                embed = discord.Embed(
                    title="🔮 自動播放推薦預覽",
                    description="❌ 無法生成推薦預覽",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="可能原因",
                    value="• 網路連線問題\n• 音樂服務暫時不可用\n• 播放歷史不足",
                    inline=False
                )
                await preview_msg.edit(embed=embed)
                
        except Exception as e:
            logger.error(f"預覽推薦時出錯: {e}")
            await ctx.send(f"❌ 預覽推薦時出錯: {e}")
    
    async def generate_recommendation_preview(self, queue):
        """生成推薦預覽（不影響實際佇列）"""
        try:
            recommendations = []
            
            if queue.history and len(queue.history) >= 1:
                # 取最近 3 首歌曲進行推薦
                recent_tracks = queue.history[-3:]
                
                for track in reversed(recent_tracks):
                    if not track.author or not track.title:
                        continue
                        
                    # 使用相同的推薦策略
                    search_strategies = [
                        f"{track.author}",  # 同一作者
                        f"{track.title.split()[0]} music",  # 標題關鍵字
                        f"{track.author} best songs",  # 作者熱門歌曲
                    ]
                    
                    for strategy in search_strategies:
                        try:
                            tracks = await wavelink.Playable.search(strategy)
                            
                            if tracks and len(tracks) > 0:
                                # 過濾已播放的歌曲
                                played_titles = {h.title.lower() for h in queue.history[-20:]}
                                available_tracks = [
                                    t for t in tracks[:15]
                                    if t.title.lower() not in played_titles and
                                    hasattr(t, 'length') and t.length < 600000  # 限制在 10 分鐘內
                                ]
                                
                                if available_tracks:
                                    # 取前幾首作為推薦
                                    recommendations.extend(available_tracks[:3])
                                    if len(recommendations) >= 10:  # 限制推薦數量
                                        break
                        except Exception as e:
                            logger.warning(f"推薦預覽策略 '{strategy}' 失敗: {e}")
                            continue
                    
                    if len(recommendations) >= 10:
                        break
            
            # 去除重複推薦
            seen_titles = set()
            unique_recommendations = []
            for track in recommendations:
                if track.title.lower() not in seen_titles:
                    seen_titles.add(track.title.lower())
                    unique_recommendations.append(track)
            
            return unique_recommendations
            
        except Exception as e:
            logger.error(f"生成推薦預覽失敗: {e}")
            return []

    @commands.hybrid_command()
    async def lavalink_version(self, ctx):
        """查看 Lavalink 伺服器版本資訊"""
        try:
            # 檢查 Wavelink 節點連接
            if not wavelink.Pool.nodes:
                await ctx.send("❌ 未連接到任何 Lavalink 伺服器")
                return
            
            embed = discord.Embed(
                title="🔧 Lavalink 版本資訊",
                color=discord.Color.blue()
            )
            
            # 獲取當前連接的節點
            current_node = None
            for node in wavelink.Pool.nodes.values():
                if node.status.name == "CONNECTED":
                    current_node = node
                    break
            
            if not current_node:
                current_node = list(wavelink.Pool.nodes.values())[0]
            
            # 基本節點資訊
            embed.add_field(
                name="📡 當前節點",
                value=f"**{current_node.identifier}**\n🌐 {current_node.uri}",
                inline=False
            )
            
            # 節點狀態
            status_emoji = {
                "CONNECTED": "🟢",
                "CONNECTING": "🟡",
                "DISCONNECTED": "🔴"
            }
            status_text = status_emoji.get(current_node.status.name, "❓") + f" {current_node.status.name}"
            embed.add_field(name="📊 連接狀態", value=status_text, inline=True)
            
            # 嘗試獲取伺服器資訊
            try:
                # 獲取節點統計資訊
                if hasattr(current_node, 'stats') and current_node.stats:
                    stats = current_node.stats
                    
                    # Lavalink 版本資訊
                    if hasattr(stats, 'lavalink_version'):
                        embed.add_field(
                            name="🏷️ Lavalink 版本",
                            value=f"`{stats.lavalink_version}`",
                            inline=True
                        )
                    
                    # JVM 版本
                    if hasattr(stats, 'jvm_version'):
                        embed.add_field(
                            name="☕ JVM 版本",
                            value=f"`{stats.jvm_version}`",
                            inline=True
                        )
                    
                    # 系統資源使用情況
                    if hasattr(stats, 'memory') and stats.memory:
                        memory_used = stats.memory.used / 1024 / 1024  # MB
                        memory_total = stats.memory.allocated / 1024 / 1024  # MB
                        memory_percent = (memory_used / memory_total) * 100 if memory_total > 0 else 0
                        
                        embed.add_field(
                            name="💾 記憶體使用",
                            value=f"`{memory_used:.1f}MB / {memory_total:.1f}MB`\n({memory_percent:.1f}%)",
                            inline=True
                        )
                    
                    # CPU 使用率
                    if hasattr(stats, 'cpu') and stats.cpu:
                        cpu_cores = getattr(stats.cpu, 'cores', 'N/A')
                        cpu_system_load = getattr(stats.cpu, 'system_load', 0) * 100
                        cpu_lavalink_load = getattr(stats.cpu, 'lavalink_load', 0) * 100
                        
                        embed.add_field(
                            name="🖥️ CPU 資訊",
                            value=f"核心數: `{cpu_cores}`\n系統負載: `{cpu_system_load:.1f}%`\nLavalink 負載: `{cpu_lavalink_load:.1f}%`",
                            inline=True
                        )
                    
                    # 播放器統計
                    if hasattr(stats, 'players'):
                        total_players = getattr(stats, 'playing_players', 0) + getattr(stats, 'players', 0) - getattr(stats, 'playing_players', 0)
                        playing_players = getattr(stats, 'playing_players', 0)
                        
                        embed.add_field(
                            name="🎵 播放器統計",
                            value=f"總播放器: `{total_players}`\n活躍播放器: `{playing_players}`",
                            inline=True
                        )
                    
                    # 運行時間
                    if hasattr(stats, 'uptime'):
                        uptime_seconds = stats.uptime // 1000
                        uptime_minutes = uptime_seconds // 60
                        uptime_hours = uptime_minutes // 60
                        uptime_days = uptime_hours // 24
                        
                        if uptime_days > 0:
                            uptime_str = f"{uptime_days}天 {uptime_hours % 24}時 {uptime_minutes % 60}分"
                        elif uptime_hours > 0:
                            uptime_str = f"{uptime_hours}時 {uptime_minutes % 60}分"
                        else:
                            uptime_str = f"{uptime_minutes}分 {uptime_seconds % 60}秒"
                        
                        embed.add_field(
                            name="⏰ 運行時間",
                            value=f"`{uptime_str}`",
                            inline=True
                        )
                
                else:
                    embed.add_field(
                        name="📊 伺服器統計",
                        value="暫無統計資訊",
                        inline=False
                    )
                
            except Exception as stats_error:
                logger.warning(f"獲取 Lavalink 統計資訊失敗: {stats_error}")
                embed.add_field(
                    name="⚠️ 統計資訊",
                    value="無法獲取詳細統計資訊",
                    inline=False
                )
            
            # Wavelink 客戶端版本
            import wavelink
            embed.add_field(
                name="🐍 Wavelink 版本",
                value=f"`{wavelink.__version__}`",
                inline=True
            )
            
            # 相容性資訊
            if lavalink_manager:
                try:
                    status_summary = lavalink_manager.get_server_status_summary()
                    embed.add_field(
                        name="🔗 版本相容性",
                        value=f"相容伺服器: `{status_summary.get('compatible', 0)}/{status_summary.get('total', 0)}`",
                        inline=True
                    )
                except:
                    pass
            
            embed.set_footer(text="📡 即時伺服器資訊")
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"查看 Lavalink 版本時出錯: {e}")
            
            # 備用簡化版本資訊
            try:
                embed = discord.Embed(
                    title="🔧 Lavalink 版本資訊",
                    color=discord.Color.orange()
                )
                
                # Wavelink 版本
                import wavelink
                embed.add_field(
                    name="🐍 Wavelink 版本",
                    value=f"`{wavelink.__version__}`",
                    inline=True
                )
                
                # 節點連接狀態
                if wavelink.Pool.nodes:
                    node_count = len(wavelink.Pool.nodes)
                    embed.add_field(
                        name="📡 已連接節點",
                        value=f"`{node_count}` 個",
                        inline=True
                    )
                    
                    # 列出節點
                    node_info = ""
                    for node in wavelink.Pool.nodes.values():
                        status_emoji = "🟢" if node.status.name == "CONNECTED" else "🔴"
                        node_info += f"{status_emoji} `{node.identifier}`\n"
                    
                    if node_info:
                        embed.add_field(
                            name="📋 節點列表",
                            value=node_info,
                            inline=False
                        )
                
                embed.add_field(
                    name="⚠️ 注意",
                    value="無法獲取詳細伺服器資訊，可能是伺服器版本較舊或連接問題",
                    inline=False
                )
                
                await ctx.send(embed=embed)
                
            except Exception as fallback_error:
                await ctx.send(f"❌ 查看版本資訊時出錯: {e}\n備用方案也失敗: {fallback_error}")

    # reconnect_lavalink 指令已移至 slash_commands.py 避免重複註冊

async def setup(bot):
    await bot.add_cog(EnhancedMusic(bot))