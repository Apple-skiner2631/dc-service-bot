import os
import asyncio
import discord
from discord.ext import commands
from aiohttp import web

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

async def handle_ping(request):
    return web.Response(text="Bot is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"✅ Web server 成功運行於 Port {port}")

@bot.event
async def on_ready():
    print(f"✅ 機器人成功線上登入：{bot.user}")

async def main():
    async with bot:

        await start_web_server()

        token = os.getenv("DISCORD_TOKEN")
        if token:
            print("🔑 正在嘗試連線至 Discord...")
            await bot.start(token.strip())
        else:
            print("❌ 錯誤：找不到 DISCORD_TOKEN 環境變數！")

if __name__ == "__main__":
    asyncio.run(main())
