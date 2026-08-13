import os
import discord
from discord.ext import commands
from discord import ui
from datetime import datetime

TOKEN = os.getenv("DISCORD_TOKEN")
TICKET_CHANNEL_ID = 1466986768652963983
PENDING_CAT_ID = 1490338802261299312
RESOLVED_CAT_ID = 1490339576689201212

STAFF_ROLE_IDS = [1459696673239470338, 1459700251295223994]

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="$", intents=intents)

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
        category = guild.get_channel(PENDING_CAT_ID)
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        for role_id in STAFF_ROLE_IDS:
            staff_role = guild.get_role(role_id)
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        channel_name = f"{self.ticket_type}-{interaction.user.name}"
        ticket_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        embed = discord.Embed(title=" ✅ 工單已建立\n 請耐心等待管理人員受理!", color=discord.Color.blue())
        embed.description = f"**時間:** {current_time}\n**使用者:** {interaction.user.mention}\n**工單類型:** {self.ticket_type}\n**{self.field1.label}:** {self.field1.value}\n**{self.field2.label}:** {self.field2.value}\n**{self.field3.label}:** {self.field3.value if self.field3.value else '無'}"
        
        view = TicketControlView()
        await ticket_channel.send(embed=embed, view=view)
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

        guild = interaction.guild
        user_name = interaction.user.name.lower()

        type_prefix_map = {
            "申訴檢舉": "report",
            "問題詢問": "ask",
            "意見回報": "suggest"
        }
        prefix = type_prefix_map.get(selected_type, "ticket")
        target_channel_name = f"{prefix}-{user_name}"

        pending_cat = guild.get_channel(PENDING_CAT_ID)
        resolved_cat = guild.get_channel(RESOLVED_CAT_ID)
        
        existing_channels = []
        if pending_cat:
            existing_channels.extend(pending_cat.text_channels)
        if resolved_cat:
            existing_channels.extend(resolved_cat.text_channels)

        for ch in existing_channels:
            if ch.name.lower() == target_channel_name:
                await interaction.response.send_message(f"**⚠️ 您已經建立過「{selected_type}」類別的工單 ({ch.mention})，無法重複建立！**", ephemeral=True)
                return

        if selected_type == "申訴檢舉":
            modal = BaseTicketModal("⚖️ 申訴檢舉單", "report", "被檢舉人 / 事件名稱", "詳細說明與經過", "證據連結 (選填)")
        elif selected_type == "問題詢問":
            modal = BaseTicketModal("❓ 問題詢問單", "ask", "問題主題", "詳細問題描述", "相關截圖 / 連結 (選填)")
        elif selected_type == "意見回報":
            modal = BaseTicketModal("💡 意見回報單", "suggest", "建議主題", "詳細建議內容 / 改善方案", "參考資料 (選填)")

        await interaction.response.send_modal(modal)

class TicketLaunchView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

class TicketControlView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="❌ 關閉工單", style=discord.ButtonStyle.blurple, custom_id="close_ticket")
    async def close(self, interaction: discord.Interaction, button: ui.Button):
        category = interaction.guild.get_channel(RESOLVED_CAT_ID)
        await interaction.channel.edit(category=category)
        
        embed = discord.Embed(title="**📨 工單管理選項**", description="**請選擇後續處理方式：**", color=discord.Color.orange())
        view = TicketPostCloseView()
        await interaction.response.send_message(embed=embed, view=view)

class TicketPostCloseView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🔄 復原工單", style=discord.ButtonStyle.secondary, custom_id="opt_reopen")
    async def opt_reopen(self, interaction: discord.Interaction, button: ui.Button):
        category = interaction.guild.get_channel(PENDING_CAT_ID)
        await interaction.channel.edit(category=category)
        await interaction.response.send_message("**🔄 工單已成功復原並移至「待處理」區域！**")

    @ui.button(label="⛔ 刪除頻道", style=discord.ButtonStyle.danger, custom_id="opt_delete")
    async def opt_delete(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("**⚠ 頻道即將在 5 秒後刪除...**")
        await interaction.channel.delete()

    @ui.button(label="📥 匯出對話檔案", style=discord.ButtonStyle.success, custom_id="opt_export")
    async def opt_export(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        log_text = ""
        async for message in interaction.channel.history(limit=None, oldest_first=True):
            log_text += f"[{message.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {message.author}: {message.content}\n"
        
        file_path = f"transcript-{interaction.channel.name}.txt"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(log_text)
        
        await interaction.followup.send(file=discord.File(file_path))
        os.remove(file_path)

@bot.event
async def on_ready():
    bot.add_view(TicketLaunchView())
    bot.add_view(TicketControlView())
    bot.add_view(TicketPostCloseView())
    channel = bot.get_channel(TICKET_CHANNEL_ID)
    if channel:
        await channel.purge(limit=10)
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

@bot.command(name="new")
async def cmd_new(ctx):
    guild = ctx.guild
    category = guild.get_channel(PENDING_CAT_ID)
    
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    
    for role_id in STAFF_ROLE_IDS:
        staff_role = guild.get_role(role_id)
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
    ticket_channel = await guild.create_text_channel(name=f"ticket-{ctx.author.name}", category=category, overwrites=overwrites)
    
    embed = discord.Embed(title="**工單已建立!**", description=f"📄 歡迎使用工單系統。\n管理團隊將迅速為您服務! \n> **👥使用者:** {ctx.author.mention}", color=discord.Color.blue())
    await ticket_channel.send(embed=embed, view=TicketControlView())
    await ctx.send(f"**已為您開啟工單頻道：{ticket_channel.mention}**")

@bot.command(name="user")
async def cmd_user(ctx, member: discord.Member):
    if any(prefix in ctx.channel.name for prefix in ["ticket-", "report-", "ask-", "suggest-"]):
        await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
        await ctx.send(f"**✅ 已成功將 {member.mention} 邀請至本工單頻道。**")
    else:
        await ctx.send("**⚠ 此指令只能在工單頻道內使用!**", delete_after=5)

@bot.command(name="close")
async def cmd_close(ctx):
    if any(prefix in ctx.channel.name for prefix in ["ticket-", "report-", "ask-", "suggest-"]):
        embed = discord.Embed(title="**📨 工單管理選項**", description="**請選擇後續處理方式：**", color=discord.Color.orange())
        await ctx.send(embed=embed, view=TicketPostCloseView())
    else:
        await ctx.send("⚠ 此指令只能在工單頻道內使用。", delete_after=5)

import logging
logging.basicConfig(level=logging.INFO)
bot.run(TOKEN)
