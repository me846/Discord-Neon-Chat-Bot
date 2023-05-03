import re
import os
import discord
import asyncio
import random
import asyncio
import pytz
import json
from discord.ext import tasks
from discord import app_commands
from discord import Embed
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID"))

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

# 挨拶を保存
def save_greetings(greetings):
    with open("greetings.json", "w", encoding="utf-8") as f:
        json.dump(greetings, f, ensure_ascii=False, indent=2)

# 挨拶を読み込み
def load_greetings():
    try:
        with open("greetings.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# 起動時に読み込む
specific_member_greetings = load_greetings()

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

# interaction.user.idとBOT_OWNER_IDを比較
async def announcement(interaction: discord.Interaction, *, content: str):
    if interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message("このコマンドはBot管理者のみが使用できます。", ephemeral=True)
        return

# アナウンス
@tree.command(
    name="announcement",
    description="Bot管理者がサーバー全体にお知らせを送信します。",
)
async def announcement(interaction: discord.Interaction, *, content: str):
    if interaction.user.id != bot.owner_id:
        await interaction.response.send_message("このコマンドはBot管理者のみが使用できます。", ephemeral=True)
        return

    for guild in bot.guilds:
        # デフォルトのテキストチャンネルを見つける
        default_channel = None
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                default_channel = channel
                break

        if default_channel is not None:
            await default_channel.send(content)
        else:
            print(f"Could not find a suitable channel to send the announcement in {guild.name}")

    await interaction.response.send_message("お知らせが送信されました。", ephemeral=True)
    
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
    "users id 1234567890": [
        "{member.mention} sample text",
    ],
}

async def send_greeting(member, private_channel):
    specific_member_greetings = load_greetings()
    member_id = str(member.id)

    if member_id in specific_member_greetings:
        greetings = specific_member_greetings[member_id]
        greeting = random.choice(greetings)
    else:
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
        greeting = random.choice(random_greetings)
    
    await private_channel.send(greeting)


@tree.command(
    name="add_greeting",
    description="特定のメンバーに対する挨拶を追加します"
)
async def _add_greeting(ctx, member: discord.Member, greeting: str):
    specific_member_greetings = load_greetings()
    member_id = str(member.id)

    if member_id not in specific_member_greetings:
        specific_member_greetings[member_id] = []

    specific_member_greetings[member_id].append(greeting)
    save_greetings(specific_member_greetings)

    embed = Embed(
        title="挨拶を追加しました",
        description=f"{member.mention}: {greeting}",
        color=0x00FF00
    )
    await ctx.response.send_message(embed=embed)

@tree.command(
    name="remove_greeting",
    description="特定のメンバーに対する挨拶を削除します"
)
async def _remove_greeting(ctx, member: discord.Member, index: int):
    specific_member_greetings = load_greetings()
    member_id = str(member.id)

    if member_id not in specific_member_greetings:
        embed = Embed(
            title="エラー",
            description="このメンバーには追加された挨拶がありません。",
            color=0xFF0000
        )
        await ctx.response.send_message(embed=embed)
        return

    greetings = specific_member_greetings[member_id]

    if 0 <= index < len(greetings):
        removed_greeting = greetings.pop(index)
        save_greetings(specific_member_greetings)
        embed = Embed(
            title="削除された挨拶",
            description=f"{member.mention}: {removed_greeting}",
            color=0xFF0000
        )
        await ctx.response.send_message(embed=embed)
    else:
        embed = Embed(
            title="エラー",
            description="無効なインデックスです。`/list_greetings` を使って正しいインデックスを確認してください。",
            color=0xFF0000
        )
        await ctx.response.send_message(embed=embed)
    
@tree.command(
    name="list_greetings",
    description="特定のメンバーに対する挨拶のリストを表示します"
)
async def _list_greetings(ctx, member: discord.Member):
    specific_member_greetings = load_greetings()
    member_id = str(member.id)

    if member_id not in specific_member_greetings or not specific_member_greetings[member_id]:
        embed = Embed(
            title="エラー",
            description="このメンバーには追加された挨拶がありません。",
            color=0xFF0000
        )
        await ctx.response.send_message(embed=embed)
        return

    greetings = specific_member_greetings[member_id]
    greetings_list = "\n".join(f"{idx}: {greeting}" for idx, greeting in enumerate(greetings))

    embed = Embed(
        title=f"{member.name} に対する挨拶のリスト",
        description=greetings_list,
        color=0x00FF00
    )
    await ctx.response.send_message(embed=embed)

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
                await asyncio.sleep(1)  # やや遅延を入れる
                await private_channel.purge(limit=50)

# ヘルプコマンド
@tree.command(name="help", description="このボットの使い方を表示します。")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="ボットの使い方", color=discord.Color.blue())

    embed.add_field(name="/time_add_comment <time> <comment>", value="指定した時刻とコメントで通知を設定します。\n例: `/time_add_comment 14:30 会議が始まります。`", inline=False)
    embed.add_field(name="ボイスチャンネルへの参加/退出", value="ボイスチャンネルに参加すると、専用のプライベートテキストチャンネルが作成されます。ボイスチャンネルから退出すると、そのテキストチャンネルへのアクセスが解除されます。全員が退出するとプライベートチャンネル内のチャットは削除されます。*1", inline=False)
    embed.add_field(name="入場時の挨拶", value="ユーザーがボイスチャンネルに入ると、ボットが設定された挨拶メッセージを送信します。個別のメンバーに対してカスタム挨拶メッセージを設定することができます。", inline=False)
    embed.add_field(name="/add_greeting <member> <greeting>", value="特定のメンバーに対する挨拶を追加します。メンバーは@メンションまたはユーザーIDで指定できます。例: `/add_greeting @username こんにちは、ようこそ！`", inline=False)
    embed.add_field(name="/remove_greeting <member> <index>", value="特定のメンバーに対する挨拶を削除します。\nindexに削除する番号をlistから調べて入力してください。", inline=False)
    embed.add_field(name="/list_greetings <member>", value="特定のメンバーに対する挨拶のリストを表示します。", inline=False)
   
    embed.add_field(name="*1", value="APIレートが制限された場合、最小限の動作になります。\n詳しくはhttps://support-dev.discord.com/hc/ja/articles/6223003921559-%E7%A7%81%E3%81%AEBot%E3%81%8C%E3%83%AC%E3%83%BC%E3%83%88%E5%88%B6%E9%99%90%E3%81%95%E3%82%8C%E3%81%A6%E3%82%8B-　 ", inline=False)
    
# ヘルプメッセージを送信します
    await interaction.response.send_message(embed=embed) # メッセージを隠す

client.run(TOKEN)
