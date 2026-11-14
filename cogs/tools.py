import discord
from discord import app_commands
from discord.ext import commands
import psutil


class Tools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.process = psutil.Process()
        self.process.cpu_percent(interval=None)

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

    @app_commands.command(name="test", description="檢視機器人系統數據與效能")
    async def test_bot(self, interaction: discord.Interaction):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)

        proc_mem = self.process.memory_info().rss // (1024 ** 2)
        proc_cpu = self.process.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        latency = self.bot.latency
        latency_text = f"{round(latency * 1000, 2)} ms" if latency == latency and latency != float("inf") else "未知"

        embed = discord.Embed(title="📊 系統效能數據", color=0x2b2d31)
        embed.add_field(name="🤖 機器人記憶體", value=f"{proc_mem} MB", inline=True)
        embed.add_field(name="🤖 機器人 CPU", value=f"{proc_cpu}%", inline=True)
        embed.add_field(name="⚡ 網路延遲 (Ping)", value=latency_text, inline=True)
        embed.add_field(
            name="🖥️ 主機記憶體",
            value=f"{memory.percent}% ({memory.used // (1024 ** 2)} MB / {memory.total // (1024 ** 2)} MB)",
            inline=False,
        )
        embed.add_field(name="🌐 伺服器數", value=str(len(self.bot.guilds)), inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="whois", description="查看指定成員的詳細資料與頭像")
    @app_commands.describe(member="目標成員")
    async def whois(self, interaction: discord.Interaction, member: discord.Member = None):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)

        target = member or interaction.user

        role_mentions = []
        length = 0
        for role in reversed(target.roles):
            if role.is_default():
                continue
            if length + len(role.mention) + 2 > 1000:
                role_mentions.append("…")
                break
            role_mentions.append(role.mention)
            length += len(role.mention) + 2
        roles_str = ", ".join(role_mentions) if role_mentions else "無"

        color = target.color if target.color.value else discord.Color(0x2b2d31)
        embed = discord.Embed(title=f"👤 成員詳細資料 - {target.name}", color=color)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="🆔 用戶 ID", value=str(target.id), inline=True)
        embed.add_field(name="🏷️ 暱稱", value=target.nick or "無", inline=True)
        embed.add_field(name="📅 帳號創建時間", value=discord.utils.format_dt(target.created_at, "F"), inline=False)
        embed.add_field(
            name="📥 加入伺服器時間",
            value=discord.utils.format_dt(target.joined_at, "F") if target.joined_at else "未知",
            inline=False,
        )
        embed.add_field(name="🎭 身分組", value=roles_str, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Tools(bot))
