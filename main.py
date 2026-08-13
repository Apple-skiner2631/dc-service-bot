import os
import asyncio
import logging
from aiohttp import web
import discord
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
PORT = int(os.getenv("PORT", 8080))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="$", intents=intents)

    async def setup_hook(self):
        initial_extensions = [
            "cogs.ticket",
            "cogs.voice"
        ]
        for ext in initial_extensions:
            try:
                await self.load_extension(ext)
                logging.info(f"成功載入模組：{ext}")
            except Exception as e:
                logging.error(f"載入模組 {ext} 失敗：{e}")

    async def on_ready(self):
        logging.info(f"機器人已上線：{self.user} (ID: {self.user.id})")


async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"Web server 已在 Port {PORT} 啟動")

bot = MyBot()

async def main():
    async with bot:

        await asyncio.gather(
            start_web_server(),
            bot.start(TOKEN)
        )

if __name__ == "__main__":
    if not TOKEN:
        logging.error("未找到 DISCORD_TOKEN 環境變數！")
    else:
        asyncio.run(main())
