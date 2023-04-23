import re
import os
import discord
import asyncio
import random
import asyncio
import pytz
from discord.ext import tasks
from discord import app_commands
from discord import Embed
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.voice_states = True
intents.messages = True
intents.reactions = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


message_data = {}
private_channels = {}
sub_admin_roles = defaultdict(lambda: None)


@client.event
async def on_ready():
    print(f"{client.user.name} is ready!")
    await tree.sync()
    client.loop.create_task(notify())  # タスクを開始

    # プライベートチャンネルを検索して辞書に追加
    for guild in client.guilds:
        for category in guild.categories:
            for voice_channel in category.voice_channels:
                # テキストチャンネル名をチェックするために、VCの名前に接尾辞を追加
                text_channel_name = f"{voice_channel.name}-private"
                text_channel = discord.utils.get(category.text_channels, name=text_channel_name)
                if text_channel:
                    private_channels[voice_channel.id] = text_channel


# ここから予定投票、及び通知コード
@tree.command(name="time_add_comment", description="通知のために時間とコメントを設定してください")
async def set_time_and_comment(interaction: discord.Interaction, time: str, comment: str):
    if not re.match(r'^([0-1]\d|2[0-3]):([0-5]\d)$', time):
        embed = Embed(description="時間は半角数字で00:00の形式で入力してください。（00〜23の間）", color=0xFF0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    channel = interaction.channel
    embed = Embed(description=f"{time}に{comment}が予定されました！リアクションボタンを押してください。",
                  color=0x00FF00,
                  timestamp=datetime.utcnow())
    embed.set_footer(text=f"予定者: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
    message = await channel.send(embed=embed)
    message_id = message.id
    message_data[message_id] = (time, comment, message, [], False, [], interaction.user)

    await message.add_reaction("⏰")
    await message.add_reaction("❌")

    embed = Embed(description=f"通知が{time}に設定されました。", color=0x00FF00)
    await interaction.response.send_message(embed=embed, ephemeral=True)  # メッセージを隠す


@client.event
async def on_raw_reaction_add(payload):
    if payload.member == client.user:
        return

    channel = client.get_channel(payload.channel_id)
    message_id = payload.message_id
    if message_id in message_data:
        time, comment, message, users, cancelled, cancelled_messages, author = message_data[message_id]
        if payload.message_id == message.id:
            if str(payload.emoji) == "⏰":
                embed = Embed(description=f"{time}に通知されます。", color=0x00FF00)
                notify_message = await channel.send(f"{payload.member.mention}", embed=embed)
                users.append(payload.member.mention)
                cancelled_messages.append(notify_message)
                message_data[message_id] = (time, comment, message, users, cancelled, cancelled_messages, author)
                
                # メッセージを数秒後に削除
                delete_after = 5  # 5秒後に削除する
                await asyncio.sleep(delete_after)
                await notify_message.delete()
                
            elif str(payload.emoji) == "❌" and payload.member == author:
                if not cancelled:
                    embed = Embed(description="予定をキャンセルされました", color=0xFF0000)
                    await message.reply(embed=embed)  # メッセージに直接返信
                    for msg in cancelled_messages:
                        await msg.delete()  # メッセージを削除
                    await message.clear_reactions()  # リアクションを全削除
                    message_data[message_id] = (time, comment, message, users, True, [], author)

async def notify():
    while True:
        for message_id, data in list(message_data.items()):
            scheduled_time, comment, message, users, cancelled, cancelled_messages, author = data

            # 現在のUTC時間を取得し、日本時間に変換
            utc_now = datetime.now(pytz.utc)
            jst_now = utc_now.astimezone(pytz.timezone("Asia/Tokyo"))
            current_time = jst_now.strftime('%H:%M')

            if current_time == scheduled_time and not cancelled:
                if not users:  # ユーザーがいない場合
                    embed = Embed(description="誰も居ませんね！予定をキャンセルします！", color=0xFF0000)
                    await message.reply(embed=embed)
                    await message.clear_reactions()
                    if message_id in message_data:  # KeyErrorを発生させないように
                        del message_data[message_id]
                else:
                    channel = client.get_channel(message.channel.id)
                    if channel:
                        mentions = ' '.join(users)
                    embed = Embed(description="予定の時間だよ！", color=0x00FF00)
                    await channel.send(f"{mentions}", embed=embed)
                    await message.clear_reaction("⏰")
                    await message.clear_reaction("❌")
                    if message_id in message_data:  # KeyErrorを発生させないように
                        del message_data[message_id]

        await asyncio.sleep(1)  # 1秒毎にチェック


# 特定のメンバーのIDとメッセージを定義
specific_member_greetings = {
    "218412882986008576": [
        "{member.mention} 魔王が来たぞ！皆逃げよ！",
        "{member.mention} 今日はナミが使えないでしょう",
        "{member.mention} 今日はジャンナが使えないでしょう",
    ],
    "319163497822945300": [
        "{member.mention} 飛べない鳥はただの鳥だ",
        "{member.mention} 鳥の唐揚げ食す？",
    ],
    "318979735822663681": [
        "{member.mention} 東山動植物園は鹿を管理しておりません。おかえりください",
        "{member.mention} 貴方…。奈良公園から脱走してきたの?",
        "{member.mention} :poop:",
    ],
    "284985396545454091": [
        "{member.mention} :poop:",
        "{member.mention} スライムさんは転生者なんだ。大変だったね",
        "{member.mention} 初めまして！　俺はスライムのぐみ！”。悪いスライムじゃ無いよ！",
    ],
    "611618187540168725": [
        "{member.mention} マスター！Vcチャットはこちらですよ！",
    ],
}

async def send_greeting(member, private_channel):
    if str(member.id) in specific_member_greetings:
        greeting_options = specific_member_greetings[str(member.id)]
        chosen_greeting = random.choice(greeting_options)
        greeting_message = chosen_greeting.format(member=member)
        await private_channel.send(greeting_message)
    else:
        # 通常の挨拶メッセージはランダムなメッセージを送るようになっています
        # ランダムな挨拶メッセージのリストを定義します
        random_greetings = [
        # デフォ
        f"{member.mention} VCチャットはこっちだよ！",
        # お嬢様
        f"{member.mention} まあ、ご来訪いただき恐悦至極でございます。どうぞお入りくださいませ",
        f"{member.mention} ご来訪を心よりお待ち申し上げておりました。どうぞお入りいただき、おくつろぎください。",
        f"{member.mention} お客様のご来訪、誠に光栄でございます。どうぞお気軽にお入りくださいませ。",
        # ツンデレ
        f"{member.mention} あんた、ここに来るなんて…まあ、入ってもいいけどね！",
        f"{member.mention} なんであんたが来たのか分からないけど、仕方ないわね。入っていいわよ。",
        f"{member.mention} 何でこんなところに？別に歓迎してるわけじゃないんだから。まあ、入っていいわよ。",
        # 天然
        f"{member.mention} あら、ここに来たのね。どうぞ、どうぞ、お入りなさい。",
        f"{member.mention} わあ、来てくれたんだね。どうぞ、お気軽にお入りください。",
        f"{member.mention} Vわあ、来てくれたんだね。どうぞ、お気軽にお入りください。",
        # 中二病
        f"{member.mention} 闇の扉を叩いた者よ、我が領域への侵入を許可する。",
        f"{member.mention} おお、来たるべき者が現れたか。さあ、我が深淵へ進め！",
        f"{member.mention} 運命の導きにより、ここへ辿り着いたか。恐れることなく、入っておくれ。",
        f"{member.mention} 終焉の地にてお前を待ち受けていた。勇気を持ち、我が領域へ入るがいい。",
        # 執事
        f"{member.mention} ご来訪誠にありがとうございます。どうぞお入りくださいませ、お客様。",
        f"{member.mention} いらっしゃいませ、お客様。こちらへどうぞお進みいただき、おくつろぎいただければと存じます。",
        f"{member.mention} ご来館いただき、誠にありがとうございます。どうぞお気軽にお入りください。",
        f"{member.mention} お越しいただき光栄でございます。どうぞお入りいただき、おくつろぎください。",
        ]

@tree.command(name="add_greeting", description="特定のメンバーに新しい挨拶を追加します")
async def add_greeting(interaction: discord.Interaction, member_id: str, greeting: str):
    if member_id not in specific_member_greetings:
        specific_member_greetings[member_id] = []

    specific_member_greetings[member_id].append(greeting)
    await interaction.response.send_message(f"{member_id} に新しい挨拶を追加しました: {greeting}", ephemeral=True)

@tree.command(name="remove_greeting", description="特定のメンバーから挨拶を削除します")
async def remove_greeting(interaction: discord.Interaction, member_id: str, greeting_index: int):
    if member_id not in specific_member_greetings:
        await interaction.response.send_message(f"{member_id} には挨拶が登録されていません", ephemeral=True)
        return

    greetings = specific_member_greetings[member_id]
    if greeting_index < 0 or greeting_index >= len(greetings):
        await interaction.response.send_message(f"{member_id} の挨拶のインデックスが無効です。有効なインデックスを指定してください。", ephemeral=True)
        return

    removed_greeting = greetings.pop(greeting_index)
    await interaction.response.send_message(f"{member_id} から挨拶を削除しました: {removed_greeting}", ephemeral=True)

#　メッセージを全削除 
async def delete_all_messages(channel):
    async for message in channel.history(limit=None):
        await message.delete()

# VC用プライベートチャンネル
@client.event
async def on_voice_state_update(member, before, after):
    if before.channel != after.channel:
        if after.channel:  # ユーザーがボイスチャンネルに参加した場合
            guild = after.channel.guild
            private_channel = private_channels.get(after.channel.id)

            if private_channel is None:
                subadmin_role = discord.utils.get(guild.roles, name="sub_admin")
                if subadmin_role is None:
                    subadmin_role = await guild.create_role(name="sub_admin")

                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    guild.me: discord.PermissionOverwrite(read_messages=True),
                    member: discord.PermissionOverwrite(read_messages=True),
                    subadmin_role: discord.PermissionOverwrite(read_messages=True)
                }

                # 同じ名前のテキストチャンネルが既に存在するかどうかを確認する
                text_channel_name = after.channel.name
                existing_channel = discord.utils.get(guild.text_channels, name=text_channel_name, category=after.channel.category)

                if existing_channel:
                    private_channel = existing_channel
                else:
                    private_channel = await guild.create_text_channel(
                        name=text_channel_name,
                        overwrites=overwrites,
                        category=after.channel.category
                    )

                private_channels[after.channel.id] = private_channel

            await private_channel.set_permissions(member, read_messages=True)

            # メンバーがボットでない場合にのみ挨拶を送信する
            if not member.bot:
                await send_greeting(member, private_channel)

    if before.channel:  # ユーザーがボイスチャンネルから退出した場合
        private_channel = private_channels.get(before.channel.id)
        if private_channel:
            # メンバーがボットでない場合にのみ、権限をリセットする
            if not member.bot:
                await private_channel.set_permissions(member, read_messages=None)

            # ボイスチャンネルに誰もいない場合は、チャットをクリアする
            if len(before.channel.members) == 0:
                async for message in private_channel.history(limit=50):
                    try:
                        await message.delete()
                    except discord.errors.NotFound:
                        pass  # メッセージが既に削除されている場合は無視する

# ヘルプコマンド
@tree.command(name="help", description="このボットの使い方を表示します。")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="ボットの使い方", color=discord.Color.blue())

    embed.add_field(name="/time_add_comment <time> <comment>", value="指定した時刻とコメントで通知を設定します。\n例: `/time_add_comment 14:30 会議が始まります。`", inline=False)
    embed.add_field(name="ボイスチャンネルへの参加/退出", value="ボイスチャンネルに参加すると、専用のプライベートテキストチャンネルが作成されます。ボイスチャンネルから退出すると、そのテキストチャンネルへのアクセスが解除されます。全員が退出するとプライベートチャンネル内のチャットは削除されます。*2", inline=False)
    embed.add_field(name="*1", value="サブ管理者は管理者以外に/delete_messageを使うために必要な権限です。今後この権限を使ったコマンドを実装予定です", inline=False)
    embed.add_field(name="*2", value="APIレートが制限された場合、最小限の動作になります。/n詳しくはhttps://support-dev.discord.com/hc/ja/articles/6223003921559-%E7%A7%81%E3%81%AEBot%E3%81%8C%E3%83%AC%E3%83%BC%E3%83%88%E5%88%B6%E9%99%90%E3%81%95%E3%82%8C%E3%81%A6%E3%82%8B-　 ", inline=False)

    # ヘルプメッセージを送信します
    await interaction.response.send_message(embed=embed) # メッセージを隠す

client.run(TOKEN)
