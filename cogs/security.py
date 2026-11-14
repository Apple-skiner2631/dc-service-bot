import logging

import discord
from discord.ext import commands


class Security(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        config = getattr(self.bot, "config_db", {}).get(guild_id, {})

        trap_channel_id = config.get("trap")
        if not trap_channel_id or message.channel.id != trap_channel_id:
            return

        if message.author.id in self.bot.allowed_ids:
            return
        if message.author.id == message.guild.owner_id:
            return

        if message.author.id in getattr(self.bot, "whitelist_db", {}).get(guild_id, []):
            return

        if not getattr(self.bot, "autoban_db", {}).get(guild_id, False):
            return

        try:
            await message.delete()
        except discord.HTTPException as e:
            logging.warning(f"陷阱頻道刪除訊息失敗: {e}")

        banned = False
        try:
            await message.author.ban(reason="觸發安全陷阱頻道自動封鎖")
            banned = True
        except discord.HTTPException as e:
            logging.warning(f"陷阱頻道封鎖失敗 {message.author}: {e}")

        punish_channel_id = config.get("punish")
        if punish_channel_id:
            ch = message.guild.get_channel(punish_channel_id)
            if ch:
                result = "已執行自動永久封鎖" if banned else "封鎖失敗，請檢查機器人權限與身分組順序"
                try:
                    await ch.send(
                        f"# 🚨 **安全防護通告**\n"
                        f"> 偵測到用戶 {message.author.mention} ({message.author.name}) 觸發陷阱頻道\n"
                        f"> {result}"
                    )
                except discord.HTTPException as e:
                    logging.warning(f"通告頻道發送失敗: {e}")


async def setup(bot):
    await bot.add_cog(Security(bot))
