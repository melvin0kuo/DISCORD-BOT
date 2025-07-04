import discord
from discord.ext import commands, tasks
import wavelink
import asyncio
from typing import List, Optional
# from function import get_lang, truncate_string, send

# 播放佇列資料結構
class Song:
    def __init__(self, info):
        self.title = info.get("title", "未知標題")
        self.url = info["url"]
        self.webpage_url = info.get("webpage_url", "")
        self.duration = info.get("duration", 0)
        self.requester = None
        self.thumbnail = info.get("thumbnail", "")
        self.author = info.get("uploader", "")
        self.is_stream = info.get("is_live", False)

class MusicQueue:
    def __init__(self):
        self.songs: List[Song] = []
        self.autoplay = False

    def add(self, song: Song):
        self.songs.append(song)

    def pop(self) -> Optional[Song]:
        if self.songs:
            return self.songs.pop(0)
        return None

    def clear(self):
        self.songs.clear()

    def is_empty(self):
        return len(self.songs) == 0

    def __len__(self):
        return len(self.songs)

    def __iter__(self):
        return iter(self.songs)

class MusicPanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}  # guild_id: MusicQueue
        self.panel_tasks = {}  # guild_id: task
        self.wavelink_ready = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.wavelink_ready:
            try:
                node = await wavelink.NodePool.create_node(
                    bot=self.bot,
                    host="lava-v4.ajieblogs.eu.org",
                    port=443,
                    password="https://dsc.gg/ajidevserver",
                    https=True,
                    secure=True
                )
                # 等待 node 進入 CONNECTED 狀態
                await node.wait_for_ready()
                print("Lavalink node 已連線")
                self.wavelink_ready = True
            except Exception as e:
                print(f"Lavalink node 連線失敗: {e}")
        print("MusicPanel cog is ready.")

    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = MusicQueue()
        return self.queues[guild_id]

    async def play_next(self, ctx):
        queue = self.get_queue(ctx.guild.id)
        if not queue.is_empty():
            song = queue.pop()
            await self._play_song(ctx, song)
        elif queue.autoplay and hasattr(ctx, "last_song") and ctx.last_song:
            await ctx.send("🔁 自動播放推薦歌曲...")
            await self.play(ctx, query=f"related:{ctx.last_song.webpage_url}")
        else:
            await ctx.send("播放佇列已結束。")
            await self.stop_panel_task(ctx.guild.id)

    async def _play_song(self, ctx, song: Song):
        vc = ctx.voice_client
        if not vc:
            return
        player: wavelink.Player = vc
        track = await wavelink.YouTubeTrack.search(song.webpage_url, return_first=True)
        await player.play(track)
        ctx.last_song = song
        await self.update_panel(ctx, song, position=0, is_new=True)

    async def update_panel(self, ctx, song, position=0, is_new=False):
        # 進度條產生
        def progress_bar(pos, dur, length=24):
            if dur == 0:
                return "─" * length
            filled = int(length * pos / dur)
            filled = min(filled, length-1)
            return "─" * filled + "●" + "─" * (length - filled - 1)

        bar = progress_bar(position, song.duration)
        embed = discord.Embed(
            title="音樂控制面板",
            description=f"{bar}\n{position}s / {song.duration}s",
            color=discord.Color.purple()
        )
        embed.add_field(name="正在播放", value=f"[{song.title}]({song.webpage_url})", inline=False)
        embed.set_thumbnail(url=song.thumbnail)
        embed.set_footer(text=f"點歌者: {song.requester.display_name if song.requester else '未知'}")

        class MusicControlView(discord.ui.View):
            def __init__(self, music_cog, ctx):
                super().__init__(timeout=60)
                self.music_cog = music_cog
                self.ctx = ctx

            @discord.ui.button(label="⏯️ 播放/暫停", style=discord.ButtonStyle.primary)
            async def playpause(self, interaction: discord.Interaction, button: discord.ui.Button):
                vc = self.ctx.voice_client
                if not vc:
                    await interaction.response.send_message("機器人不在語音頻道", ephemeral=True)
                    return
                if vc.is_playing():
                    await vc.pause()
                    await interaction.response.send_message("已暫停", ephemeral=True)
                elif vc.is_paused():
                    await vc.resume()
                    await interaction.response.send_message("繼續播放", ephemeral=True)
                else:
                    await interaction.response.send_message("目前沒有音樂播放", ephemeral=True)
                await self.music_cog.refresh_panel(self.ctx)

            @discord.ui.button(label="⏭️ 跳過", style=discord.ButtonStyle.secondary)
            async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
                vc = self.ctx.voice_client
                if not vc or not vc.is_playing():
                    await interaction.response.send_message("目前沒有正在播放的音樂", ephemeral=True)
                    return
                await vc.stop()
                await interaction.response.send_message("已跳過", ephemeral=True)
                await self.music_cog.refresh_panel(self.ctx)

            @discord.ui.button(label="⏹️ 停止", style=discord.ButtonStyle.danger)
            async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
                vc = self.ctx.voice_client
                if not vc:
                    await interaction.response.send_message("機器人不在語音頻道", ephemeral=True)
                    return
                await vc.disconnect()
                self.music_cog.get_queue(self.ctx.guild.id).clear()
                await interaction.response.send_message("已停止播放並離開語音頻道", ephemeral=True)
                await self.music_cog.stop_panel_task(self.ctx.guild.id)

        if is_new or not hasattr(ctx, "panel_message") or ctx.panel_message is None:
            ctx.panel_message = await ctx.send(embed=embed, view=MusicControlView(self, ctx))
        else:
            await ctx.panel_message.edit(embed=embed, view=MusicControlView(self, ctx))

    async def refresh_panel(self, ctx):
        vc = ctx.voice_client
        song = getattr(ctx, "last_song", None)
        if not song or not vc:
            return
        # 估算播放秒數
        position = int(vc.source.original.tell() / 48000) if hasattr(vc, "source") and hasattr(vc.source, "original") else 0
        await self.update_panel(ctx, song, position=position)

    async def stop_panel_task(self, guild_id):
        task = self.panel_tasks.get(guild_id)
        if task:
            task.cancel()
            self.panel_tasks[guild_id] = None

    @commands.command(name="play", help="播放音樂（YouTube 連結或關鍵字）")
    async def play(self, ctx, *, query: str):
        try:
            if not ctx.author.voice:
                return await ctx.send("你需要先加入一個語音頻道")
            channel = ctx.author.voice.channel
            if not ctx.voice_client:
                vc = await channel.connect(cls=wavelink.Player)
            else:
                vc = ctx.voice_client

            await ctx.send(f"🔍 正在搜尋: `{query}` ...")
            # 使用 wavelink 搜尋
            track = await wavelink.YouTubeTrack.search(query, return_first=True)
            song = Song({
                "title": track.title,
                "url": track.uri,
                "webpage_url": track.uri,
                "duration": track.length // 1000,
                "thumbnail": getattr(track, "thumb", ""),
                "uploader": getattr(track, "author", ""),
                "is_live": track.is_stream
            })
            song.requester = ctx.author

            queue = self.get_queue(ctx.guild.id)
            queue.add(song)

            if not vc.is_playing():
                await self._play_song(ctx, song)
                # 啟動自動更新面板
                if ctx.guild.id not in self.panel_tasks or self.panel_tasks[ctx.guild.id] is None:
                    self.panel_tasks[ctx.guild.id] = self.bot.loop.create_task(self.panel_updater(ctx))
            else:
                await ctx.send(f"已加入佇列: **{song.title}**")

        except Exception as e:
            await ctx.send(f"❌ 發生錯誤: {e}")

    async def panel_updater(self, ctx):
        try:
            while True:
                await asyncio.sleep(5)
                await self.refresh_panel(ctx)
        except asyncio.CancelledError:
            pass

    @commands.command(name="musicpanel", help="顯示音樂控制面板")
    async def musicpanel(self, ctx):
        song = getattr(ctx, "last_song", None)
        if not song:
            return await ctx.send("目前沒有正在播放的音樂")
        await self.update_panel(ctx, song, position=0, is_new=True)
        # 啟動自動更新面板
        if ctx.guild.id not in self.panel_tasks or self.panel_tasks[ctx.guild.id] is None:
            self.panel_tasks[ctx.guild.id] = self.bot.loop.create_task(self.panel_updater(ctx))

    @commands.command(name="autoplay", help="切換自動播放")
    async def autoplay(self, ctx):
        queue = self.get_queue(ctx.guild.id)
        queue.autoplay = not queue.autoplay
        await ctx.send(f"自動播放已 {'啟用' if queue.autoplay else '關閉'}")

    @commands.command(name="queue", help="顯示播放佇列")
    async def queue_cmd(self, ctx):
        queue = self.get_queue(ctx.guild.id)
        if queue.is_empty():
            return await ctx.send("播放佇列是空的")
        queue_list = ""
        for i, song in enumerate(queue, start=1):
            queue_list += f"{i}. [{song.title}]({song.webpage_url})\n"
        embed = discord.Embed(title="播放佇列", description=queue_list, color=discord.Color.blue())
        await ctx.send(embed=embed)

    @commands.command(name="clear", help="清空播放佇列")
    async def clear(self, ctx):
        queue = self.get_queue(ctx.guild.id)
        queue.clear()
        await ctx.send("已清空播放佇列")

    # ====== effect.py 指令整合 ======
    async def check_access(self, ctx: commands.Context):
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            text = await get_lang(ctx.guild.id, "noPlayer")
            raise voicelink.exceptions.VoicelinkException(text)
        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                text = await get_lang(ctx.guild.id, "notInChannel")
                raise voicelink.exceptions.VoicelinkException(text.format(ctx.author.mention, player.channel.mention))
        return player

    @commands.hybrid_command(name="speed", aliases=get_aliases("speed"))
    @app_commands.describe(value="The value to set the speed to. Default is `1.0`")
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def speed(self, ctx: commands.Context, value: commands.Range[float, 0, 2]):
        player = await self.check_access(ctx)
        if player.filters.has_filter(filter_tag="speed"):
            player.filters.remove_filter(filter_tag="speed")
        effect = voicelink.Timescale(tag="speed", speed=value)
        await player.add_filter(effect, ctx.author)
        await send(ctx, "addEffect", effect.tag)

    # ...（其餘 effect.py 指令方法依序插入）

    # ====== settings.py 指令整合 ======
    @commands.hybrid_group(
        name="settings",
        aliases=get_aliases("settings"),
        invoke_without_command=True
    )
    async def settings(self, ctx: commands.Context):
        view = HelpView(self.bot, ctx.author)
        embed = view.build_embed(self.__class__.__name__)
        view.response = await send(ctx, embed, view=view)

    @settings.command(name="prefix", aliases=get_aliases("prefix"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def prefix(self, ctx: commands.Context, prefix: str):
        if not self.bot.intents.message_content:
            return await send(ctx, "missingIntents", "MESSAGE_CONTENT", ephemeral=True)
        await update_settings(ctx.guild.id, {"$set": {"prefix": prefix}})
        await send(ctx, "setPrefix", prefix, prefix)

    # ...（其餘 settings.py 指令方法依序插入）

async def setup(bot):
    await bot.add_cog(MusicPanel(bot))