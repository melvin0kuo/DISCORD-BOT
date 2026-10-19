# Enhanced Music Cog with UI, Playlist, Autoplay, and More
import re
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
import importlib
import config
from utils.local_lavalink import local_lavalink
from utils.music_player import VoicePlayer
from utils.youtube_fallback import resolve_youtube_fallback

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
        try:
            if self.player.paused:
                await self.player.pause(False)
                await interaction.response.send_message("▶️ 繼續播放", ephemeral=True)
            else:
                await self.player.pause(True)
                await interaction.response.send_message("⏸️ 已暫停", ephemeral=True)
        except Exception as e:
            logger.warning(f"[MusicControlView] play_pause 失敗: {e}")
            await interaction.response.send_message("⚠️ 操作失敗，Lavalink 節點暫時無回應，請稍後再試。", ephemeral=True)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        """跳過按鈕"""
        if not self.player.current:
            await interaction.response.send_message("❌ 沒有正在播放的音樂", ephemeral=True)
            return
        try:
            await self.player.stop()
            await interaction.response.send_message("⏭️ 已跳過", ephemeral=True)
        except Exception as e:
            logger.warning(f"[MusicControlView] skip 失敗: {e}")
            await interaction.response.send_message("⚠️ 跳過失敗，Lavalink 節點暫時無回應，請稍後再試。", ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        """停止按鈕"""
        queue = self.music_cog.get_queue(interaction.guild.id)
        queue.clear()
        self.music_cog._cancel_pending_playback(interaction.guild.id)
        try:
            await self.player.stop()
            await interaction.response.send_message("⏹️ 已停止播放並清空佇列", ephemeral=True)
        except Exception as e:
            logger.warning(f"[MusicControlView] stop 失敗: {e}")
            await interaction.response.send_message("⚠️ 停止失敗，Lavalink 節點暫時無回應。", ephemeral=True)
    
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

class LyricsPageView(discord.ui.View):
    """歌詞分頁導航"""
    def __init__(self, title: str, pages: list[str]):
        super().__init__(timeout=120)
        self.title = title
        self.pages = pages
        self.current = 0
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = self.current == 0
        self.next_btn.disabled = self.current == len(self.pages) - 1

    def _embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=self.title,
            description=self.pages[self.current],
            color=discord.Color.purple(),
        )
        embed.set_footer(text=f"第 {self.current + 1} / {len(self.pages)} 頁")
        return embed

    @discord.ui.button(label="◀ 上一頁", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self._embed(), view=self)

    @discord.ui.button(label="下一頁 ▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self._embed(), view=self)

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
        self._playback_blocked = set()
        self._track_end_locks = {}
        self._voice_locks = {}
        self._playback_generation = {}
        self._fallback_attempts = {}
        self._playback_active = {}
        self.ensure_data_dir()
        self.load_playlists()
        self.load_autoplay_config()

    async def cog_load(self):
        # 熱重載時一併替換舊的公共節點管理器，並釋放其 HTTP session。
        global lavalink_manager
        for node in list(wavelink.Pool.nodes.values()):
            await node.close(eject=True)
        if lavalink_manager:
            await lavalink_manager.close_session()
        module = importlib.reload(importlib.import_module('utils.lavalink_manager'))
        lavalink_manager = module.lavalink_manager
        if self.bot.is_ready():
            await self.connect_to_lavalink()
        
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
                self._cancel_pending_playback(guild_id)
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
                    logger.warning(f'語音連線提前中斷 (guild={guild_id}, elapsed={elapsed:.1f}s)，保留本機節點')
                if guild_id in self.queues:
                    self.queues[guild_id].clear()

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
        await self.connect_to_lavalink()
        
        logger.info("✅ Enhanced Music cog 已準備就緒")

    @staticmethod
    def _make_node(uri: str, password: str, identifier: str, session=None) -> wavelink.Node:
        """統一建立 wavelink Node，確保參數與最新 API 一致"""
        return wavelink.Node(
            uri=uri,
            password=password,
            identifier=identifier,
            session=session,
            retries=1,
            resume_timeout=60,
            inactive_player_timeout=300,   # 靜止 300 秒觸發 inactive 事件
            inactive_channel_tokens=3,     # 空頻道播完 3 首後觸發
        )

    async def connect_to_lavalink(self, force=False):
        """只連接本機節點，清理殘留節點並等待 WebSocket ready。"""
        async with self._connect_lock:
            uri = config.LAVALINK_URI.rstrip('/')
            ready = None
            for existing in list(wavelink.Pool.nodes.values()):
                if not force and existing.uri.rstrip('/') == uri and existing.status == wavelink.NodeStatus.CONNECTED:
                    ready = existing
                else:
                    try:
                        await existing.close(eject=True)
                    except Exception as error:
                        logger.warning('清理舊節點失敗: %s', error)
                        return False
            if ready:
                return True
            if not lavalink_manager or not await local_lavalink.ensure_started():
                logger.error('本機音樂服務未啟動，請執行 start_with_lavalink.bat')
                return False
            await lavalink_manager.update_server_list()
            server = await lavalink_manager.get_best_server()
            if server is None:
                logger.error('本機 Lavalink API 驗證失敗')
                return False
            session = await lavalink_manager._get_session()
            node = self._make_node(server.uri, server.password, 'local-lavalink', session=session)
            try:
                await asyncio.wait_for(wavelink.Pool.connect(nodes=[node], client=self.bot),
                                       timeout=config.LAVALINK_CONNECT_TIMEOUT)
                deadline = asyncio.get_running_loop().time() + config.LAVALINK_CONNECT_TIMEOUT
                while node.status != wavelink.NodeStatus.CONNECTED:
                    if asyncio.get_running_loop().time() >= deadline:
                        raise TimeoutError('本機 Lavalink 未回傳 WebSocket ready')
                    await asyncio.sleep(0.05)
                lavalink_manager.current_server = server
                logger.info('✅ 已連接本機 Lavalink: %s', server.uri)
                return True
            except Exception as error:
                logger.error('本機 Lavalink 連線失敗: %s', error)
                await node.close(eject=True)
                return False

    async def switch_lavalink_server(self):
        """相容舊指令：重新連接本機服務，不使用公共伺服器。"""
        return await self.connect_to_lavalink(force=True)

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
        # WebSocket 只做有限次重連；刻意 close 不再觸發另一條無限重連鏈。

    @commands.Cog.listener()
    async def on_wavelink_inactive_player(self, player: wavelink.Player):
        """播放器閒置事件——只記 log，不自動斷線"""
        logger.info(
            f"[閒置] guild={player.guild.id} | "
            f"current={player.current} | "
            f"channel={getattr(player, 'channel', None)}"
        )

    async def _halt_failed_playback(self, player, track=None):
        guild_id = player.guild.id
        player.autoplay = wavelink.AutoPlayMode.disabled
        if guild_id in self._playback_blocked:
            return
        self._playback_blocked.add(guild_id)
        channel = getattr(player, 'last_channel', None)
        if channel:
            generation = self._playback_generation.get(guild_id, 0)
            extras = dict(getattr(track, 'extras', {}))
            title = extras.get('_original_title') or getattr(track, 'title', '這首歌曲')
            notice = f'❌ 無法讀取「{title}」的音訊，已停止自動接播。音源可能要求登入或暫時不可用；請改用其他音源或重新點歌。'
            if getattr(track, 'source', None) == 'youtube' or extras.get('_youtube_fallback'):
                try:
                    candidates = await asyncio.wait_for(wavelink.Playable.search(
                        f"{title} {extras.get('_original_author') or getattr(track, 'author', '')}",
                        source=wavelink.TrackSource.SoundCloud), timeout=5)
                    choices = [f'{index}. {candidate.title}: {candidate.uri}'
                               for index, candidate in enumerate(candidates[:3], 1)]
                    if choices:
                        notice += '\n\n其他音源候選（版本可能不同，請自行選擇並使用 `/play 網址`）：\n' + '\n'.join(choices)
                except Exception:
                    logger.info('未能取得其他音源候選')
            if self._playback_generation.get(guild_id, 0) == generation:
                await channel.send(notice, allowed_mentions=discord.AllowedMentions.none())

    def _cancel_pending_playback(self, guild_id):
        self._playback_generation[guild_id] = self._playback_generation.get(guild_id, 0) + 1
        self._playback_active.pop(guild_id, None)

    def _is_current_track_event(self, guild_id, track):
        generation = self._playback_generation.get(guild_id, 0)
        extras = dict(getattr(track, 'extras', {}))
        if extras.get('_request_generation', generation) != generation:
            return False
        active = self._playback_active.get(guild_id)
        if active is None:
            return guild_id not in self._playback_generation
        return active == (generation, getattr(track, 'encoded', None))

    async def _handle_track_failure(self, player, track):
        guild_id = player.guild.id
        if not self._is_current_track_event(guild_id, track):
            return
        generation = self._playback_generation.get(guild_id, 0)
        key = (generation, getattr(track, 'encoded', None))
        if self._fallback_attempts.get(guild_id) == key:
            return  # exception 與 loadFailed 是同一輪失敗，不重複擷取或報錯。
        if (guild_id not in self._playback_blocked and getattr(track, 'source', None) == 'youtube'
                and getattr(config, 'YOUTUBE_FALLBACK_ENABLED', True)):
            self._fallback_attempts[guild_id] = key
            try:
                fallback = await resolve_youtube_fallback(track)
                if self._playback_generation.get(guild_id, 0) != generation or not getattr(player, 'connected', True):
                    return
                fallback.extras = {**dict(getattr(fallback, 'extras', {})), '_request_generation': generation}
                self._playback_active[guild_id] = (generation, fallback.encoded)
                await player.play(fallback)
                logger.info('已切換原歌曲的 yt-dlp 音訊備援: %s', track.title)
                return
            except Exception as error:
                logger.warning('YouTube 音訊備援失敗: %s', type(error).__name__)
                if self._playback_generation.get(guild_id, 0) != generation:
                    return
        await self._halt_failed_playback(player, track)

    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, payload):
        if not payload.player or not payload.player.guild:
            return
        logger.error('[Track exception] guild=%s | error=%s', payload.player.guild.id, payload.exception)
        await self._handle_track_failure(payload.player, payload.track)

    @commands.Cog.listener()
    async def on_wavelink_track_stuck(self, payload):
        if not payload.player or not payload.player.guild:
            return
        guild_id = payload.player.guild.id
        if not self._is_current_track_event(guild_id, payload.track):
            return
        generation = self._playback_generation.get(guild_id, 0)
        await self._halt_failed_playback(payload.player, payload.track)
        if (self._playback_generation.get(guild_id, 0) == generation
                and self._is_current_track_event(guild_id, payload.track)):
            await payload.player.stop()

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload):
        if not payload.player or not payload.player.guild:
            return
        player = payload.player
        await asyncio.sleep(0.5)
        if (self._is_current_track_event(player.guild.id, payload.track)
                and player.guild.id not in self._playback_blocked and player.current == payload.track
                and getattr(player, 'last_channel', None)):
            await player.last_channel.send(embed=self.create_now_playing_embed(player, player.guild.id),
                                           view=MusicControlView(player, self))

    async def _play_track(self, player, track, *, manual=False):
        if manual:
            self._playback_blocked.discard(player.guild.id)
        elif player.guild.id in self._playback_blocked:
            return False
        self._cancel_pending_playback(player.guild.id)
        generation = self._playback_generation[player.guild.id]
        track.extras = {**dict(getattr(track, 'extras', {})), '_request_generation': generation}
        self._playback_active[player.guild.id] = (generation, getattr(track, 'encoded', None))
        await player.play(track)
        return True

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload):
        if not payload.player or not payload.player.guild:
            return
        player = payload.player
        guild_id = player.guild.id
        if not self._is_current_track_event(guild_id, payload.track):
            return
        reason = str(payload.reason).lower()
        if reason in ('loadfailed', 'load_failed'):
            await self._handle_track_failure(player, payload.track)
            return
        if reason not in ('finished', 'stopped') or guild_id in self._playback_blocked:
            return
        lock = self._track_end_locks.setdefault(guild_id, asyncio.Lock())
        async with lock:
            if player.current is not None or guild_id in self._playback_blocked:
                return
            queue = self.get_queue(guild_id)
            next_track = queue.get_next() if reason == 'finished' or queue.queue else None
            if not next_track and reason == 'finished' and self.get_autoplay_status(guild_id):
                await self.auto_recommend_and_play(player)
                if guild_id in self._playback_blocked or player.current is not None:
                    return
                next_track = queue.get_next()
            if next_track:
                try:
                    await self._play_track(player, next_track)
                except Exception:
                    logger.exception('播放下一首失敗')
                    await self._halt_failed_playback(player, next_track)

    def _extract_youtube_id(self, uri: str) -> Optional[str]:
        """從 YouTube URL 或 identifier 提取 video ID"""
        if not uri:
            return None
        m = re.search(r'(?:v=|youtu\.be/|/embed/|/v/)([a-zA-Z0-9_-]{11})', uri)
        if m:
            return m.group(1)
        # wavelink 有時 identifier 本身就是 11 位 ID
        if re.fullmatch(r'[a-zA-Z0-9_-]{11}', uri):
            return uri
        return None

    async def auto_recommend_and_play(self, player: wavelink.Player):
        """自動推薦並將音樂加入佇列（YouTube Radio 優先）"""
        try:
            guild_id = player.guild.id
            queue = self.get_queue(guild_id)
            
            # 更新統計
            if guild_id not in self.autoplay_stats:
                self.autoplay_stats[guild_id] = {'attempts': 0, 'successes': 0, 'last_attempt': 0}
            
            self.autoplay_stats[guild_id]['attempts'] += 1
            self.autoplay_stats[guild_id]['last_attempt'] = time.time()
            
            logger.info(f"🤖 開始自動推薦 (嘗試 #{self.autoplay_stats[guild_id]['attempts']}) - 歷史記錄: {len(queue.history)} 首")

            played_titles = {h.title.lower() for h in queue.history[-30:]}
            recommended_track = None

            def pick_from(candidates):
                """從候選清單中隨機挑一首未播過的"""
                eligible = [t for t in candidates if t.title.lower() not in played_titles]
                return random.choice(eligible) if eligible else None

            # ── 策略 1：YouTube Radio（RDAMVM）——風格最相近 ──────────────
            # YouTube Music 的 Radio 功能：基於同一首歌自動生成相似曲目清單
            if queue.history:
                for base_track in reversed(queue.history[-5:]):
                    vid_id = self._extract_youtube_id(
                        getattr(base_track, 'uri', None) or getattr(base_track, 'identifier', None)
                    )
                    if not vid_id:
                        continue
                    radio_url = f"https://www.youtube.com/playlist?list=RDAMVM{vid_id}"
                    try:
                        result = await wavelink.Playable.search(radio_url)
                        radio_tracks = result.tracks if isinstance(result, wavelink.Playlist) else (result if isinstance(result, list) else [])
                        recommended_track = pick_from(radio_tracks)
                        if recommended_track:
                            logger.info(f"✅ [Radio] {recommended_track.title} (基於 {base_track.title})")
                            break
                    except Exception as e:
                        logger.debug(f"Radio 搜尋失敗 ({vid_id}): {e}")

            # ── 策略 2：同類型關鍵字搜尋 ─────────────────────────────────
            # 從最近播放中提取作者/標題關鍵字，擴展到同類型但不限同作者
            if not recommended_track and queue.history:
                recent = queue.history[-3:]
                search_queries = []
                for t in reversed(recent):
                    if t.author:
                        search_queries.append(f"{t.author} mix")
                        search_queries.append(f"{t.author} similar artists playlist")
                    if t.title:
                        # 取標題第一個關鍵詞，搜尋相似風格
                        kw = t.title.split()[0] if t.title else ""
                        if kw:
                            search_queries.append(f"{kw} chill mix playlist")

                for q in search_queries:
                    try:
                        result = await wavelink.Playable.search(q)
                        candidates = result.tracks if isinstance(result, wavelink.Playlist) else (result[:20] if isinstance(result, list) else [])
                        recommended_track = pick_from(candidates)
                        if recommended_track:
                            logger.info(f"✅ [Mix 搜尋] {recommended_track.title} (查詢: {q})")
                            break
                    except Exception as e:
                        logger.debug(f"Mix 搜尋失敗 ({q}): {e}")

            # ── 策略 3：備用熱門榜單 ──────────────────────────────────────
            if not recommended_track:
                fallback_queries = [
                    "Billboard Hot 100 2024 playlist",
                    "trending music playlist",
                    "popular hits mix",
                ]
                for q in fallback_queries:
                    try:
                        result = await wavelink.Playable.search(q)
                        candidates = result.tracks if isinstance(result, wavelink.Playlist) else (result[:20] if isinstance(result, list) else [])
                        suitable = [t for t in candidates if getattr(t, 'length', 999999) < 480000]
                        recommended_track = pick_from(suitable) or (random.choice(suitable) if suitable else None)
                        if recommended_track:
                            logger.info(f"✅ [備用] {recommended_track.title}")
                            break
                    except Exception as e:
                        logger.debug(f"備用搜尋失敗: {e}")
            
            # 將推薦歌曲加入佇列
            if recommended_track:
                queue.add(recommended_track)
                logger.info(f"📋 已將推薦歌曲加入佇列: {recommended_track.title}")
                
                return True
            else:
                logger.warning("❌ 所有推薦策略都失敗了")
                return False
                
        except Exception as e:
            logger.error(f"❌ 自動播放推薦失敗: {e}", exc_info=True)
            return False

    async def _connect_voice(self, guild, channel, text_channel):
        lock = self._voice_locks.setdefault(guild.id, asyncio.Lock())
        async with lock:
            current = guild.voice_client
            if current and getattr(current, 'connected', False):
                if current.channel != channel:
                    raise RuntimeError('機器人已在其他語音頻道服務')
                current.last_channel = text_channel
                return current
            if not any(node.status == wavelink.NodeStatus.CONNECTED for node in wavelink.Pool.nodes.values()):
                if not await self.connect_to_lavalink():
                    raise RuntimeError('本機音樂服務尚未就緒')
            for attempt in range(2):
                try:
                    logger.info('語音連線嘗試 #%s: %s', attempt + 1, channel.name)
                    player = await channel.connect(cls=VoicePlayer, self_deaf=True, timeout=30.0)
                    player.last_channel = text_channel
                    return player
                except (wavelink.ChannelTimeoutException, discord.ClientException):
                    stale = guild.voice_client
                    if stale:
                        await stale.disconnect(force=True)
                    else:
                        await guild.change_voice_state(channel=None)
                    if attempt == 1:
                        raise
                    await asyncio.sleep(1)

    @commands.hybrid_command()
    async def join(self, ctx):
        """讓機器人加入語音頻道"""
        await ctx.defer()
        if not ctx.author.voice:
            await ctx.send('❌ 你必須先加入語音頻道。')
            return
        channel = ctx.author.voice.channel
        try:
            if ctx.voice_client and ctx.voice_client.connected:
                await ctx.voice_client.move_to(channel, timeout=30.0)
                ctx.voice_client.last_channel = ctx.channel
            else:
                await self._connect_voice(ctx.guild, channel, ctx.channel)
            await ctx.send(f'✅ 已加入語音頻道：{channel.name}')
        except Exception:
            logger.exception('語音連線失敗')
            await ctx.send('❌ 語音連線失敗，請稍後重試；本機音樂節點已保留。')

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

            if not ctx.voice_client or not ctx.voice_client.connected:
                try:
                    player = await self._connect_voice(ctx.guild, ctx.author.voice.channel, ctx.channel)
                except Exception:
                    logger.exception('播放前語音連線失敗')
                    await ctx.send('❌ 無法連接語音頻道，請稍後重試；本機音樂節點已保留。')
                    return
            else:
                player = ctx.voice_client
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
                    
                    # 如果是最後一次嘗試，拋出異常
                    if attempt == max_retries - 1:
                        raise
                    
                    # 短暫等待後重試
                    await asyncio.sleep(2)
            
            if not tracks:
                await ctx.send("❌ 找不到相關音樂。可能是搜尋服務暫時不可用，請稍後再試。")
                return

            # ── YouTube 播放清單批次導入 ──────────────────────────────────
            if isinstance(tracks, wavelink.Playlist):
                playlist = tracks
                queue = self.get_queue(ctx.guild.id)
                added = 0
                first_track = None
                for t in playlist.tracks:
                    if added == 0 and not player.current:
                        first_track = t
                    else:
                        queue.add(t)
                    added += 1
                if first_track:
                    await self._play_track(player, first_track, manual=True)
                    queue.add_to_history(first_track)
                embed = discord.Embed(
                    title="📋 播放清單已導入",
                    description=f"**{playlist.name}**",
                    color=discord.Color.green()
                )
                embed.add_field(name="歌曲數量", value=f"{added} 首", inline=True)
                embed.add_field(name="佇列位置", value=f"第 1 ~ {added} 首", inline=True)
                if first_track:
                    embed.add_field(name="▶️ 正在播放", value=first_track.title, inline=False)
                await ctx.send(embed=embed)
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
                            await self.music_cog._play_track(player, track, manual=True)
                            # 將直接播放的歌曲添加到歷史記錄
                            queue.add_to_history(track)
                            await interaction.response.send_message(f'⏳ 正在載入：{track.title}', ephemeral=True)

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
                    await self._play_track(player, track, manual=True)
                    # 將直接播放的歌曲添加到歷史記錄
                    queue.add_to_history(track)
                    await ctx.send(f'⏳ 正在載入：{track.title}')
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
            await ctx.send('❌ 音源讀取失敗，請稍後重試或更換音源；本機節點已保留。')
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
                await self._play_track(player, next_track, manual=True)
                # get_next() 已經將歌曲添加到歷史記錄，這裡不需要重複添加
                await ctx.send(f'⏳ 正在載入：{next_track.title}')
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
        self._cancel_pending_playback(ctx.guild.id)
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
    async def leave(self, ctx):
        """離開語音頻道並清空佇列"""
        player: wavelink.Player = ctx.voice_client
        if not player:
            await ctx.send("❌ 機器人未在語音頻道中。")
            return

        queue = self.get_queue(ctx.guild.id)
        queue.clear()
        self._cancel_pending_playback(ctx.guild.id)
        self._user_stopped.add(ctx.guild.id)

        try:
            await player.disconnect()
            await ctx.send("👋 已離開語音頻道。")
        except LavalinkException as e:
            logger.warning(f"⚠️ 斷線時 Lavalink 錯誤 (可忽略): {e}")
            await ctx.send("👋 已離開語音頻道。")
        except Exception as e:
            logger.error(f"❌ 離開語音頻道時出錯: {e}")
            await ctx.send("⚠️ 嘗試離開時出錯，請確認機器人狀態。")

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

    async def _fetch_lyrics(self, title: str, artist: str) -> Optional[str]:
        """嘗試從 LRCLib 取得歌詞，失敗則改用 lyrics.ovh"""
        import aiohttp
        clean_title = re.sub(r'\s*[\(\[].*?[\)\]]', '', title).strip()

        # ── 優先：LRCLib ──────────────────────────────────────────────
        try:
            async with aiohttp.ClientSession() as session:
                params = {"track_name": clean_title, "artist_name": artist}
                async with session.get(
                    "https://lrclib.net/api/get",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=8),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # 優先用純文字歌詞；沒有的話把 LRC 時間標記去掉
                        plain = data.get("plainLyrics") or ""
                        if not plain:
                            synced = data.get("syncedLyrics") or ""
                            plain = re.sub(r'\[\d+:\d+\.\d+\]', '', synced).strip()
                        if plain:
                            return plain
        except Exception as e:
            logger.debug(f"LRCLib 查詢失敗: {e}")

        # ── 備用：lyrics.ovh ──────────────────────────────────────────
        try:
            import urllib.parse
            enc_artist = urllib.parse.quote(artist)
            enc_title = urllib.parse.quote(clean_title)
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.lyrics.ovh/v1/{enc_artist}/{enc_title}",
                    timeout=aiohttp.ClientTimeout(total=8),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("lyrics")
        except Exception as e:
            logger.debug(f"lyrics.ovh 查詢失敗: {e}")

        return None

    @commands.hybrid_command()
    async def lyrics(self, ctx, *, query: str = None):
        """顯示歌詞（自動抓取正在播放的歌曲，或手動指定「歌名 歌手」）"""
        await ctx.defer()
        player: wavelink.Player = ctx.voice_client

        if query:
            parts = query.split(maxsplit=1)
            title = parts[0]
            artist = parts[1] if len(parts) > 1 else ""
        else:
            if not player or not player.current:
                await ctx.send("❌ 請提供歌曲名稱，或先播放一首歌。")
                return
            title = player.current.title
            artist = getattr(player.current, "author", "") or ""

        text = await self._fetch_lyrics(title, artist)

        if not text:
            await ctx.send(f"❌ 找不到 **{title}** 的歌詞。")
            return

        # ── 分頁：每頁最多 3800 字元（Embed description 上限 4096）────
        pages = []
        lines = text.splitlines()
        chunk = ""
        for line in lines:
            if len(chunk) + len(line) + 1 > 3800:
                pages.append(chunk.strip())
                chunk = ""
            chunk += line + "\n"
        if chunk.strip():
            pages.append(chunk.strip())

        total = len(pages)
        header = f"🎤 {title}" + (f" — {artist}" if artist else "")

        if total == 1:
            embed = discord.Embed(title=header, description=pages[0], color=discord.Color.purple())
            await ctx.send(embed=embed)
        else:
            # 多頁時使用帶導航按鈕的 View
            view = LyricsPageView(header, pages)
            embed = discord.Embed(
                title=header,
                description=pages[0],
                color=discord.Color.purple(),
            )
            embed.set_footer(text=f"第 1 / {total} 頁")
            await ctx.send(embed=embed, view=view)

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
                    await self.music_cog._play_track(player, track, manual=True)
                    # 將直接播放的歌曲添加到歷史記錄
                    queue.add_to_history(track)
                    await interaction.response.send_message(f'⏳ 正在載入：{track.title}', ephemeral=True)

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
        
        msg = await ctx.send("🔍 正在檢查本機 Lavalink...")
        
        try:
            await lavalink_manager.update_server_list(force=True)
            await lavalink_manager.get_best_server()
            status = lavalink_manager.get_server_status_summary()
            await msg.edit(content=f"本機 Lavalink：{'✅ 可用' if status['online'] else '❌ 未就緒'}")
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
            played_titles = {h.title.lower() for h in queue.history[-30:]}

            if queue.history:
                for base_track in reversed(queue.history[-5:]):
                    # 優先用 YouTube Radio
                    vid_id = self._extract_youtube_id(
                        getattr(base_track, 'uri', None) or getattr(base_track, 'identifier', None)
                    )
                    if vid_id:
                        try:
                            result = await wavelink.Playable.search(
                                f"https://www.youtube.com/playlist?list=RDAMVM{vid_id}"
                            )
                            radio_tracks = result.tracks if isinstance(result, wavelink.Playlist) else (result if isinstance(result, list) else [])
                            eligible = [t for t in radio_tracks if t.title.lower() not in played_titles]
                            recommendations.extend(eligible[:4])
                        except Exception as e:
                            logger.debug(f"Radio 預覽失敗: {e}")

                    # 補充：同類型關鍵字搜尋
                    if len(recommendations) < 10 and base_track.author:
                        try:
                            result = await wavelink.Playable.search(f"{base_track.author} mix")
                            candidates = result if isinstance(result, list) else []
                            eligible = [t for t in candidates[:10] if t.title.lower() not in played_titles]
                            recommendations.extend(eligible[:3])
                        except Exception:
                            pass

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
