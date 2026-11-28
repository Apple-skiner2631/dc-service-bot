import asyncio
import hashlib
import hmac
import logging
import os
import time
from collections import deque
from functools import wraps

import discord
import psutil
from flask import jsonify, request, session

from cogs.welcome import DEFAULT_WELCOME, MAX_ROLES, publish_selfrole

STARTED_AT = time.time()
PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "")
failures = {}

SETTING_TYPES = {
    "room": discord.VoiceChannel,
    "trap": discord.TextChannel,
    "punish": discord.TextChannel,
    "ticket_panel": discord.TextChannel,
    "ticket_pending": discord.CategoryChannel,
    "ticket_resolved": discord.CategoryChannel,
}


class LogBuffer(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = deque(maxlen=200)
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

    def emit(self, record):
        self.lines.append(self.format(record))


LOG_BUFFER = LogBuffer()


def register_dashboard(app, bot):
    if LOG_BUFFER not in logging.getLogger().handlers:
        logging.getLogger().addHandler(LOG_BUFFER)
    secret = f"dash:{PASSWORD}:{os.environ.get('TOKEN', '')}"
    app.secret_key = hashlib.sha256(secret.encode()).hexdigest()
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=True,
        PERMANENT_SESSION_LIFETIME=43200,
    )

    def client_ip():
        return request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()

    def run_on_bot(coro, timeout=15):
        return asyncio.run_coroutine_threadsafe(coro, bot.loop).result(timeout=timeout)

    def guarded(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not PASSWORD:
                return jsonify(error="尚未設定 DASHBOARD_PASSWORD"), 503
            if session.get("ok") is not True:
                return jsonify(error="未登入"), 401
            if request.method == "POST" and not request.is_json:
                return jsonify(error="請求格式錯誤"), 400
            if not bot.is_ready():
                return jsonify(error="機器人尚未就緒"), 503
            return fn(*args, **kwargs)
        return wrapper

    def channel_name(guild, config, key):
        channel_id = config.get(key)
        channel = guild.get_channel(channel_id) if channel_id else None
        return channel.name if channel else None

    @app.get("/api/session")
    def session_info():
        return jsonify(configured=bool(PASSWORD), authed=bool(PASSWORD) and session.get("ok") is True)

    @app.post("/api/login")
    def login():
        if not PASSWORD:
            return jsonify(error="尚未設定 DASHBOARD_PASSWORD"), 503
        ip = client_ip()
        now = time.time()
        recent = [t for t in failures.get(ip, []) if now - t < 600]
        if len(recent) >= 5:
            return jsonify(error="嘗試次數過多，請 10 分鐘後再試"), 429
        data = request.get_json(silent=True) or {}
        if hmac.compare_digest(str(data.get("password", "")).encode(), PASSWORD.encode()):
            session.clear()
            session["ok"] = True
            session.permanent = True
            failures.pop(ip, None)
            return jsonify(ok=True)
        recent.append(now)
        failures[ip] = recent
        return jsonify(error="密碼錯誤"), 401

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.get("/api/status")
    @guarded
    def status():
        latency = bot.latency
        latency_ms = round(latency * 1000) if latency == latency and latency != float("inf") else None
        guilds = []
        music = bot.get_cog("Music")
        for guild in bot.guilds:
            config = bot.config_db.get(guild.id, {})
            session_view = music.sessions.get(guild.id) if music else None
            guilds.append({
                "id": str(guild.id),
                "name": guild.name,
                "members": guild.member_count,
                "autoban": bool(bot.autoban_db.get(guild.id, False)),
                "room": channel_name(guild, config, "room"),
                "trap": channel_name(guild, config, "trap"),
                "punish": channel_name(guild, config, "punish"),
                "ticket": channel_name(guild, config, "ticket_panel"),
                "voice": guild.voice_client.channel.name if guild.voice_client else None,
                "playing": session_view.title if session_view else None,
            })
        return jsonify(
            bot=str(bot.user),
            latency=latency_ms,
            uptime=int(time.time() - STARTED_AT),
            memory=psutil.Process().memory_info().rss // (1024 * 1024),
            guilds=guilds,
        )

    @app.get("/api/guilds/<guild_id>/channels")
    @guarded
    def channels(guild_id):
        guild = bot.get_guild(int(guild_id)) if guild_id.isdigit() else None
        if not guild:
            return jsonify(error="找不到伺服器"), 404
        items = [
            {"id": str(ch.id), "name": ch.name}
            for ch in guild.text_channels
            if ch.permissions_for(guild.me).send_messages
        ]
        return jsonify(channels=items)

    @app.post("/api/guilds/<guild_id>/autoban")
    @guarded
    def autoban(guild_id):
        guild = bot.get_guild(int(guild_id)) if guild_id.isdigit() else None
        if not guild:
            return jsonify(error="找不到伺服器"), 404
        enabled = bool((request.get_json(silent=True) or {}).get("enabled"))
        bot.autoban_db[guild.id] = enabled
        run_on_bot(bot.save_state())
        return jsonify(ok=True, enabled=enabled)

    @app.post("/api/send")
    @guarded
    def send():
        data = request.get_json(silent=True) or {}
        content = str(data.get("content", "")).strip()
        if not content or len(content) > 2000:
            return jsonify(error="訊息長度需為 1 到 2000 字"), 400
        raw_id = str(data.get("channel_id", ""))
        channel = bot.get_channel(int(raw_id)) if raw_id.isdigit() else None
        if not isinstance(channel, discord.TextChannel):
            return jsonify(error="找不到文字頻道"), 404
        try:
            run_on_bot(channel.send(content, allowed_mentions=discord.AllowedMentions.none()))
        except Exception as e:
            return jsonify(error=f"發送失敗: {e}"), 500
        return jsonify(ok=True)

    async def do_restart():
        await bot.save_state()
        await asyncio.sleep(1)
        await bot.close()
        os._exit(1)

    @app.post("/api/restart")
    @guarded
    def restart():
        asyncio.run_coroutine_threadsafe(do_restart(), bot.loop)
        return jsonify(ok=True)

    @app.get("/api/logs")
    @guarded
    def logs():
        return jsonify(lines=list(LOG_BUFFER.lines))

    @app.get("/api/guilds/<guild_id>/settings")
    @guarded
    def get_settings(guild_id):
        guild = bot.get_guild(int(guild_id)) if guild_id.isdigit() else None
        if not guild:
            return jsonify(error="找不到伺服器"), 404
        config = bot.config_db.get(guild.id, {})

        def items(seq):
            return [{"id": str(c.id), "name": c.name} for c in seq]

        return jsonify(
            text=items(guild.text_channels),
            voice=items(guild.voice_channels),
            categories=items(guild.categories),
            roles=items(r for r in reversed(guild.roles) if not r.is_default() and not r.managed),
            config={key: (str(config[key]) if config.get(key) else None) for key in SETTING_TYPES},
            staff=[str(r) for r in config.get("ticket_staff", [])],
        )

    @app.post("/api/guilds/<guild_id>/settings")
    @guarded
    def set_setting(guild_id):
        guild = bot.get_guild(int(guild_id)) if guild_id.isdigit() else None
        if not guild:
            return jsonify(error="找不到伺服器"), 404
        data = request.get_json(silent=True) or {}
        key = data.get("key")
        expected = SETTING_TYPES.get(key)
        if not expected:
            return jsonify(error="未知的設定項目"), 400
        config = bot.config_db.setdefault(guild.id, {})
        value = data.get("value")
        if value in (None, ""):
            config.pop(key, None)
            run_on_bot(bot.save_state())
            return jsonify(ok=True)
        channel = guild.get_channel(int(value)) if str(value).isdigit() else None
        if not isinstance(channel, expected):
            return jsonify(error="頻道類型不符"), 400
        config[key] = channel.id
        run_on_bot(bot.save_state())
        if key == "ticket_panel":
            cog = bot.get_cog("TicketCog")
            if cog:
                try:
                    run_on_bot(cog.send_panel(channel, force=True))
                except Exception as e:
                    return jsonify(ok=True, warning=f"已儲存，但發送開票訊息失敗: {e}")
        return jsonify(ok=True)

    @app.post("/api/guilds/<guild_id>/staff")
    @guarded
    def set_staff(guild_id):
        guild = bot.get_guild(int(guild_id)) if guild_id.isdigit() else None
        if not guild:
            return jsonify(error="找不到伺服器"), 404
        data = request.get_json(silent=True) or {}
        raw_id = str(data.get("role_id", ""))
        role = guild.get_role(int(raw_id)) if raw_id.isdigit() else None
        if not role:
            return jsonify(error="找不到身分組"), 404
        staff = bot.config_db.setdefault(guild.id, {}).setdefault("ticket_staff", [])
        if data.get("enabled"):
            if role.id not in staff:
                staff.append(role.id)
        elif role.id in staff:
            staff.remove(role.id)
        run_on_bot(bot.save_state())
        return jsonify(ok=True)

    @app.post("/api/guilds/<guild_id>/voice/leave")
    @guarded
    def voice_leave(guild_id):
        guild = bot.get_guild(int(guild_id)) if guild_id.isdigit() else None
        if not guild or not guild.voice_client:
            return jsonify(error="機器人不在語音頻道中"), 404

        async def leave():
            music = bot.get_cog("Music")
            if music:
                await music._stop_playback(guild)
            await guild.voice_client.disconnect()

        run_on_bot(leave())
        return jsonify(ok=True)

    @app.get("/api/guilds/<guild_id>/welcome")
    @guarded
    def get_welcome_settings(guild_id):
        guild = bot.get_guild(int(guild_id)) if guild_id.isdigit() else None
        if not guild:
            return jsonify(error="找不到伺服器"), 404
        welcome = dict(DEFAULT_WELCOME)
        welcome.update(bot.welcome_db.get(guild.id, {}))
        for key in ("member_role", "bot_role"):
            welcome[key] = str(welcome[key]) if welcome.get(key) else None
        channel = bot.config_db.get(guild.id, {}).get("welcome")
        saved = bot.roles_db.get(guild.id, {})
        selfrole = {
            "channel": str(saved["channel"]) if saved.get("channel") else None,
            "type": saved.get("type", "button"),
            "title": saved.get("title", "身分組領取"),
            "content": saved.get("content", "點選下方的按鈕來領取身分組"),
            "roles": [str(r["id"]) for r in saved.get("roles", [])],
        }
        return jsonify(
            welcome=welcome,
            channel=str(channel) if channel else None,
            selfrole=selfrole,
            text=[{"id": str(c.id), "name": c.name} for c in guild.text_channels],
            roles=[{"id": str(r.id), "name": r.name} for r in reversed(guild.roles) if not r.is_default() and not r.managed],
        )

    @app.post("/api/guilds/<guild_id>/welcome")
    @guarded
    def save_welcome(guild_id):
        guild = bot.get_guild(int(guild_id)) if guild_id.isdigit() else None
        if not guild:
            return jsonify(error="找不到伺服器"), 404
        data = request.get_json(silent=True) or {}

        def role_value(key):
            raw = str(data.get(key) or "")
            role = guild.get_role(int(raw)) if raw.isdigit() else None
            return role.id if role else None

        bot.welcome_db[guild.id] = {
            "enabled": bool(data.get("enabled")),
            "title": str(data.get("title", ""))[:256],
            "body": str(data.get("body", ""))[:4000],
            "thumbnail": str(data.get("thumbnail", ""))[:500],
            "image": str(data.get("image", ""))[:500],
            "member_role": role_value("member_role"),
            "bot_role": role_value("bot_role"),
        }
        config = bot.config_db.setdefault(guild.id, {})
        raw_channel = str(data.get("channel") or "")
        if raw_channel:
            channel = guild.get_channel(int(raw_channel)) if raw_channel.isdigit() else None
            if not isinstance(channel, discord.TextChannel):
                return jsonify(error="歡迎頻道必須是文字頻道"), 400
            config["welcome"] = channel.id
        else:
            config.pop("welcome", None)
        run_on_bot(bot.save_state())
        return jsonify(ok=True)

    @app.post("/api/guilds/<guild_id>/selfrole")
    @guarded
    def save_selfrole(guild_id):
        guild = bot.get_guild(int(guild_id)) if guild_id.isdigit() else None
        if not guild:
            return jsonify(error="找不到伺服器"), 404
        data = request.get_json(silent=True) or {}
        raw_channel = str(data.get("channel") or "")
        channel = guild.get_channel(int(raw_channel)) if raw_channel.isdigit() else None
        if not isinstance(channel, discord.TextChannel):
            return jsonify(error="請選擇發送頻道"), 400
        roles = []
        for raw in list(data.get("roles", []))[:MAX_ROLES]:
            role = guild.get_role(int(raw)) if str(raw).isdigit() else None
            if role and not role.is_default() and not role.managed:
                roles.append({"id": role.id, "label": role.name[:80]})
        if not roles:
            return jsonify(error="請至少選擇一個身分組"), 400
        old = bot.roles_db.get(guild.id, {})
        config = {
            "channel": channel.id,
            "type": "select" if data.get("type") == "select" else "button",
            "title": str(data.get("title", ""))[:256],
            "content": str(data.get("content", ""))[:4000],
            "roles": roles,
            "message_id": old.get("message_id") if old.get("channel") == channel.id else None,
        }
        try:
            run_on_bot(publish_selfrole(bot, guild, config))
        except Exception as e:
            return jsonify(error=f"發送失敗: {e}"), 500
        bot.roles_db[guild.id] = config
        run_on_bot(bot.save_state())
        return jsonify(ok=True)
