import os
import asyncio
import logging
from threading import Thread
from flask import Flask, render_template
import discord
from discord.ext import commands

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    t = Thread(target=run, daemon=True)
    t.start()

intents = discord.Intents.all()

EXTENSIONS = [
    "cogs.admin",
    "cogs.music",
    "cogs.tools",
    "cogs.security",
    "cogs.ticket",
    "cogs.voice",
]

class ServiceBot(commands.Bot):
    async def setup_hook(self):
        for ext in EXTENSIONS:
            try:
                await self.load_extension(ext)
                logging.info(f"成功載入模組: {ext}")
            except Exception:
                logging.exception(f"載入模組 {ext} 失敗")

        try:
            synced = await self.tree.sync()
            logging.info(f"✅ 成功同步了 {len(synced)} 個斜槓指令: {[c.name for c in synced]}")
        except Exception:
            logging.exception("❌ 同步指令發生錯誤")

bot = ServiceBot(command_prefix="!", intents=intents, help_command=None)

ALLOWED_IDS = [1008278721007992863, 1359813653544566815]
bot.allowed_ids = ALLOWED_IDS

@bot.event
async def on_ready():
    logging.info(f"機器人已成功登入: {bot.user}")

async def main():
    token = os.environ.get("TOKEN")
    if not token:
        logging.error("找不到 TOKEN 環境變數！")
        return

    keep_alive()
    async with bot:
        await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
