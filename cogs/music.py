import asyncio
import io
import logging
import os
import re
import time

import discord
from discord import app_commands
from discord.ext import commands
import edge_tts
import requests
import yt_dlp

BILIBILI_COOKIE = os.getenv("BILI_COOKIE", "").replace("\r", "").replace("\n", "").replace('"', "")


def get_ffmpeg_path() -> str:
    local_ffmpeg = os.path.join(os.getcwd(), "runtime_bin", "ffmpeg")
    return local_ffmpeg if os.path.exists(local_ffmpeg) else "ffmpeg"


def fetch_bilibili_info(url: str):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.bilibili.com/",
            "Cookie": BILIBILI_COOKIE,
        }
        if "b23.tv" in url:
            url = requests.get(url, headers=headers, allow_redirects=True, timeout=10).url

        match = re.search(r"BV[a-zA-Z0-9]{10}", url)
        if not match:
            return None
        bvid = match.group(0)

        res = requests.get(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}", headers=headers, timeout=10)
        if res.status_code != 200:
            return None
        data = res.json().get("data") or {}
        if not data:
            return None

        play_res = requests.get(
            f"https://api.bilibili.com/x/player/wbi/playurl?bvid={bvid}&cid={data.get('cid')}&fnval=16",
            headers=headers,
            timeout=10,
        )
        if play_res.status_code != 200:
            return None
        p_data = play_res.json().get("data") or {}
        audio = (p_data.get("dash") or {}).get("audio") or []
        if not audio or not audio[0].get("baseUrl"):
            return None

        return (
            data.get("title", "Bilibili Audio"),
            (data.get("owner") or {}).get("name", "未知UP主"),
            data.get("duration", 0),
            audio[0]["baseUrl"],
        )
    except Exception as e:
        logging.warning(f"Bilibili 解析失敗: {e}")
        return None


class PlayerControlView(discord.ui.View):
    def __init__(self, interaction, url, audio_url, title, duration, uploader):
        super().__init__(timeout=None)
        self.initial_interaction = interaction
        self.url = url
        self.audio_url = audio_url
        self.title = title
        self.duration = duration
        self.uploader = uploader
        self.is_looping = True
        self.manual_stop = False
        self.current_volume = 1.0
        self.start_time = time.time()
        self.paused_at = None
        self.paused_total = 0
        self.message = None

    def _elapsed(self) -> int:
        now = time.time()
        paused = self.paused_total + ((now - self.paused_at) if self.paused_at else 0)
        return max(0, int(now - self.start_time - paused))

    def _create_progress_bar(self):
        if not self.duration:
            return "🔴 ─── 直播或未知長度 ───"
        elapsed = self._elapsed()
        total = int(self.duration)
        if elapsed > total:
            elapsed = total
        bar_length = 20
        progress_position = int((elapsed / total) * bar_length) if total > 0 else 0
        progress_position = min(max(progress_position, 0), bar_length - 1)
        bar = "".join(["▬" if i != progress_position else "🔵" for i in range(bar_length)])
        elapsed_str = f"{elapsed // 60}:{elapsed % 60:02d}"
        total_str = f"{total // 60}:{total % 60:02d}"
        return f"`{elapsed_str}` {bar} `{total_str}`"

    def _get_embed(self, status="正在播放"):
        embed = discord.Embed(title=f"🎵 {status}", color=0x3498db if status == "正在播放" else 0x95a5a6)
        embed.add_field(name="🎵 歌名", value=f"[{self.title}]({self.url})", inline=False)
        embed.add_field(name="📤 上傳者", value=self.uploader, inline=True)
        embed.add_field(name="🔊 音量", value=f"{int(self.current_volume * 100)}%", inline=True)
        embed.add_field(name="⏱️ 播放進度", value=self._create_progress_bar(), inline=False)
        embed.set_footer(text=f"🔄 自動循環: {'開啟' if self.is_looping else '關閉'}")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cog = interaction.client.get_cog("Music")
        if cog and cog.sessions.get(interaction.guild.id) is not self:
            await interaction.response.send_message("❌ 此播放面板已失效（已有新的播放或已結束）", ephemeral=True)
            return False

        vc = interaction.guild.voice_client
        user_vc = interaction.user.voice.channel if interaction.user.voice else None
        privileged = (
            interaction.user.id in interaction.client.allowed_ids
            or interaction.user.id == interaction.guild.owner_id
        )
        if privileged or (vc and user_vc and user_vc == vc.channel):
            return True

        await interaction.response.send_message("❌ 你必須和機器人在同一個語音頻道才能操作。", ephemeral=True)
        return False

    @discord.ui.button(label="暫停/繼續", style=discord.ButtonStyle.blurple, emoji="⏯️", row=0)
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message("❌ 機器人不在語音頻道中", ephemeral=True)
        if vc.is_playing():
            vc.pause()
            self.paused_at = time.time()
            await interaction.response.edit_message(embed=self._get_embed("已暫停播放"), view=self)
        elif vc.is_paused():
            vc.resume()
            if self.paused_at:
                self.paused_total += time.time() - self.paused_at
                self.paused_at = None
            await interaction.response.edit_message(embed=self._get_embed("正在播放"), view=self)
        else:
            await interaction.response.send_message("⚠️ 目前沒有正在播放的音訊", ephemeral=True)

    @discord.ui.button(label="重複: 開", style=discord.ButtonStyle.green, emoji="🔁", row=0)
    async def toggle_loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.is_looping = not self.is_looping
        button.label = f"重複: {'開' if self.is_looping else '關'}"
        button.style = discord.ButtonStyle.green if self.is_looping else discord.ButtonStyle.gray
        await interaction.response.edit_message(embed=self._get_embed(), view=self)

    @discord.ui.button(label="音量 +", style=discord.ButtonStyle.gray, emoji="🔊", row=1)
    async def volume_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc or not vc.source:
            return await interaction.response.send_message("❌ 目前沒有正在播放的音訊", ephemeral=True)
        self.current_volume = min(self.current_volume + 0.1, 2.0)
        if isinstance(vc.source, discord.PCMVolumeTransformer):
            vc.source.volume = self.current_volume
        await interaction.response.edit_message(embed=self._get_embed(), view=self)

    @discord.ui.button(label="音量 -", style=discord.ButtonStyle.gray, emoji="🔉", row=1)
    async def volume_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc or not vc.source:
            return await interaction.response.send_message("❌ 目前沒有正在播放的音訊", ephemeral=True)
        self.current_volume = max(self.current_volume - 0.1, 0.0)
        if isinstance(vc.source, discord.PCMVolumeTransformer):
            vc.source.volume = self.current_volume
        await interaction.response.edit_message(embed=self._get_embed(), view=self)

    @discord.ui.button(label="更新進度", style=discord.ButtonStyle.gray, emoji="🔄", row=1)
    async def refresh_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self._get_embed(), view=self)

    @discord.ui.button(label="停止播放", style=discord.ButtonStyle.red, emoji="⏹️", row=2)
    async def stop_player(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message("❌ 機器人不在語音頻道中", ephemeral=True)
        await interaction.response.send_message("⏹️ 已停止播放", ephemeral=True)
        cog = interaction.client.get_cog("Music")
        if cog:
            await cog._stop_playback(interaction.guild)
        else:
            self.is_looping = False
            self.manual_stop = True
            vc.stop()

    @discord.ui.button(label="退出頻道", style=discord.ButtonStyle.red, emoji="🚪", row=2)
    async def leave_vc(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message("❌ 機器人不在語音頻道中", ephemeral=True)
        await interaction.response.send_message("🚪 已斷開連線", ephemeral=True)
        cog = interaction.client.get_cog("Music")
        if cog:
            await cog._stop_playback(interaction.guild)
        else:
            self.is_looping = False
            self.manual_stop = True
        await vc.disconnect()


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sessions: dict[int, PlayerControlView] = {}

    def is_allowed(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return False
        uid = interaction.user.id
        if uid in self.bot.allowed_ids:
            return True
        if uid == interaction.guild.owner_id:
            return True
        if uid in getattr(self.bot, "op_access_db", {}).get(interaction.guild_id, []):
            return True
        return False

    async def _ensure_connected(self, guild: discord.Guild, channel: discord.VoiceChannel):
        vc = guild.voice_client
        if vc is None:
            return await channel.connect(reconnect=True, timeout=20)
        if vc.channel != channel:
            await vc.move_to(channel)
        return vc

    async def _safe_edit(self, message: discord.Message, view: PlayerControlView):
        try:
            await message.edit(embed=view._get_embed("播放結束"), view=None)
        except discord.HTTPException:
            pass

    async def _stop_playback(self, guild: discord.Guild):
        view = self.sessions.pop(guild.id, None)
        if view:
            view.is_looping = False
            view.manual_stop = True
        vc = guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
        if view and view.message:
            await self._safe_edit(view.message, view)

    def _play_with_loop(self, guild: discord.Guild, view: PlayerControlView, ffmpeg_opts: dict):
        source = discord.FFmpegPCMAudio(view.audio_url, executable=get_ffmpeg_path(), **ffmpeg_opts)
        volume_source = discord.PCMVolumeTransformer(source, volume=view.current_volume)
        guild.voice_client.play(
            volume_source,
            after=lambda err: self._after_play(err, guild, view, ffmpeg_opts),
        )

    def _after_play(self, error, guild: discord.Guild, view: PlayerControlView, ffmpeg_opts: dict):
        if error:
            logging.error(f"FFmpeg 播放錯誤: {error}")
        if view.manual_stop or self.sessions.get(guild.id) is not view:
            return

        def next_step():
            if view.manual_stop or self.sessions.get(guild.id) is not view:
                return
            vc = guild.voice_client
            if view.is_looping and not error and vc and vc.is_connected() and not vc.is_playing():
                try:
                    view.start_time = time.time()
                    view.paused_at = None
                    view.paused_total = 0
                    self._play_with_loop(guild, view, ffmpeg_opts)
                    return
                except Exception:
                    logging.exception("循環播放失敗")
            self.sessions.pop(guild.id, None)
            if view.message:
                self.bot.loop.create_task(self._safe_edit(view.message, view))

        self.bot.loop.call_soon_threadsafe(next_step)

    @app_commands.command(name="music", description="語音頻道連線與音樂播放")
    @app_commands.choices(action=[
        app_commands.Choice(name="join", value="join"),
        app_commands.Choice(name="leave", value="leave"),
        app_commands.Choice(name="play", value="play")
    ])
    @app_commands.describe(action="選擇動作", url="音樂網址 (僅play時需要)")
    async def music_command(self, interaction: discord.Interaction, action: str, url: str = None):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        user_vc = interaction.user.voice.channel if interaction.user.voice else None

        if action == "join":
            if not user_vc:
                return await interaction.followup.send("⚠️ 你必須先進入一個語音頻道！", ephemeral=True)
            try:
                await self._ensure_connected(guild, user_vc)
                await interaction.followup.send(f"✅ 已成功加入語音頻道：{user_vc.name}", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"❌ 無法加入語音: `{e}`", ephemeral=True)

        elif action == "leave":
            vc = guild.voice_client
            if not vc:
                return await interaction.followup.send("⚠️ 機器人目前不在語音頻道中", ephemeral=True)
            await self._stop_playback(guild)
            await vc.disconnect()
            await interaction.followup.send("🚪 已退出語音頻道", ephemeral=True)

        elif action == "play":
            await self._play(interaction, url, user_vc)

    async def _play(self, interaction: discord.Interaction, url: str, user_vc):
        guild = interaction.guild

        if not url:
            return await interaction.followup.send("⚠️ 使用 play 時必須提供音樂網址！", ephemeral=True)
        if not user_vc:
            return await interaction.followup.send("⚠️ 請先進入語音頻道", ephemeral=True)

        try:
            await self._ensure_connected(guild, user_vc)
        except Exception as e:
            return await interaction.followup.send(f"❌ 無法進入頻道: `{e}`", ephemeral=True)

        await self._stop_playback(guild)
        await asyncio.sleep(0.3)

        loop = asyncio.get_running_loop()
        is_bilibili = "bilibili.com" in url or "b23.tv" in url
        bili = await loop.run_in_executor(None, fetch_bilibili_info, url) if is_bilibili else None

        view = None
        try:
            if bili:
                title, uploader, duration, play_source_url = bili
            else:
                ydl_opts = {
                    "format": "bestaudio/best",
                    "quiet": True,
                    "noplaylist": True,
                    "skip_download": True,
                }

                def fetch_info():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        return ydl.extract_info(url, download=False)

                info = await loop.run_in_executor(None, fetch_info)
                if "entries" in info:
                    if not info["entries"]:
                        raise Exception("搜尋結果為空")
                    info = info["entries"][0]
                title = info.get("title", "未知歌曲")
                uploader = info.get("uploader", "未知來源")
                duration = info.get("duration")
                play_source_url = info["url"]

            if is_bilibili:
                ffmpeg_opts = {
                    "before_options": f'-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -headers "Referer: https://www.bilibili.com/\r\nUser-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\nCookie: {BILIBILI_COOKIE}\r\n"',
                    "options": "-vn -ac 2 -ar 48000",
                }
            else:
                ffmpeg_opts = {
                    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -analyzeduration 0 -probesize 32",
                    "options": "-vn -ac 2 -ar 48000",
                }

            view = PlayerControlView(interaction, url, play_source_url, title, duration, uploader)
            self.sessions[guild.id] = view
            self._play_with_loop(guild, view, ffmpeg_opts)

            msg = await interaction.channel.send(embed=view._get_embed(), view=view)
            view.message = msg
            await interaction.followup.send("✅ 音樂開始播放", ephemeral=True)

        except Exception as e:
            logging.exception("播放過程發生例外狀況")
            if view and self.sessions.get(guild.id) is view:
                self.sessions.pop(guild.id, None)
            await interaction.followup.send(f"❌ 播放失敗: `{str(e)[:100]}`", ephemeral=True)

    @app_commands.command(name="stop", description="停止當前音樂播放")
    async def stop_music(self, interaction: discord.Interaction):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)
        if not interaction.guild.voice_client:
            return await interaction.response.send_message("⚠️ 機器人不在語音頻道中", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        await self._stop_playback(interaction.guild)
        await interaction.followup.send("⏹️ 已停止播放", ephemeral=True)

    @app_commands.command(name="tts", description="文字轉語音朗讀")
    @app_commands.choices(lang=[
        app_commands.Choice(name="國語 (TW)", value="zh-TW-HsiaoChenNeural"),
        app_commands.Choice(name="粵語 (HK)", value="zh-HK-WanLungNeural"),
        app_commands.Choice(name="簡中 (CN)", value="zh-CN-XiaoxiaoNeural"),
        app_commands.Choice(name="日語 (JP)", value="ja-JP-NanamiNeural"),
        app_commands.Choice(name="英語 (EN)", value="en-US-AriaNeural")
    ])
    @app_commands.describe(text="要朗讀的文字 (最多 300 字)", lang="選擇語言 (未選則預設國語)")
    async def tts(self, interaction: discord.Interaction, text: app_commands.Range[str, 1, 300], lang: str = "zh-TW-HsiaoChenNeural"):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        user_vc = interaction.user.voice.channel if interaction.user.voice else None
        if not user_vc:
            return await interaction.followup.send("❌ 你必須先加入一個語音頻道！", ephemeral=True)

        try:
            vc = await self._ensure_connected(interaction.guild, user_vc)
        except Exception as e:
            return await interaction.followup.send(f"❌ 無法進入頻道: `{e}`", ephemeral=True)

        await self._stop_playback(interaction.guild)
        await asyncio.sleep(0.3)

        try:
            communicate = edge_tts.Communicate(text, lang)
            chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    chunks.append(chunk["data"])
            audio_data = b"".join(chunks)

            if not audio_data:
                return await interaction.followup.send("❌ TTS 生成語音資料失敗（內容為空）", ephemeral=True)

            source = discord.FFmpegPCMAudio(
                io.BytesIO(audio_data),
                pipe=True,
                executable=get_ffmpeg_path(),
                before_options="-f mp3 -loglevel warning",
                options="-vn -ac 2 -ar 48000 -b:a 128k",
            )
            vc.play(discord.PCMVolumeTransformer(source, volume=1.0))
            await interaction.followup.send(f"🎤 正在朗讀：\"{text}\"", ephemeral=True)
        except Exception as e:
            logging.exception("TTS 播放發生例外狀況")
            await interaction.followup.send(f"❌ TTS 播放失敗: `{str(e)[:100]}`", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Music(bot))
