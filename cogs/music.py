import discord
from discord.ext import commands
import wavelink

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.command(name="play", help="播放音樂")
    async def play(self, ctx, *, query: str):
        if not ctx.voice_client:
            if not ctx.author.voice:
                return await ctx.send("你需要先加入一個語音頻道")
            vc = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        else:
            vc = ctx.voice_client
                
        # 搜索並播放音樂
        search = await wavelink.YouTubeTrack.search(query=query, return_first=True)
        if not search:
            return await ctx.send("找不到相關音樂")
        
        await vc.play(search)
        await ctx.send(f"正在播放: **{search.title}**")
    
    @commands.command(name="pause", help="暫停音樂")
    async def pause(self, ctx):
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send("目前沒有正在播放的音樂")
        
        await ctx.voice_client.pause()
        await ctx.send("音樂已暫停")
    
    @commands.command(name="resume", help="繼續播放音樂")
    async def resume(self, ctx):
        if not ctx.voice_client or not ctx.voice_client.is_paused():
            return await ctx.send("沒有已暫停的音樂")
        
        await ctx.voice_client.resume()
        await ctx.send("繼續播放音樂")
    
    @commands.command(name="stop", help="停止播放音樂")
    async def stop(self, ctx):
        if not ctx.voice_client:
            return await ctx.send("機器人不在語音頻道中")
        
        await ctx.voice_client.disconnect()
        await ctx.send("已停止播放並離開語音頻道")
    
    @commands.command(name="skip", help="跳過當前音樂")
    async def skip(self, ctx):
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send("目前沒有正在播放的音樂")
        
        await ctx.voice_client.stop()
        await ctx.send("已跳過當前音樂")
    
    @commands.command(name="queue", help="顯示播放佇列")
    async def queue(self, ctx):
        if not ctx.voice_client or not hasattr(ctx.voice_client, 'queue'):
            return await ctx.send("目前沒有播放佇列")
        
        if ctx.voice_client.queue.is_empty:
            return await ctx.send("播放佇列是空的")
        
        queue_list = ""
        for i, track in enumerate(ctx.voice_client.queue, start=1):
            queue_list += f"{i}. {track.title}\n"
        
        embed = discord.Embed(title="播放佇列", description=queue_list, color=discord.Color.blue())
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Music(bot))