import discord
from discord.ext import commands

class Security(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Cogs if False else discord.Message):
        if message.author.bot or not message.guild:
            return

        admin_cog = self.bot.get_cog("Admin")
        if not admin_cog:
            return

        guild_id = message.guild.id
        trap_channel_id = admin_cog.config_db.get(guild_id, {}).get("trap")
        if not trap_channel_id or message.channel.id != trap_channel_id:
            return

        if message.author.id in self.bot.allowed_ids:
            return
        if message.author.id == message.guild.owner_id:
            return

        whitelist = admin_cog.whitelist_db.get(guild_id, [])
        if message.author.id in whitelist:
            return

        autoban_enabled = admin_cog.autoban_db.get(guild_id, False)
        if not autoban_enabled:
            return

        try:
            await message.delete()
        except:
            pass

        try:
            await message.author.ban(reason="觸發安全陷阱頻道自動封鎖")
        except:
            pass

        punish_channel_id = admin_cog.config_db.get(guild_id, {}).get("punish")
        if punish_channel_id:
            ch = message.guild.get_channel(punish_channel_id)
            if ch:
                await ch.send(f"# 🚨 **安全防護通告**\n> 偵測到用戶 {message.author.mention} ({message.author.name}) 觸發陷阱頻道\n> 已執行自動永久封鎖")

async def setup(bot):
    await bot.add_cog(Security(bot))
