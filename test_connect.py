import discord
import os
from dotenv import load_dotenv
import asyncio

# 載入環境變數
load_dotenv()

# 檢查 TOKEN 是否正確載入
token = os.getenv('DISCORD_TOKEN')
print(f"TOKEN 載入狀態: {'✅ 已載入' if token else '❌ 未載入'}")
if token:
    print(f"TOKEN 前10字符: {token[:10]}...")
    print(f"TOKEN 長度: {len(token)}")
else:
    print("❌ 請檢查 .env 文件中的 DISCORD_TOKEN 設定")
    exit(1)

# 設置 intents
intents = discord.Intents.default()
intents.message_content = True

# 創建客戶端
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'✅ 成功登入為: {client.user}')
    print(f'機器人 ID: {client.user.id}')
    print(f'連接的伺服器數量: {len(client.guilds)}')
    
    # 列出連接的伺服器
    if client.guilds:
        print("連接的伺服器:")
        for guild in client.guilds:
            print(f"  - {guild.name} (ID: {guild.id})")
    else:
        print("⚠️  機器人尚未加入任何伺服器")
    
    # 測試完成後關閉
    await client.close()

@client.event
async def on_error(event, *args, **kwargs):
    print(f"❌ 發生錯誤: {event}")
    import traceback
    traceback.print_exc()

# 嘗試登入
try:
    print("🔄 嘗試連接到 Discord...")
    client.run(token)
except discord.LoginFailure:
    print("❌ 登入失敗 - TOKEN 無效")
    print("請檢查:")
    print("1. TOKEN 是否正確複製")
    print("2. TOKEN 是否已重新生成")
    print("3. 機器人是否已啟用")
except discord.HTTPException as e:
    print(f"❌ HTTP 錯誤: {e}")
except Exception as e:
    print(f"❌ 未知錯誤: {e}")
    import traceback
    traceback.print_exc()