import discord
from discord import app_commands
from discord.ext import commands
import psutil

class Tools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_allowed(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id in self.bot.allowed_ids:
            return True
        if interaction.guild and interaction.user.id == interaction.guild.owner_id:
            return True
        return False

    @app_commands.command(name="test", description="檢視機器人系統數據與效能")
    async def test_bot(self, interaction: discord.Interaction):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)
        
        cpu_usage = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        latency = round(self.bot.latency * 1000, 2)
        
        embed = discord.Embed(title="📊 系統效能數據", color=0x2b2d31)
        embed.add_field(name="🧠 記憶體佔用", value=f"{memory.percent}% ({memory.used // (1024**2)} MB / {memory.total // (1024**2)} MB)", inline=False)
        embed.add_field(name="💻 CPU 使用率", value=f"{cpu_usage}%", inline=False)
        embed.add_field(name="⚡ 網路延遲 (Ping)", value=f"{latency} ms", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="whois", description="查看指定成員的詳細資料與頭像")
    @app_commands.describe(member="目標成員")
    async def whois(self, interaction: discord.Interaction, member: discord.Member = None):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)
        
        target = member or interaction.user
        roles = [role.mention for role in target.roles if role != interaction.guild.default_role]
        roles_str = ", ".join(roles) if roles else "無"
        
        embed = discord.Embed(title=f"👤 成員詳細資料 - {target.name}", color=target.color if target.color.value else 0x2b2d31)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="🆔 用戶 ID", value=target.id, inline=True)
        embed.add_field(name="🏷️ 暱稱", value=target.nick or "無", inline=True)
        embed.add_field(name="📅 帳號創建時間", value=target.created_at.strftime("%Y-%m-%d %H:%M"), inline=False)
        embed.add_field(name="📥 加入伺服器時間", value=target.joined_at.strftime("%Y-%m-%d %H:%M") if target.joined_at else "未知", inline=False)
        embed.add_field(name="🎭 身分組", value=roles_str[:1024], inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Tools(bot))
