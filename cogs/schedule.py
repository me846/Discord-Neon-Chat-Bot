import discord
from discord.ext import commands, tasks
from discord import app_commands

from datetime import datetime

import re
import pytz
import asyncio


message_data = {}

class ScheduleNotifierCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.notify.start()

    @app_commands.command(
        name='time_add_comment',
        description='通知のために時間とコメントを設定してください'
    )
    async def set_time_and_comment(self, itn: discord.Interaction, time: str, comment: str):
        if not re.match(r'^([0-1]\d|2[0-3]):([0-5]\d)$', time):
            embed = discord.Embed(description="時間は半角数字で00:00の形式で入力してください。（00〜23の間）", color=0xFF0000)
            await itn.response.send_message(embed=embed, ephemeral=True)
            return

        channel = itn.channel
        embed = discord.Embed(description=f"{time}に{comment}が予定されました！リアクションボタンを押してください。",
                        color=0x00FF00,
                        timestamp=datetime.utcnow())
        embed.set_footer(text=f"予定者: {itn.user.display_name}", icon_url=itn.user.display_avatar.url)
        message = await channel.send(embed=embed)
        message_id = message.id
        message_data[message_id] = (time, comment, message, [], False, [], itn.user)

        await message.add_reaction("⏰")
        await message.add_reaction("❌")

        embed = discord.Embed(description=f"通知が{time}に設定されました。", color=0x00FF00)
        await itn.response.send_message(embed=embed, ephemeral=True)
        
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.member == self.bot.user:
            return

        channel = self.bot.get_channel(payload.channel_id)
        message_id = payload.message_id
        if message_id in message_data:
            time, comment, message, users, cancelled, cancelled_messages, author = message_data[message_id]
            if payload.message_id == message.id:
                if str(payload.emoji) == "⏰":
                    embed = discord.Embed(description=f"{time}に通知されます。", color=0x00FF00)
                    notify_message = await channel.send(f"{payload.member.mention}", embed=embed)
                    users.append(payload.member.mention)
                    cancelled_messages.append(notify_message)
                    message_data[message_id] = (time, comment, message, users, cancelled, cancelled_messages, author)

                    delete_after = 3
                    await asyncio.sleep(delete_after)
                    try:
                        await notify_message.delete()
                    except discord.NotFound:
                        pass  # 何も行わない

                elif str(payload.emoji) == "❌" and payload.member == author:
                    if not cancelled:
                        embed = discord.Embed(description="予定をキャンセルされました", color=0xFF0000)
                        await message.reply(embed=embed)
                        for msg in cancelled_messages:
                            await msg.delete()
                        await message.clear_reactions()
                        message_data[message_id] = (time, comment, message, users, True, [], author)
                        
    @tasks.loop(seconds=1)
    async def notify(self):
        while True:
            for message_id, data in list(message_data.items()):
                scheduled_time, comment, message, users, cancelled, cancelled_messages, author = data

                # 現在のUTC時間を取得し、日本時間に変換
                utc_now = datetime.now(pytz.utc)
                jst_now = utc_now.astimezone(pytz.timezone("Asia/Tokyo"))
                current_time = jst_now.strftime('%H:%M')

                if current_time == scheduled_time and not cancelled:
                    if not users:  # ユーザーがいない場合
                        embed = discord.Embed(description="誰も居ませんね！予定をキャンセルします！", color=0xFF0000)
                        await message.reply(embed=embed)
                        await message.clear_reactions()
                        if message_id in message_data:
                            del message_data[message_id]
                    else:
                        channel = self.bot.get_channel(message.channel.id)
                        if channel:
                            mentions = ' '.join(users)
                            embed = discord.Embed(description="予定の時間だよ！", color=0x00FF00)
                            await channel.send(f"{mentions}", embed=embed)
                            await message.clear_reaction("⏰")
                            await message.clear_reaction("❌")
                            if message_id in message_data:
                                del message_data[message_id]

            await asyncio.sleep(1)  # 1秒ごとにチェック
            
    @notify.before_loop
    async def before_notify(self):
        print('waiting until bot is ready')
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(ScheduleNotifierCog(bot))
