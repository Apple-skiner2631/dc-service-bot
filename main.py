import os
import asyncio
import discord
from discord.ext import commands
from aiohttp import web

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

async def handle_ping(request):
    return web.Response(text="Bot is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"✅ Web Server 已啟動，監聽 Port: {port}")

@bot.event
async def on_ready():
    print(f"🎉 成功登入 Discord！機器人名稱：{bot.user}")

async def main():
    async with bot:

        await start_web_server()

        token = os.getenv("DISCORD_TOKEN")
        if not token:
            print("❌ [錯誤] 抓不到 DISCORD_TOKEN！請檢查 Render 的 Environment 變數名稱！")
            return
        
        token = token.strip()
        print(f"🔑 已找到 Token (前5碼: {token[:5]}...)，正在嘗試連線至 Discord...")
        
        try:
            await bot.start(token)
        except discord.errors.LoginFailure:
            print("❌ [錯誤] Discord Token 無效或已過期！請重新生成 Token。")
        except discord.errors.PrivilegedIntentsRequired:
            print("❌ [錯誤] 請至 Discord Developer Portal 開啟 Privileged Gateway Intents (Server Members Intent)！")
        except Exception as e:
            print(f"❌ [未知錯誤] 連線失敗：{e}")

if __name__ == "__main__":
    asyncio.run(main())
