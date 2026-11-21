import os
import io
import json
import asyncio
import importlib.metadata
import importlib.util
import logging
import shutil
from threading import Thread

from flask import Flask, render_template
import discord
from discord import app_commands
from discord.ext import commands

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

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

STORE_CHANNEL_ID = int(os.environ.get("STORE_CHANNEL_ID", "0") or 0)
STATE_KEYS = ("config_db", "whitelist_db", "op_access_db", "autoban_db")
STATE_FILENAME = "bot_state.json"


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
        self.state_message = None
        self.state_lock = asyncio.Lock()
        for key in STATE_KEYS:
            setattr(self, key, {})

    def build_state_file(self) -> discord.File:
        payload = {key: {str(k): v for k, v in getattr(self, key).items()} for key in STATE_KEYS}
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        return discord.File(io.BytesIO(data), filename=STATE_FILENAME)

    async def load_state(self):
        if not STORE_CHANNEL_ID:
            logging.warning("未設定 STORE_CHANNEL_ID，設定資料在重啟後會遺失")
            return

        try:
            channel = await self.fetch_channel(STORE_CHANNEL_ID)
            async for message in channel.history(limit=50):
                if message.author.id != self.user.id:
                    continue
                attachment = next((a for a in message.attachments if a.filename == STATE_FILENAME), None)
                if not attachment:
                    continue
                data = json.loads((await attachment.read()).decode("utf-8"))
                for key in STATE_KEYS:
                    raw = data.get(key, {})
                    setattr(self, key, {int(k): v for k, v in raw.items()})
                self.state_message = message
                counts = {key: len(getattr(self, key)) for key in STATE_KEYS}
                logging.info(f"已載入設定資料: {counts}")
                return
            logging.info("找不到既有的設定檔，第一次儲存時會自動建立")
        except Exception:
            logging.exception("讀取設定資料失敗，請確認 STORE_CHANNEL_ID 與機器人在該頻道的權限")

    async def save_state(self):
        if not STORE_CHANNEL_ID:
            return

        async with self.state_lock:
            try:
                if self.state_message:
                    try:
                        self.state_message = await self.state_message.edit(attachments=[self.build_state_file()])
                        return
                    except discord.NotFound:
                        self.state_message = None

                channel = await self.fetch_channel(STORE_CHANNEL_ID)
                self.state_message = await channel.send(
                    content="🗂️ 機器人設定資料（請勿刪除此訊息）",
                    file=self.build_state_file(),
                )
                logging.info("已建立設定檔訊息")
            except Exception:
                logging.exception("儲存設定資料失敗")

    async def setup_hook(self):
        logging.info(f"discord.py 版本: {discord.__version__}")
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

        await self.load_state()

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
