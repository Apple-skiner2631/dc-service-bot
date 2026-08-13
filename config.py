import asyncio
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select, UserSelect

TRIGGER_CHANNEL_ID = 1530974075902759083
CATEGORY_ID = 1459692616076624087
STAFF_ROLE_ID = 1459696673239470338


class VoiceChannelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):

        pass

async def setup(bot):
    await bot.add_cog(VoiceChannelCog(bot))
