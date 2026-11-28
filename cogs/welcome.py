import logging

import discord
from discord import ui
from discord.ext import commands

MAX_ROLES = 15

DEFAULT_WELCOME = {
    "enabled": True,
    "title": "歡迎 %username% 加入 %guild%！",
    "body": "# 嗨！%user%\n\n歡迎來到 **%guild%**，你是第 **%count%** 位成員。\n請先閱讀規則，然後開始聊天吧！",
    "thumbnail": "%avatar%",
    "image": "",
    "member_role": None,
    "bot_role": None,
}


def render(text: str, member: discord.Member) -> str:
    return (
        text.replace("%user%", member.mention)
        .replace("%username%", member.display_name)
        .replace("%guild%", member.guild.name)
        .replace("%count%", str(member.guild.member_count))
        .replace("%avatar%", member.display_avatar.url)
    )


def get_welcome(bot, guild_id: int) -> dict:
    data = dict(DEFAULT_WELCOME)
    data.update(bot.welcome_db.get(guild_id, {}))
    return data


def build_welcome_embed(member: discord.Member, data: dict) -> discord.Embed:
    embed = discord.Embed(
        title=render(data["title"], member)[:256] or None,
        description=render(data["body"], member)[:4000] or None,
        color=discord.Color.blurple(),
    )
    thumbnail = render(data["thumbnail"], member).strip()
    if thumbnail.startswith("http"):
        embed.set_thumbnail(url=thumbnail)
    image = render(data["image"], member).strip()
    if image.startswith("http"):
        embed.set_image(url=image)
    return embed


class RoleButton(ui.Button):
    def __init__(self, guild_id: int, role: dict):
        super().__init__(label=role["label"], style=discord.ButtonStyle.secondary, custom_id=f"selfrole:{guild_id}:{role['id']}")
        self.role_id = role["id"]

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(self.role_id)
        if not role:
            return await interaction.response.send_message("❌ 找不到這個身分組。", ephemeral=True)
        try:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                message = f"已移除身分組 {role.mention}"
            else:
                await interaction.user.add_roles(role)
                message = f"已取得身分組 {role.mention}"
        except discord.HTTPException:
            message = "❌ 機器人權限不足，或該身分組的位置高於機器人。"
        await interaction.response.send_message(message, ephemeral=True)


class RoleSelect(ui.Select):
    def __init__(self, guild_id: int, roles: list):
        options = [discord.SelectOption(label=r["label"][:100], value=str(r["id"])) for r in roles]
        super().__init__(
            placeholder="選擇你要的身分組...",
            min_values=0,
            max_values=len(options),
            options=options,
            custom_id=f"selfrole_select:{guild_id}",
        )
        self.role_ids = [r["id"] for r in roles]

    async def callback(self, interaction: discord.Interaction):
        chosen = {int(v) for v in self.values}
        member = interaction.user
        to_add = [r for r in (interaction.guild.get_role(i) for i in chosen) if r and r not in member.roles]
        to_remove = [r for r in member.roles if r.id in self.role_ids and r.id not in chosen]
        try:
            if to_add:
                await member.add_roles(*to_add)
            if to_remove:
                await member.remove_roles(*to_remove)
            message = "✅ 身分組已更新。"
        except discord.HTTPException:
            message = "❌ 機器人權限不足，或身分組的位置高於機器人。"
        await interaction.response.send_message(message, ephemeral=True)


def build_selfrole_view(guild_id: int, config: dict) -> ui.View:
    view = ui.View(timeout=None)
    roles = config.get("roles", [])[:MAX_ROLES]
    if config.get("type") == "select":
        view.add_item(RoleSelect(guild_id, roles))
    else:
        for role in roles:
            view.add_item(RoleButton(guild_id, role))
    return view


async def publish_selfrole(bot, guild: discord.Guild, config: dict) -> discord.Message:
    channel = guild.get_channel(config["channel"])
    if not isinstance(channel, discord.TextChannel):
        raise ValueError("找不到文字頻道")
    embed = discord.Embed(
        title=config.get("title") or None,
        description=config.get("content") or "點選下方來領取身分組",
        color=discord.Color.blurple(),
    )
    view = build_selfrole_view(guild.id, config)
    bot.add_view(view)

    message = None
    if config.get("message_id"):
        try:
            message = await channel.fetch_message(config["message_id"])
            await message.edit(embed=embed, view=view)
        except discord.NotFound:
            message = None
    if message is None:
        message = await channel.send(embed=embed, view=view)
    config["message_id"] = message.id
    return message


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        for name in ("welcome_db", "roles_db"):
            if not hasattr(bot, name):
                setattr(bot, name, {})

    async def cog_load(self):
        for guild_id, config in self.bot.roles_db.items():
            if config.get("roles"):
                self.bot.add_view(build_selfrole_view(guild_id, config))

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        data = get_welcome(self.bot, member.guild.id)

        role_id = data["bot_role"] if member.bot else data["member_role"]
        role = member.guild.get_role(role_id) if role_id else None
        if role:
            try:
                await member.add_roles(role, reason="自動分發身分組")
            except discord.HTTPException as e:
                logging.warning(f"自動分發身分組失敗 {member}: {e}")

        channel_id = self.bot.config_db.get(member.guild.id, {}).get("welcome")
        if member.bot or not data["enabled"] or not channel_id:
            return
        channel = member.guild.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            try:
                await channel.send(
                    embed=build_welcome_embed(member, data),
                    allowed_mentions=discord.AllowedMentions(users=[member]),
                )
            except discord.HTTPException as e:
                logging.warning(f"發送歡迎訊息失敗: {e}")


async def setup(bot):
    await bot.add_cog(Welcome(bot))
