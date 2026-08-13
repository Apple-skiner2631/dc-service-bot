import asyncio
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select, UserSelect


TRIGGER_CHANNEL_ID = 1530974075902759083
CATEGORY_ID = 1459692616076624087
STAFF_ROLE_ID = 1459696673239470338

WHITELIST_CHANNEL_IDS = {
    TRIGGER_CHANNEL_ID,
    1531994737819779112
}


voice_owners = {1008278721007992863 ,1487725330117562399 ,1359813653544566815}


E_MENU_SETTINGS = discord.PartialEmoji(name="menu_settings", id=1531236010413920276)
E_NAME     = discord.PartialEmoji(name="e_name",     id=1531235954893783070)
E_LIMIT    = discord.PartialEmoji(name="e_limit",    id=1531235983956377742)
E_STATUS   = discord.PartialEmoji(name="e_status",   id=1531236041736978563)
E_GAME     = discord.PartialEmoji(name="e_game",     id=1531236073768751235)
E_LFM      = discord.PartialEmoji(name="e_lfm",      id=1531236105914159154)
E_BITRATE  = discord.PartialEmoji(name="e_bitrate",  id=1531236135202848938)
E_REGION   = discord.PartialEmoji(name="e_region",   id=1531236162763620422)
E_TEXT     = discord.PartialEmoji(name="e_text",     id=1531236193503547565)
E_NSFW     = discord.PartialEmoji(name="e_nsfw",     id=1531236231122391133)
E_CLAIM    = discord.PartialEmoji(name="e_claim",    id=1531237261205573654)

E_LOCK     = discord.PartialEmoji(name="e_lock",     id=1531236263338709093)
E_UNLOCK   = discord.PartialEmoji(name="e_unlock",   id=1531237058662633492)
E_PERMIT   = discord.PartialEmoji(name="e_permit",   id=1531237091264954418)
E_REJECT   = discord.PartialEmoji(name="e_reject",   id=1531237123514961931)
E_INVITE   = discord.PartialEmoji(name="e_invite",   id=1531237152736678089)
E_GHOST    = discord.PartialEmoji(name="e_ghost",    id=1531237201780805723)
E_UNGHOST  = discord.PartialEmoji(name="e_unghost",  id=1531237228905496826)
E_TRANSFER = discord.PartialEmoji(name="e_transfer", id=1531237291639439492)


def is_authorized(member: discord.Member, channel_id: int) -> bool:
    owner_id = voice_owners.get(channel_id)
    if member.id == owner_id:
        return True
    if member.guild_permissions.manage_channels:
        return True
    if any(role.id == STAFF_ROLE_ID for role in member.roles):
        return True
    return False


class DeleteTextChannelView(View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=None)
        self.owner_id = owner_id

    @discord.ui.button(label="刪除頻道", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_channel(self, interaction: discord.Interaction, button: Button):
        if not is_authorized(interaction.user, interaction.channel.id) and interaction.user.id != self.owner_id:
            return await interaction.response.send_message("❌ 只有房主或管理人員才能刪除此文字頻道！", ephemeral=True)
        
        await interaction.response.send_message("🗑️ 專屬文字頻道即將刪除...", ephemeral=True)
        await asyncio.sleep(1)
        await interaction.channel.delete()


class NameModal(Modal, title="修改頻道名稱"):
    channel_name = TextInput(label="新頻道名稱", placeholder="輸入新的語音頻道名稱...", max_length=100)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.channel.edit(name=self.channel_name.value)
        await interaction.response.send_message(f"✅ 頻道名稱已修改為：**{self.channel_name.value}**", ephemeral=True)


class LimitModal(Modal, title="設定人數限制"):
    user_limit = TextInput(label="人數限制 (0 為無限制，上限 99)", placeholder="0", max_length=2)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            limit = int(self.user_limit.value)
            if 0 <= limit <= 99:
                await interaction.channel.edit(user_limit=limit)
                await interaction.response.send_message(f"✅ 人數限制已設定為：**{limit if limit > 0 else '無限制'}**", ephemeral=True)
            else:
                await interaction.response.send_message("❌ 請輸入 0 到 99 之間的數字！", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ 請輸入有效的數字！", ephemeral=True)


class StatusModal(Modal, title="設定頻道狀態"):
    status_text = TextInput(label="頻道狀態", placeholder="輸入目前的狀態文字...", max_length=50)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.channel.edit(status=self.status_text.value)
        await interaction.response.send_message(f"✅ 頻道狀態已更新為：**{self.status_text.value}**", ephemeral=True)


class BitrateModal(Modal, title="調整音質 (位元率)"):
    bitrate_kbps = TextInput(label="位元率 (kbps, 預設 64, 最高 96/128/256/384)", placeholder="64", max_length=3)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            bitrate_value = int(self.bitrate_kbps.value) * 1000
            max_bitrate = interaction.guild.bitrate_limit
            if 8000 <= bitrate_value <= max_bitrate:
                await interaction.channel.edit(bitrate=bitrate_value)
                await interaction.response.send_message(f"✅ 頻道音質已設定為：**{self.bitrate_kbps.value} kbps**", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ 請輸入 8 到 {int(max_bitrate/1000)} kbps 之間的數字！", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ 請輸入有效的數字！", ephemeral=True)


class UserSelectMenu(UserSelect):
    def __init__(self, action_type: str, owner_id: int):
        super().__init__(placeholder="請選擇成員...", min_values=1, max_values=1)
        self.action_type = action_type
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction):
        if not is_authorized(interaction.user, interaction.channel.id):
            return await interaction.response.send_message("❌ 只有房主或管理人員可以使用此選單！", ephemeral=True)

        target_member = self.values[0]
        channel = interaction.channel

        if self.action_type == "permit":
            await channel.set_permissions(target_member, connect=True, view_channel=True)
            await interaction.response.send_message(f"✅ 已允許 {target_member.mention} 加入與查看頻道。", ephemeral=True)

        elif self.action_type == "reject":
            await channel.set_permissions(target_member, connect=False)
            if target_member in channel.members:
                await target_member.move_to(None)
            await interaction.response.send_message(f"🚫 已封鎖並踢出 {target_member.mention}。", ephemeral=True)

        elif self.action_type == "invite":
            await interaction.response.send_message(f"📩 {target_member.mention}，{interaction.user.mention} 邀請你加入頻道：{channel.mention}")

        elif self.action_type == "transfer":
            voice_owners[channel.id] = target_member.id
            await channel.set_permissions(target_member, manage_channels=True, move_members=True)
            await channel.set_permissions(interaction.user, overwrite=None)
            await interaction.response.send_message(f"👑 房主權限已轉移給 {target_member.mention}！")


class UserSelectView(View):
    def __init__(self, action_type: str, owner_id: int):
        super().__init__(timeout=60)
        self.add_item(UserSelectMenu(action_type=action_type, owner_id=owner_id))


class ChannelSettingsSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="修改名稱", description="變更語音频道的名稱", emoji=E_NAME, value="name"),
            discord.SelectOption(label="人數限制", description="設定頻道的最大容納人數", emoji=E_LIMIT, value="limit"),
            discord.SelectOption(label="頻道狀態", description="設定頻道的自訂狀態文字", emoji=E_STATUS, value="status"),
            discord.SelectOption(label="遊戲主題", description="自動將頻道名稱改為你正在玩的遊戲", emoji=E_GAME, value="game"),
            discord.SelectOption(label="組隊尋人", description="發送尋找隊友的訊息通知", emoji=E_LFM, value="lfm"),
            discord.SelectOption(label="調整音質", description="修改頻道的位元率 (Bitrate)", emoji=E_BITRATE, value="bitrate"),
            discord.SelectOption(label="語音區域", description="查看語音伺服器區域資訊", emoji=E_REGION, value="region"),
            discord.SelectOption(label="專屬文字房", description="建立臨時的專屬文字頻道", emoji=E_TEXT, value="text"),
            discord.SelectOption(label="年齡分級", description="切換頻道的 NSFW (限制級) 狀態", emoji=E_NSFW, value="nsfw"),
            discord.SelectOption(label="聲明房主", description="接管目前無人管理的頻道房主權限", emoji=E_CLAIM, value="claim"),
        ]
        super().__init__(placeholder="⚙️ 頻道設定 (Channel Settings)", min_values=1, max_values=1, options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        channel = interaction.channel
        owner_id = voice_owners.get(channel.id)

        await interaction.message.edit(view=ControlPanelView())

        if self.values[0] == "claim":
            if owner_id in [m.id for m in channel.members]:
                return await interaction.response.send_message("❌ 原房主仍在此頻道中，無法轉移所有權！", ephemeral=True)
            voice_owners[channel.id] = interaction.user.id
            await interaction.response.send_message(f"👑 {interaction.user.mention} 已成功轉移並成為此包廂的新房主！")
            return

        if not is_authorized(interaction.user, channel.id):
            return await interaction.response.send_message("❌ 只有房主或管理人員才能進行設定！", ephemeral=True)

        selected = self.values[0]
        if selected == "name":
            await interaction.response.send_modal(NameModal())
        elif selected == "limit":
            await interaction.response.send_modal(LimitModal())
        elif selected == "status":
            await interaction.response.send_modal(StatusModal())
        elif selected == "game":
            game_activity = next((act.name for act in interaction.user.activities if act.type == discord.ActivityType.playing), None)
            if game_activity:
                await channel.edit(name=f"🎮 {game_activity}")
                await interaction.response.send_message(f"✅ 頻道名稱已自動變更為遊戲名稱：**{game_activity}**", ephemeral=True)
            else:
                await interaction.response.send_message("❌ 偵測不到你目前正在遊玩的遊戲狀態！", ephemeral=True)
        elif selected == "lfm":
            await interaction.response.send_message(f"📢 **【組隊尋人】** {interaction.user.mention} 正在包廂 {channel.mention} 尋找隊友！歡迎加入！")
        elif selected == "bitrate":
            await interaction.response.send_modal(BitrateModal())
        elif selected == "region":
            await interaction.response.send_message("ℹ️ 目前伺服器由 Discord 自動指派最佳語音區域。", ephemeral=True)
        
        elif selected == "text":
            staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

            for member in channel.members:
                overwrites[member] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

            text_channel = await interaction.guild.create_text_channel(
                name=f"💬-{channel.name}",
                category=channel.category,
                overwrites=overwrites
            )

            welcome_embed = discord.Embed(
                title=f"💬 {channel.name} - 專屬討論空間",
                description=(
                    f"歡迎來到專屬文字頻道 {text_channel.mention}！\n\n"
                    "📌 **說明：**\n"
                    "• 此頻道為此語音包廂的臨時文字討論區。\n"
                    "• 點擊下方按鈕可由房主或管理員隨時手動刪除此文字頻道。"
                ),
                color=discord.Color.green()
            )
            welcome_embed.set_footer(text=f"房主：{interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

            delete_view = DeleteTextChannelView(owner_id=interaction.user.id)
            await text_channel.send(embed=welcome_embed, view=delete_view)

            await interaction.response.send_message(f"✅ 已為您建立專屬文字頻道：{text_channel.mention}", ephemeral=True)

        elif selected == "nsfw":
            is_nsfw = not channel.nsfw
            await channel.edit(nsfw=is_nsfw)
            status_msg = "已開啟 (NSFW)" if is_nsfw else "已關閉 (SFW)"
            await interaction.response.send_message(f"✅ 頻道分級已更新為：**{status_msg}**", ephemeral=True)


class ChannelPermissionsSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="上鎖頻道", description="上鎖頻道，禁止其他成員隨意加入", emoji=E_LOCK, value="lock"),
            discord.SelectOption(label="解鎖頻道", description="解鎖頻道，允許所有人加入", emoji=E_UNLOCK, value="unlock"),
            discord.SelectOption(label="允許成員", description="允許指定成員查看與加入頻道", emoji=E_PERMIT, value="permit"),
            discord.SelectOption(label="踢出/封鎖", description="封鎖指定成員並將其踢出頻道", emoji=E_REJECT, value="reject"),
            discord.SelectOption(label="邀請成員", description="發送邀請給指定成員加入頻道", emoji=E_INVITE, value="invite"),
            discord.SelectOption(label="隱藏頻道", description="讓頻道對其他人不可見 (隱身模式)", emoji=E_GHOST, value="ghost"),
            discord.SelectOption(label="取消隱藏", description="讓頻道恢復公開顯示", emoji=E_UNGHOST, value="unghost"),
            discord.SelectOption(label="讓渡房主", description="將房主管理權限轉移給其他成員", emoji=E_TRANSFER, value="transfer"),
        ]
        super().__init__(placeholder="🔒 頻道權限 (Channel Permissions)", min_values=1, max_values=1, options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        channel = interaction.channel
        owner_id = voice_owners.get(channel.id)

        await interaction.message.edit(view=ControlPanelView())

        if not is_authorized(interaction.user, channel.id):
            return await interaction.response.send_message("❌ 只有房主或管理人員才能設定權限！", ephemeral=True)

        selected = self.values[0]
        guild = interaction.guild

        if selected == "lock":
            await channel.set_permissions(guild.default_role, connect=False)
            await interaction.response.send_message("🔒 頻道已上鎖，其他成員無法隨意加入。", ephemeral=True)
        elif selected == "unlock":
            await channel.set_permissions(guild.default_role, connect=None)
            await interaction.response.send_message("🔓 頻道已解鎖，所有成員皆可加入。", ephemeral=True)
        elif selected == "ghost":
            await channel.set_permissions(guild.default_role, view_channel=False)
            await interaction.response.send_message("👻 頻道已隱藏 (隱身模式)。", ephemeral=True)
        elif selected == "unghost":
            await channel.set_permissions(guild.default_role, view_channel=None)
            await interaction.response.send_message("⭕ 頻道已解除隱藏，公開顯示。", ephemeral=True)
        elif selected in ["permit", "reject", "invite", "transfer"]:
            action_names = {
                "permit": "允許成員",
                "reject": "踢出/封鎖",
                "invite": "邀請成員",
                "transfer": "讓渡房主"
            }
            view = UserSelectView(action_type=selected, owner_id=owner_id)
            await interaction.response.send_message(f"請選擇要進行 **{action_names[selected]}** 操作的成員：", view=view, ephemeral=True)


class ControlPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ChannelSettingsSelect())
        self.add_item(ChannelPermissionsSelect())


class VoiceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):

        if after.channel and after.channel.id == TRIGGER_CHANNEL_ID:
            guild = member.guild
            category = guild.get_channel(CATEGORY_ID)

            if not category or not isinstance(category, discord.CategoryChannel):
                return

            new_channel = await guild.create_voice_channel(
                name=f"{member.display_name} 的語音頻道",
                category=category,
                position=len(category.channels)
            )

            voice_owners[new_channel.id] = member.id
            await member.move_to(new_channel)

            embed = discord.Embed(
                title="🔊 歡迎來到你的專屬語音頻道",
                description=(
                    f"你好 {member.mention}！\n 使用下方選單調整頻道設定：\n"
                    "──────────────────────────\n"
                    "**頻道設定[Channel Settings]**\n\n"
                    "──────────────────────────\n"
                    "**頻道權限[Channel Permissions]**"
                ),
                color=discord.Color.from_rgb(47, 49, 54)
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="提示：所有人離開頻道後，系統將自動清理此空間。")

            view = ControlPanelView()
            await new_channel.send(embed=embed, view=view)

        if before.channel and before.channel.category_id == CATEGORY_ID:
            if before.channel.id in WHITELIST_CHANNEL_IDS:
                return

            if len(before.channel.members) == 0:
                channel_id = before.channel.id
                try:
                    await before.channel.delete()
                    if channel_id in voice_owners:
                        del voice_owners[channel_id]
                except discord.NotFound:
                    pass


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceCog(bot))
