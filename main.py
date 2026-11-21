import os
import asyncio
import importlib.util
import logging
import shutil
from threading import Thread
from flask import Flask, render_template
import discord
from discord import app_commands
from discord.ext import commands
import importlib.metadata


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logging.getLogger("discord.voice_state").setLevel(logging.DEBUG)
logging.getLogger("discord.voice_client").setLevel(logging.DEBUG)

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


def run():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))


def keep_alive():
    Thread(target=run, daemon=True).start()


EXTENSIONS = [
    "cogs.admin",
    "cogs.music",
    "cogs.tools",
    "cogs.security",
    "cogs.ticket",
    "cogs.voice",
]

ALLOWED_IDS = [1008278721007992863, 1359813653544566815]


def describe_commands(tree: app_commands.CommandTree):
    lines = []
    for cmd in tree.walk_commands():
        if isinstance(cmd, app_commands.Command):
            lines.append(f"/{cmd.qualified_name}: {[p.name for p in cmd.parameters]}")
    return lines


class ServiceBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all(), help_command=None)
        self.allowed_ids = ALLOWED_IDS
        self.guild_cleanup_done = False

    async def setup_hook(self):
        logging.info(f"discord.py 版本: {discord.__version__}")
        logging.info(f"davey 已安裝: {importlib.util.find_spec('davey') is not None}")
        logging.info(f"davey 版本: {importlib.metadata.version('davey')}")
        logging.info(f"PyNaCl 已安裝: {importlib.util.find_spec('nacl') is not None}")
        if not discord.opus.is_loaded():
            for name in ("libopus.so.0", "libopus.so", "opus"):
                try:
                    discord.opus.load_opus(name)
                    break
                except Exception:
                    continue
        logging.info(f"Opus 已載入: {discord.opus.is_loaded()}")
        logging.info(f"ffmpeg 路徑: {shutil.which('ffmpeg')}")

        for ext in EXTENSIONS:
            try:
                await self.load_extension(ext)
                logging.info(f"成功載入模組: {ext}")
            except Exception:
                logging.exception(f"載入模組 {ext} 失敗")

        for line in describe_commands(self.tree):
            logging.info(f"本機指令定義 {line}")

        try:
            synced = await self.tree.sync()
            logging.info(f"✅ 全域同步完成，共 {len(synced)} 個頂層指令: {[c.name for c in synced]}")
        except Exception:
            logging.exception("❌ 全域同步指令發生錯誤")

    async def on_ready(self):
        logging.info(f"機器人已登入: {self.user} (ID: {self.user.id})，所在伺服器數: {len(self.guilds)}")

        if os.environ.get("CLEAN_GUILD_COMMANDS") == "1" and not self.guild_cleanup_done:
            self.guild_cleanup_done = True
            for guild in self.guilds:
                try:
                    self.tree.clear_commands(guild=guild)
                    await self.tree.sync(guild=guild)
                    logging.info(f"已清除伺服器專屬指令: {guild.name}")
                except Exception:
                    logging.exception(f"清除伺服器專屬指令失敗: {guild.name}")


bot = ServiceBot()


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
