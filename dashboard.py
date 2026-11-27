import asyncio
import hashlib
import hmac
import os
import time
from functools import wraps

import discord
import psutil
from flask import jsonify, request, session

STARTED_AT = time.time()
PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "")
failures = {}


def register_dashboard(app, bot):
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
        for guild in bot.guilds:
            config = bot.config_db.get(guild.id, {})
            guilds.append({
                "id": str(guild.id),
                "name": guild.name,
                "members": guild.member_count,
                "autoban": bool(bot.autoban_db.get(guild.id, False)),
                "room": channel_name(guild, config, "room"),
                "trap": channel_name(guild, config, "trap"),
                "punish": channel_name(guild, config, "punish"),
                "ticket": channel_name(guild, config, "ticket_panel"),
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
