import asyncio
import io
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import ui
from discord.ext import commands


TICKET_CHANNEL_ID = 1466986768652963983
PENDING_CAT_ID = 1490338802261299312
RESOLVED_CAT_ID = 1490339576689201212
STAFF_ROLE_IDS = [1459696673239470338, 1459700251295223994]

TAIPEI_TZ = timezone(timedelta(hours=8))
TICKET_PREFIXES = ("ticket-", "report-", "ask-", "suggest-")
OWNER_TOPIC_PREFIX = "ticket_owner:"


def is_ticket_channel(channel) -> bool:
    return any(channel.name.startswith(prefix) for prefix in TICKET_PREFIXES)


def get_opener_id(channel):
    topic = getattr(channel, "topic", None) or ""
    if topic.startswith(OWNER_TOPIC_PREFIX):
        try:
            return int(topic[len(OWNER_TOPIC_PREFIX):].strip())
        except ValueError:
            return None
    return None


def is_staff(member: discord.Member, allowed_ids) -> bool:
    if member.id in allowed_ids:
        return True
    if member.guild_permissions.manage_channels:
        return True
    return any(role.id in STAFF_ROLE_IDS for role in member.roles)


def can_manage(interaction: discord.Interaction) -> bool:
    return is_staff(interaction.user, interaction.client.allowed_ids)


def is_opener_or_staff(interaction: discord.Interaction) -> bool:
    return can_manage(interaction) or get_opener_id(interaction.channel) == interaction.user.id


def build_overwrites(guild: discord.Guild, user: discord.Member) -> dict:
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }
    for role_id in STAFF_ROLE_IDS:
        staff_role = guild.get_role(role_id)
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    return overwrites


async def create_ticket_channel(guild: discord.Guild, user: discord.Member, channel_name: str) -> discord.TextChannel:
    category = guild.get_channel(PENDING_CAT_ID)
    return await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=build_overwrites(guild, user),
        topic=f"{OWNER_TOPIC_PREFIX}{user.id}",
    )


def find_existing_ticket(guild: discord.Guild, channel_name: str):
    for cat_id in (PENDING_CAT_ID, RESOLVED_CAT_ID):
        category = guild.get_channel(cat_id)
        if category:
            for ch in category.text_channels:
                if ch.name.lower() == channel_name:
                    return ch
    return None


class BaseTicketModal(ui.Modal):
    def __init__(self, title_text: str, ticket_type: str, field1_label: str, field2_label: str, field3_label: str):
        super().__init__(title=title_text)
        self.ticket_type = ticket_type

        self.field1 = ui.TextInput(label=field1_label, placeholder="請輸入...", max_length=100)
        self.field2 = ui.TextInput(label=field2_label, style=discord.TextStyle.paragraph, placeholder="請詳細說明...", max_length=1000)
        self.field3 = ui.TextInput(label=field3_label, placeholder="可提供圖片或雲端連結，限10KB以內", required=False, max_length=500)

        self.add_item(self.field1)
        self.add_item(self.field2)
        self.add_item(self.field3)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        channel_name = f"{self.ticket_type}-{interaction.user.name.lower()}"

        existing = find_existing_ticket(guild, channel_name)
        if existing:
            return await interaction.followup.send(f"**⚠️ 您已經建立過此類別的工單 ({existing.mention})，無法重複建立！**", ephemeral=True)

        try:
            ticket_channel = await create_ticket_channel(guild, interaction.user, channel_name)
        except discord.HTTPException as e:
            logging.warning(f"建立工單頻道失敗: {e}")
            return await interaction.followup.send("❌ 建立工單失敗，請聯絡管理人員（可能是分類頻道已滿或機器人權限不足）。", ephemeral=True)

        current_time = datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M:%S")

        embed = discord.Embed(title=" ✅ 工單已建立\n 請耐心等待管理人員受理!", color=discord.Color.blue())
        embed.description = (
            f"**時間:** {current_time}\n"
            f"**使用者:** {interaction.user.mention}\n"
            f"**工單類型:** {self.ticket_type}\n"
            f"**{self.field1.label}:** {self.field1.value}\n"
            f"**{self.field2.label}:** {self.field2.value}\n"
            f"**{self.field3.label}:** {self.field3.value if self.field3.value else '無'}"
        )

        await ticket_channel.send(embed=embed, view=TicketControlView())
        await interaction.followup.send(f"**工單已成功建立：{ticket_channel.mention}**", ephemeral=True)


class TicketSelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="請選擇服務類別...", value="none", description="點擊下方選項以選擇工單類型", emoji="📌", default=True),
            discord.SelectOption(label="申訴檢舉", emoji="⚖️", value="申訴檢舉", description="回報玩家違規或對處分提出申訴"),
            discord.SelectOption(label="問題詢問", emoji="❓", value="問題詢問", description="尋求遊戲、伺服器或系統協助"),
            discord.SelectOption(label="意見回報", emoji="💡", value="意見回報", description="提供建議或反饋改善方案"),
        ]
        super().__init__(placeholder="請選擇您要進行的服務類別...", min_values=1, max_values=1, options=options, custom_id="ticket_select_menu")

    async def callback(self, interaction: discord.Interaction):
        selected_type = self.values[0]

        if selected_type == "none":
            await interaction.response.send_message("請選擇有效的服務類別！", ephemeral=True)
            return

        type_prefix_map = {
            "申訴檢舉": "report",
            "問題詢問": "ask",
            "意見回報": "suggest",
        }
        prefix = type_prefix_map.get(selected_type)
        if not prefix:
            await interaction.response.send_message("請選擇有效的服務類別！", ephemeral=True)
            return

        target_channel_name = f"{prefix}-{interaction.user.name.lower()}"
        existing = find_existing_ticket(interaction.guild, target_channel_name)
        if existing:
            await interaction.response.send_message(f"**⚠️ 您已經建立過「{selected_type}」類別的工單 ({existing.mention})，無法重複建立！**", ephemeral=True)
            return

        if selected_type == "申訴檢舉":
            modal = BaseTicketModal("⚖️ 申訴檢舉單", "report", "被檢舉人 / 事件名稱", "詳細說明與經過", "證據連結 (選填)")
        elif selected_type == "問題詢問":
            modal = BaseTicketModal("❓ 問題詢問單", "ask", "問題主題", "詳細問題描述", "相關截圖 / 連結 (選填)")
        else:
            modal = BaseTicketModal("💡 意見回報單", "suggest", "建議主題", "詳細建議內容 / 改善方案", "參考資料 (選填)")

        await interaction.response.send_modal(modal)

        try:
            await interaction.message.edit(view=TicketLaunchView())
        except discord.HTTPException:
            pass


class TicketLaunchView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


class TicketControlView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="❌ 關閉工單", style=discord.ButtonStyle.blurple, custom_id="close_ticket")
    async def close(self, interaction: discord.Interaction, button: ui.Button):
        if not is_opener_or_staff(interaction):
            return await interaction.response.send_message("❌ 只有開單者或管理人員才能關閉工單。", ephemeral=True)

        await interaction.response.defer()
        category = interaction.guild.get_channel(RESOLVED_CAT_ID)
        try:
            await interaction.channel.edit(category=category)
        except discord.HTTPException as e:
            return await interaction.followup.send(f"❌ 移動工單失敗: {e}", ephemeral=True)

        embed = discord.Embed(title="**📨 工單管理選項**", description="**請選擇後續處理方式：**", color=discord.Color.orange())
        await interaction.followup.send(embed=embed, view=TicketPostCloseView())


class TicketPostCloseView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🔄 復原工單", style=discord.ButtonStyle.secondary, custom_id="opt_reopen")
    async def opt_reopen(self, interaction: discord.Interaction, button: ui.Button):
        if not can_manage(interaction):
            return await interaction.response.send_message("❌ 只有管理人員才能復原工單。", ephemeral=True)

        await interaction.response.defer()
        category = interaction.guild.get_channel(PENDING_CAT_ID)
        try:
            await interaction.channel.edit(category=category)
        except discord.HTTPException as e:
            return await interaction.followup.send(f"❌ 復原失敗: {e}", ephemeral=True)
        await interaction.followup.send("**🔄 工單已成功復原並移至「待處理」區域！**")

    @ui.button(label="⛔ 刪除頻道", style=discord.ButtonStyle.danger, custom_id="opt_delete")
    async def opt_delete(self, interaction: discord.Interaction, button: ui.Button):
        if not can_manage(interaction):
            return await interaction.response.send_message("❌ 只有管理人員才能刪除頻道。", ephemeral=True)

        await interaction.response.send_message("**⚠ 頻道即將在 5 秒後刪除...**")
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except discord.HTTPException as e:
            logging.warning(f"刪除工單頻道失敗: {e}")

    @ui.button(label="📥 匯出對話檔案", style=discord.ButtonStyle.success, custom_id="opt_export")
    async def opt_export(self, interaction: discord.Interaction, button: ui.Button):
        if not is_opener_or_staff(interaction):
            return await interaction.response.send_message("❌ 只有開單者或管理人員才能匯出對話。", ephemeral=True)

        await interaction.response.defer()
        lines = []
        async for message in interaction.channel.history(limit=None, oldest_first=True):
            stamp = message.created_at.astimezone(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M:%S")
            content = message.content
            if message.attachments:
                content += " " + " ".join(a.url for a in message.attachments)
            if message.embeds and not content:
                content = "[嵌入訊息]"
            lines.append(f"[{stamp}] {message.author}: {content}")

        file_buffer = io.BytesIO("\n".join(lines).encode("utf-8"))
        file_name = f"transcript-{interaction.channel.name}.txt"
        await interaction.followup.send(file=discord.File(fp=file_buffer, filename=file_name))


class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_sent = False

    async def cog_load(self):
        self.bot.add_view(TicketLaunchView())
        self.bot.add_view(TicketControlView())
        self.bot.add_view(TicketPostCloseView())

    @commands.Cog.listener()
    async def on_ready(self):
        if self.panel_sent:
            return
        self.panel_sent = True

        channel = self.bot.get_channel(TICKET_CHANNEL_ID)
        if not channel:
            logging.warning("找不到工單面板頻道，請確認 TICKET_CHANNEL_ID")
            return

        try:
            await channel.purge(limit=50, check=lambda m: m.author.id == self.bot.user.id)
        except discord.HTTPException as e:
            logging.warning(f"清理舊工單面板失敗: {e}")

        embed = discord.Embed(
            title="📨 票務系統 | Ticket System",
            description="""歡迎使用支援服務，請點擊下方選單選擇您要開啟的服務類別。

**⚠️ 開票須知：**
1. 開啟工單前，請務必先詳閱伺服器規範。
2. 進入頻道後請詳細說明事由，**請勿惡意標記 (@) 管理團隊**。
3. 每位玩家在每個類別最多只能開啟 1 張工單 (最多 3 張)。
4. 請勿無故濫用票務系統，非必要請勿隨意開票。

*管理團隊將會盡快為您處理，感謝您的配合！*""",
            color=discord.Color.green()
        )
        await channel.send(embed=embed, view=TicketLaunchView())

    @commands.command(name="new")
    @commands.guild_only()
    async def cmd_new(self, ctx: commands.Context):
        channel_name = f"ticket-{ctx.author.name.lower()}"

        existing = find_existing_ticket(ctx.guild, channel_name)
        if existing:
            return await ctx.send(f"**⚠️ 您已經有一張工單：{existing.mention}**", delete_after=10)

        try:
            ticket_channel = await create_ticket_channel(ctx.guild, ctx.author, channel_name)
        except discord.HTTPException as e:
            logging.warning(f"建立工單頻道失敗: {e}")
            return await ctx.send("❌ 建立工單失敗，請聯絡管理人員。", delete_after=10)

        embed = discord.Embed(
            title="**工單已建立!**",
            description=f"📄 歡迎使用工單系統。\n管理團隊將迅速為您服務! \n> **👥使用者:** {ctx.author.mention}",
            color=discord.Color.blue()
        )
        await ticket_channel.send(embed=embed, view=TicketControlView())
        await ctx.send(f"**已為您開啟工單頻道：{ticket_channel.mention}**")

    @commands.command(name="user")
    @commands.guild_only()
    async def cmd_user(self, ctx: commands.Context, member: discord.Member):
        if not is_staff(ctx.author, self.bot.allowed_ids):
            return await ctx.send("**❌ 只有管理人員可以使用此指令。**", delete_after=5)
        if not is_ticket_channel(ctx.channel):
            return await ctx.send("**⚠ 此指令只能在工單頻道內使用!**", delete_after=5)

        await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
        await ctx.send(f"**✅ 已成功將 {member.mention} 邀請至本工單頻道。**")

    @commands.command(name="close")
    @commands.guild_only()
    async def cmd_close(self, ctx: commands.Context):
        if not is_ticket_channel(ctx.channel):
            return await ctx.send("⚠ 此指令只能在工單頻道內使用。", delete_after=5)

        allowed = is_staff(ctx.author, self.bot.allowed_ids) or get_opener_id(ctx.channel) == ctx.author.id
        if not allowed:
            return await ctx.send("❌ 只有開單者或管理人員才能關閉工單。", delete_after=5)

        embed = discord.Embed(title="**📨 工單管理選項**", description="**請選擇後續處理方式：**", color=discord.Color.orange())
        await ctx.send(embed=embed, view=TicketPostCloseView())


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketCog(bot))
