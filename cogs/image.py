import discord
from discord.ext import commands
import requests
from config import IMAGE_API_KEY, IMAGE_API_URL

class ImageGeneration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.command(name="generate", help="生成圖片")
    async def generate_image(self, ctx, *, prompt: str):
        await ctx.send("正在生成圖片，請稍候...")
        
        try:
            # 這裡使用假設的 API 請求，您需要替換為實際使用的 API
            response = requests.post(
                IMAGE_API_URL,
                json={"prompt": prompt},
                headers={"Authorization": f"Bearer {IMAGE_API_KEY}"}
            )
            
            if response.status_code == 200:
                # 假設 API 返回圖片 URL
                image_url = response.json().get("image_url")
                embed = discord.Embed(title="生成的圖片", color=discord.Color.green())
                embed.set_image(url=image_url)
                embed.add_field(name="提示詞", value=prompt)
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"生成圖片失敗：{response.text}")
        except Exception as e:
            await ctx.send(f"發生錯誤：{str(e)}")
    
    @commands.command(name="image_help", help="顯示圖片生成幫助")
    async def image_help(self, ctx):
        embed = discord.Embed(
            title="圖片生成幫助",
            description="使用 `!generate [描述]` 來生成圖片。提供越詳細的描述，生成的圖片越符合您的期望。",
            color=discord.Color.blue()
        )
        embed.add_field(name="範例", value="`!generate 一隻在草地上奔跑的柴犬`")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ImageGeneration(bot))