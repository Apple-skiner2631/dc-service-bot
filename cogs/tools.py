import discord
from discord import app_commands
from discord.ext import commands
import psutil

class Utility(commands.Cog):
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

    @app_commands.command(name="avatar", description="查看指定成員的頭像")
    @app_commands.describe(member="目標成員")
    async def get_avatar(self, interaction: discord.Interaction, member: discord.Member = None):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)
        
        target = member or interaction.user
        embed = discord.Embed(title=f"{target.name} 的頭像", color=0x2b2d31)
        embed.set_image(url=target.display_avatar.url)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Utility(bot))
