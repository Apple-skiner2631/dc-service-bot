import os
import sys
import asyncio
import discord
from discord.ext import commands
from aiohttp import web

sys.stdout.reconfigure(line_buffering=True)

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
async def handle_ping(request):
    return web.Response(text="Bot is running smoothly on Docker!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"✅ Web Server 成功於 Port {port} 中")

async def load_extensions():
    if os.path.exists("./cogs"):
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                await bot.load_extension(f"cogs.{filename[:-3]}")
                print(f"📦 已成功載入模組: {filename}")

@bot.event
async def on_ready():
    print(f"機器人已成功登入：{bot.user}")

async def main():
    async with bot:
        await start_web_server()
        await load_extensions()
        
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            print("❌ [錯誤] 找不到 DISCORD_TOKEN 環境變數！")
            return
            
        print("🔑 正在嘗試連線至 Discord...")
        try:
            await bot.start(token.strip())
        except Exception as e:
            print(f"❌ [連線失敗] 原因：{e}")

if __name__ == "__main__":
    asyncio.run(main())