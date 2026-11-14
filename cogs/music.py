import asyncio
import datetime
import io
import os
import re
import time
import discord
from discord import app_commands
from discord.ext import commands
import edge_tts
import requests
import yt_dlp

BILIBILI_COOKIE = os.getenv("BILI_COOKIE", "")

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
        self.message = None

    def _create_progress_bar(self):
        if not self.duration:
            return "🔴 ─── 直播或未知長度 ───"
        elapsed = int(time.time() - self.start_time)
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

    @discord.ui.button(label="暫停/繼續", style=discord.ButtonStyle.blurple, emoji="⏯️", row=0)
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc: return await interaction.response.send_message("❌ 機器人不在語音頻道中", ephemeral=True)
        if vc.is_playing():
            vc.pause()
            await interaction.response.edit_message(embed=self._get_embed("已暫停播放"), view=self)
        elif vc.is_paused():
            vc.resume()
            await interaction.response.edit_message(embed=self._get_embed("正在播放"), view=self)

    @discord.ui.button(label="重複: 開", style=discord.ButtonStyle.green, emoji="🔁", row=0)
    async def toggle_loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.is_looping = not self.is_looping
        button.label = f"重複: {'開' if self.is_looping else '關'}"
        button.style = discord.ButtonStyle.green if self.is_looping else discord.ButtonStyle.gray
        await interaction.response.edit_message(embed=self._get_embed(), view=self)

    @discord.ui.button(label="音量 +", style=discord.ButtonStyle.gray, emoji="🔊", row=1)
    async def volume_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc or not vc.source: return await interaction.response.send_message("❌ 目前沒有正在播放的音訊", ephemeral=True)
        self.current_volume = min(self.current_volume + 0.1, 2.0)
        if isinstance(vc.source, discord.PCMVolumeTransformer):
            vc.source.volume = self.current_volume
        await interaction.response.edit_message(embed=self._get_embed(), view=self)

    @discord.ui.button(label="音量 -", style=discord.ButtonStyle.gray, emoji="🔉", row=1)
    async def volume_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc or not vc.source: return await interaction.response.send_message("❌ 目前沒有正在播放的音訊", ephemeral=True)
        self.current_volume = max(self.current_volume - 0.1, 0.0)
        if isinstance(vc.source, discord.PCMVolumeTransformer):
            vc.source.volume = self.current_volume
        await interaction.response.edit_message(embed=self._get_embed(), view=self)

    @discord.ui.button(label="更新進度", style=discord.ButtonStyle.gray, emoji="🔄", row=1)
    async def refresh_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self._get_embed(), view=self)

    @discord.ui.button(label="停止播放", style=discord.ButtonStyle.red, emoji="⏹️", row=2)
    async def stop_player(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.is_looping = False
        self.manual_stop = True
        if interaction.guild.voice_client:
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("⏹️ 已停止播放", ephemeral=True)
            if self.message:
                try: await self.message.edit(embed=self._get_embed("播放結束"), view=self)
                except: pass

    @discord.ui.button(label="退出頻道", style=discord.ButtonStyle.red, emoji="🚪", row=2)
    async def leave_vc(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.is_looping = False
        self.manual_stop = True
        if interaction.guild.voice_client:
            if self.message:
                try: await self.message.edit(embed=self._get_embed("播放結束"), view=self)
                except: pass
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("🚪 已斷開連線", ephemeral=True)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_allowed(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id in self.bot.allowed_ids:
            return True
        if interaction.guild and interaction.user.id == interaction.guild.owner_id:
            return True
        return False

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

        if action == "join":
            if not interaction.user.voice or not interaction.user.voice.channel:
                return await interaction.response.send_message("⚠️ 你必須先進入一個語音頻道！", ephemeral=True)
            voice_channel = interaction.user.voice.channel
            try:
                if interaction.guild.voice_client:
                    await interaction.guild.voice_client.move_to(voice_channel)
                else:
                    await voice_channel.connect()
                await interaction.response.send_message(f"✅ 已成功加入語音頻道：{voice_channel.name}", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ 無法加入語音: `{e}`", ephemeral=True)

        elif action == "leave":
            if interaction.guild.voice_client:
                await interaction.guild.voice_client.disconnect()
                await interaction.response.send_message("🚪 已退出語音頻道", ephemeral=True)
            else:
                await interaction.response.send_message("⚠️ 機器人目前不在語音頻道中", ephemeral=True)

        elif action == "play":
            if not url:
                return await interaction.response.send_message("⚠️ 使用 play 時必須提供音樂網址！", ephemeral=True)
            if not interaction.user.voice:
                return await interaction.response.send_message("⚠️ 請先進入語音頻道", ephemeral=True)

            if not interaction.guild.voice_client:
                try:
                    await interaction.user.voice.channel.connect(reconnect=True, timeout=20)
                except Exception as e:
                    return await interaction.response.send_message(f"❌ 無法進入頻道: `{e}`", ephemeral=True)

            vc = interaction.guild.voice_client
            if vc.is_playing() or vc.is_paused():
                vc.stop()
                await asyncio.sleep(1)

            await interaction.response.defer(ephemeral=True)

            is_bilibili = "bilibili.com" in url or "b23.tv" in url
            b_audio_url = None
            b_title, b_uploader, b_duration = 'Bilibili Audio', 'Bilibili UP主', 0

            if is_bilibili:
                try:
                    bvid = None
                    bv_match = re.search(r'BV[a-zA-Z0-9]{10}', url)
                    if bv_match:
                        bvid = bv_match.group(0)
                    if bvid:
                        b_headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                            "Referer": "https://www.bilibili.com/",
                            "Cookie": BILIBILI_COOKIE
                        }
                        res = requests.get(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}", headers=b_headers)
                        if res.status_code == 200:
                            b_data = res.json().get('data', {})
                            if b_data:
                                b_title = b_data.get('title', 'Bilibili Audio')
                                b_uploader = b_data.get('owner', {}).get('name', '未知UP主')
                                b_duration = b_data.get('duration', 0)
                                cid = b_data.get('cid')
                                play_res = requests.get(
                                    f"https://api.bilibili.com/x/player/wbi/playurl?bvid={bvid}&cid={cid}&fnval=16",
                                    headers=b_headers
                                )
                                if play_res.status_code == 200:
                                    p_data = play_res.json().get('data', {})
                                    if 'dash' in p_data and p_data['dash'].get('audio'):
                                        b_audio_url = p_data['dash']['audio'][0].get('baseUrl')
                except:
                    pass

            try:
                if is_bilibili and b_audio_url:
                    title, uploader, duration, play_source_url = b_title, b_uploader, b_duration, b_audio_url
                else:
                    ydl_opts = {
                        'format': 'bestaudio/best', 
                        'quiet': True, 
                        'noplaylist': True,
                        'skip_download': True,
                    }
                    def fetch_info():
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            return ydl.extract_info(url, download=False)
                    info = await self.bot.loop.run_in_executor(None, fetch_info)
                    if 'entries' in info:
                        if not info['entries']: raise Exception("搜尋結果為空")
                        info = info['entries'][0]
                    title = info.get('title', '未知歌曲')
                    uploader = info.get('uploader', '未知來源')
                    duration = info.get('duration')
                    play_source_url = info['url']

                local_ffmpeg = os.path.join(os.getcwd(), "runtime_bin", "ffmpeg")
                ffmpeg_exe = local_ffmpeg if os.path.exists(local_ffmpeg) else "ffmpeg"

                if is_bilibili:
                    ffmpeg_opts = {
                        'before_options': f'-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -headers "Referer: https://www.bilibili.com/\r\nUser-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\nCookie: {BILIBILI_COOKIE}\r\n"',
                        'options': '-vn -ac 2 -ar 48000'
                    }
                else:
                    ffmpeg_opts = {
                        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -analyzeduration 0 -probesize 32',
                        'options': '-vn -ac 2 -ar 48000'
                    }

                source = discord.FFmpegPCMAudio(play_source_url, executable=ffmpeg_exe, **ffmpeg_opts)
                view = PlayerControlView(interaction, url, play_source_url, title, duration, uploader)
                volume_source = discord.PCMVolumeTransformer(source, volume=view.current_volume)

                def after_play(error):
                    if error:
                        print(f"FFmpeg 播放錯誤: {error}")
                    if view.manual_stop: return
                    if view.is_looping and interaction.guild.voice_client:
                        view.start_time = time.time()
                        def re_play():
                            if interaction.guild.voice_client and not interaction.guild.voice_client.is_playing():
                                s = discord.FFmpegPCMAudio(play_source_url, executable=ffmpeg_exe, **ffmpeg_opts)
                                vs = discord.PCMVolumeTransformer(s, volume=view.current_volume)
                                interaction.guild.voice_client.play(vs, after=after_play)
                        self.bot.loop.call_soon_threadsafe(re_play)

                interaction.guild.voice_client.play(volume_source, after=after_play)
                msg = await interaction.channel.send(embed=view._get_embed(), view=view)
                view.message = msg
                await interaction.followup.send("✅ 音樂開始播放", ephemeral=True)
            except Exception as e:
                print(f"播放過程發生例外狀況: {e}")
                await interaction.followup.send(f"❌ 播放失敗: `{str(e)[:100]}`", ephemeral=True)
                
    @app_commands.command(name="stop", description="停止當前音樂播放")
    async def stop_music(self, interaction: discord.Interaction):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)
        if interaction.guild.voice_client:
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("⏹️ 已停止播放", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ 機器人不在語音頻道中", ephemeral=True)

   @app_commands.command(name="tts", description="文字轉語音朗讀")
    @app_commands.choices(lang=[
        app_commands.Choice(name="國語 (TW)", value="zh-TW-HsiaoChenNeural"),
        app_commands.Choice(name="粵語 (HK)", value="zh-HK-WanLungNeural"),
        app_commands.Choice(name="簡中 (CN)", value="zh-CN-XiaoxiaoNeural"),
        app_commands.Choice(name="日語 (JP)", value="ja-JP-NanamiNeural"),
        app_commands.Choice(name="英語 (EN)", value="en-US-AriaNeural")
    ])
    @app_commands.describe(text="要朗讀的文字", lang="選擇語言 (未選則預設國語)")
    async def tts(self, interaction: discord.Interaction, text: str, lang: str = "zh-TW-HsiaoChenNeural"):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)

        if not interaction.user.voice:
            return await interaction.response.send_message("❌ 你必須先加入一個語音頻道！", ephemeral=True)

        vc = interaction.guild.voice_client
        if not vc:
            try:
                vc = await interaction.user.voice.channel.connect(reconnect=True, timeout=20)
            except Exception as e:
                return await interaction.response.send_message(f"❌ 無法進入頻道: `{e}`", ephemeral=True)
        elif vc.channel != interaction.user.voice.channel:
            await vc.move_to(interaction.user.voice.channel)

        if vc.is_playing() or vc.is_paused():
            vc.stop()
            await asyncio.sleep(0.5)

        try:
            await interaction.response.defer(ephemeral=True)
            communicate = edge_tts.Communicate(text, lang)
            audio_data = b""
            async async_generator in [communicate.stream()]:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_data += chunk["data"]

            if not audio_data:
                return await interaction.followup.send("❌ TTS 生成語音資料失敗（內容為空）", ephemeral=True)

            audio_fp = io.BytesIO(audio_data)
            local_ffmpeg = os.path.join(os.getcwd(), "runtime_bin", "ffmpeg")
            ffmpeg_exe = local_ffmpeg if os.path.exists(local_ffmpeg) else "ffmpeg"
            ffmpeg_opts = {
                'before_options': '-f mp3 -loglevel warning',
                'options': '-vn -ac 2 -ar 48000 -b:a 128k'
            }

            source = discord.FFmpegPCMAudio(
                audio_fp,
                pipe=True,
                executable=ffmpeg_exe,
                **ffmpeg_opts
            )
            volume_source = discord.PCMVolumeTransformer(source, volume=1.0)
            
            vc.play(volume_source)
            await interaction.followup.send(f"🎤 正在朗讀：\"{text}\"", ephemeral=True)
        except Exception as e:
            print(f"TTS 播放發生例外狀況: {e}")
            await interaction.followup.send(f"❌ TTS 播放失敗: `{str(e)[:100]}`", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Music(bot))
