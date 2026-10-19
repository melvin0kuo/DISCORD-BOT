"""舊音樂擴展入口，沿用目前的 Wavelink 播放器實作。"""

from cogs.music import EnhancedMusic, MusicQueue, MusicControlView

MusicPanel = EnhancedMusic

__all__ = ['MusicPanel', 'MusicQueue', 'MusicControlView', 'setup']


async def setup(bot):
    if bot.get_cog('EnhancedMusic') is None:
        await bot.add_cog(MusicPanel(bot))
