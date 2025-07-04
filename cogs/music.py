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
    
    def get_next(self) -> Optional[wavelink.Playable]:
        """獲取下一首音樂"""
        if self.loop_mode == "track":
            return self.history[-1] if self.history else None
        
        if not self.queue:
            return None
            
        next_track = self.queue.pop(0)
        self.history.append(next_track)
        
        # 保持歷史記錄不超過 50 首
        if len(self.history) > 50:
            self.history = self.history[-50:]
            
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
        self.ensure_data_dir()
        self.load_playlists()
        
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
        
        # 自動播放狀態
        autoplay_status = "✅" if self.autoplay_enabled.get(guild_id, False) else "❌"
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
            try:
                node = wavelink.Node(
                    uri="https://lava-all.ajieblogs.eu.org:443",
                    password="https://dsc.gg/ajidevserver",
                    identifier="music_node"
                )
                
                await wavelink.Pool.connect(client=self.bot, nodes=[node])
                logger.info("Wavelink 節點已連接")
                
            except Exception as e:
                logger.error(f"連接 Wavelink 節點失敗: {e}")
        
        logger.info("Enhanced Music cog 已準備就緒")

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        """當 Wavelink 節點準備就緒時觸發"""
        logger.info(f"Wavelink 節點 {payload.node.identifier} 已準備就緒!")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        """當音軌結束時自動播放下一首"""
        player = payload.player
        guild_id = player.guild.id
        queue = self.get_queue(guild_id)
        
        # 如果是佇列循環模式，將當前歌曲重新加入佇列
        if queue.loop_mode == "queue" and payload.track:
            queue.add(payload.track)
        
        # 獲取下一首歌曲
        next_track = queue.get_next()
        
        if next_track:
            await player.play(next_track)
            # 發送正在播放的消息到最後一個使用音樂命令的頻道
            if hasattr(player, 'last_channel'):
                embed = self.create_now_playing_embed(player, guild_id)
                view = MusicControlView(player, self)
                try:
                    await player.last_channel.send(embed=embed, view=view)
                except:
                    pass
        elif self.autoplay_enabled.get(guild_id, False):
            # 自動播放功能
            await self.auto_recommend_and_play(player)

    async def auto_recommend_and_play(self, player: wavelink.Player):
        """自動推薦並播放音樂"""
        try:
            guild_id = player.guild.id
            queue = self.get_queue(guild_id)
            
            # 基於歷史記錄推薦
            if queue.history:
                last_track = queue.history[-1]
                # 搜索相似的音樂
                search_terms = [
                    f"{last_track.author} music",
                    f"similar to {last_track.title}",
                    f"{last_track.author} popular songs"
                ]
                
                for term in search_terms:
                    try:
                        tracks = await wavelink.Playable.search(term)
                        if tracks:
                            # 過濾掉已經播放過的歌曲
                            new_tracks = [t for t in tracks[:5] if t.title not in [h.title for h in queue.history[-10:]]]
                            if new_tracks:
                                selected_track = random.choice(new_tracks)
                                await player.play(selected_track)
                                queue.history.append(selected_track)
                                
                                if hasattr(player, 'last_channel'):
                                    embed = discord.Embed(
                                        title="🤖 自動播放",
                                        description=f"為你推薦: **{selected_track.title}**",
                                        color=discord.Color.purple()
                                    )
                                    await player.last_channel.send(embed=embed)
                                return
                    except:
                        continue
            
            # 如果沒有歷史記錄，播放熱門音樂
            popular_searches = ["popular music 2024", "top hits", "trending music"]
            search_term = random.choice(popular_searches)
            tracks = await wavelink.Playable.search(search_term)
            
            if tracks:
                selected_track = random.choice(tracks[:10])
                await player.play(selected_track)
                queue.history.append(selected_track)
                
                if hasattr(player, 'last_channel'):
                    embed = discord.Embed(
                        title="🤖 自動播放",
                        description=f"為你推薦熱門音樂: **{selected_track.title}**",
                        color=discord.Color.purple()
                    )
                    await player.last_channel.send(embed=embed)
        
        except Exception as e:
            logger.error(f"自動播放推薦失敗: {e}")

    @commands.hybrid_command()
    async def join(self, ctx):
        """讓機器人加入語音頻道"""
        if not ctx.author.voice:
            await ctx.send("❌ 你必須先加入語音頻道。")
            return
            
        channel = ctx.author.voice.channel
        
        if ctx.voice_client:
            await ctx.voice_client.move_to(channel)
            await ctx.send(f"✅ 已移動到語音頻道：{channel.name}")
        else:
            try:
                player: wavelink.Player = await channel.connect(cls=wavelink.Player)
                player.last_channel = ctx.channel
                await ctx.send(f"✅ 已加入語音頻道：{channel.name}")
            except Exception as e:
                await ctx.send(f"❌ 加入語音頻道失敗: {e}")

    @commands.hybrid_command()
    async def play(self, ctx, *, search: str):
        """播放音樂"""
        if not wavelink.Pool.nodes:
            await ctx.send("❌ 音樂服務暫時不可用，請稍後再試。")
            return
            
        if not ctx.author.voice:
            await ctx.send("❌ 你必須先加入語音頻道。")
            return

        if not ctx.voice_client:
            try:
                player: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
                player.last_channel = ctx.channel
            except Exception as e:
                await ctx.send(f"❌ 無法連接到語音頻道: {e}")
                return
        else:
            player: wavelink.Player = ctx.voice_client
            player.last_channel = ctx.channel

        try:
            tracks = await wavelink.Playable.search(search)
            if not tracks:
                await ctx.send("❌ 找不到相關音樂。")
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
                            await interaction.response.send_message(f"✅ 已加入佇列: **{track.title}**", ephemeral=True)
                        else:
                            await player.play(track)
                            embed = self.music_cog.create_now_playing_embed(player, self.ctx.guild.id)
                            view = MusicControlView(player, self.music_cog)
                            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

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
                await player.play(track)
                embed = self.create_now_playing_embed(player, ctx.guild.id)
                view = MusicControlView(player, self)
                await ctx.send(embed=embed, view=view)

        except Exception as e:
            # Lavalink v4: KeyError: 'timestamp' hotfix
            if hasattr(e, "args") and e.args and isinstance(e.args[0], dict) and "timestamp" not in e.args[0]:
                e.args[0]["timestamp"] = 0
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
            current = self.autoplay_enabled.get(ctx.guild.id, False)
            self.autoplay_enabled[ctx.guild.id] = not current
            status = "開啟" if not current else "關閉"
        else:
            self.autoplay_enabled[ctx.guild.id] = enable
            status = "開啟" if enable else "關閉"
        
        embed = discord.Embed(
            title="🤖 自動播放",
            description=f"自動播放已{status}",
            color=discord.Color.green() if self.autoplay_enabled[ctx.guild.id] else discord.Color.red()
        )
        if self.autoplay_enabled[ctx.guild.id]:
            embed.add_field(
                name="功能說明",
                value="當佇列播放完畢時，會自動根據播放歷史推薦相似音樂",
                inline=False
            )
        await ctx.send(embed=embed)

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
        
        await player.disconnect()
        await ctx.send("⏹️ 已停止播放並離開語音頻道")

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
        queue = self.get_queue(ctx.guild.id)
        player: wavelink.Player = ctx.voice_client
        
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
        embed.add_field(name="🤖 自動播放", value="開啟" if self.autoplay_enabled.get(ctx.guild.id, False) else "關閉", inline=True)
        
        # 計算總播放時間
        if queue.history:
            total_duration = sum(getattr(track, 'length', 0) for track in queue.history)
            embed.add_field(name="⏰ 總播放時間", value=self.format_duration(total_duration), inline=True)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(EnhancedMusic(bot))