import os
import asyncio
import discord
from discord.ext import commands
from aiohttp import web

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True

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
    print(f"Web server running on port {port}")

@bot.event
async def on_ready():
    print(f"機器人已上線：{bot.user}")

async def main():
    async with bot:
        await start_web_server()
        
        token = os.getenv("DISCORD_TOKEN")
        if token:
            await bot.start(token)
        else:
            print("錯誤：找不到 DISCORD_TOKEN")

if __name__ == "__main__":
    asyncio.run(main())
