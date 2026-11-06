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
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

ALLOWED_IDS = [1008278721007992863, 1359813653544566815]
bot.allowed_ids = ALLOWED_IDS

@bot.event
async def on_ready():
    print(f'系統連線成功 | 帳號: {bot.user}')

async def main():
    async with bot:
        extensions = [
            "cogs.admin",
            "cogs.music",
            "cogs.utility",
            "cogs.trap"
        ]
        for ext in extensions:
            try:
                await bot.load_extension(ext)
                print(f"成功載入模組: {ext}")
            except Exception as e:
                print(f"載入模組 {ext} 失敗: {e}")
        
        token = os.environ.get("TOKEN")
        if not token:
            print("找不到 TOKEN 環境變數！")
            return
        
        keep_alive()
        await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
