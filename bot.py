import re
import os
import discord
import asyncio
import random
import asyncio
import pytz
import openai
from discord.ext import tasks
from discord import app_commands
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
openai.api_key = os.getenv("OPENAI_API_KEY")

TOKEN_LIMIT = 10000  # 例: 1ヶ月あたりのトークン使用量上限
PREVIOUS_MESSAGES_LIMIT = 3
user_token_count = {}  # 各ユーザーのトークン使用量を格納するディクショナリ

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


# サブ管理者の役職を検索して辞書に追加
async def is_bot_admin(ctx):
    bot_admin_id = "BOT_ADMIN_USER_ID"
    return ctx.author.id == int(BOT_ADMIN_ID=611618187540168725)

# サブ管理者の追加(管理者のみのコマンド)
@tree.command(name="sub_admin_add", description="指定されたユーザーにサブ管理者の役職を付与する")
async def sub_admin_add(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("このコマンドはサーバーの管理者のみが使用できます。", ephemeral=True)
        return

    # 役職が存在しない場合に役職を作成する
    sub_admin_role = discord.utils.get(interaction.guild.roles, name="sub_admin")
    if sub_admin_role is None:
        sub_admin_role = await interaction.guild.create_role(name="sub_admin")

    # 指定されたユーザーにサブ管理者の役職を付与する
    await member.add_roles(sub_admin_role)
    await interaction.response.send_message(f"{member.display_name}にサブ管理者の役職を付与しました。")

    
# Chat gptのチャット機能
@tree.command(name="chat", description="AIとのチャット機能です")
async def chat(interaction: discord.Interaction, prompt: str):
    # ユーザートークンの辞書が存在するかどうかを確認し、存在しない場合は作成する
    if not hasattr(client, 'user_token_count'):
        client.user_token_count = {}

    # ユーザーが既に辞書に存在するかどうかを確認し、存在しない場合は0トークン使用で追加する
    user_id = interaction.user.id
    if user_id not in client.user_token_count:
        client.user_token_count[user_id] = 0

    # 応答を遅延させる
    await interaction.response.defer(ephemeral=True)

    # ユーザーがトークン制限を超過していないか確認する
    if client.user_token_count[user_id] >= TOKEN_LIMIT:
        await interaction.followup.send("トークンの使用量上限に達しています。", ephemeral=True)
        return

    # プロンプトの最後に改行を追加する
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=f"{prompt}\nAI:",
        max_tokens=1000,
        n=1,
        stop=None,
        temperature=0.5,
    )
    response_text = response.choices[0].text.strip()

    

    await interaction.followup.send(response_text, ephemeral=False)

    # ユーザーのトークン使用量を更新する
    client.user_token_count[user_id] += len(response_text)

    # 残りのトークン数を表示する
    remaining_tokens = TOKEN_LIMIT - client.user_token_count[user_id]
    await interaction.followup.send(f"残りのトークン数: {remaining_tokens}", ephemeral=True)




# メッセージn削除　All削除
@tree.command(name="delete_message", description="指定された数のメッセージを削除する")
async def delete_message(interaction: discord.Interaction, n: str):
    subadmin_role = discord.utils.get(interaction.guild.roles, name="sub_admin")
    if not (interaction.user.guild_permissions.administrator or (subadmin_role and subadmin_role in interaction.user.roles)):
        await interaction.response.send_message("このコマンドはサーバーの管理者またはsub_admin役職のユーザーのみが使用できます。", ephemeral=True)
        return

    await interaction.response.defer()

    if n != "all":
        try:
            n = int(n)
            if n < 1 or n > 100:
                raise ValueError()
        except ValueError:
            await interaction.followup.send("削除するメッセージ数は1から100の範囲で指定してください。", ephemeral=True)
            return
    else:
        # 確認メッセージ
        confirm_message = await interaction.channel.send("本当に全てのメッセージを削除しますか？")
        await confirm_message.add_reaction("✅")
        await confirm_message.add_reaction("❌")

        def check(reaction, user):
            return user == interaction.user and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == confirm_message.id

        try:
            reaction, _ = await interaction.client.wait_for("reaction_add", timeout=60.0, check=check)
        except asyncio.TimeoutError:
            await confirm_message.delete()
            return

        if str(reaction.emoji) == "❌":
            await confirm_message.delete()
            return

        await confirm_message.delete()

    deleted_count = 0
    original_message_id = interaction.data["id"]
    is_all = n == "all"

    while is_all or deleted_count < n:
        limit = 50 if is_all else min(n - deleted_count, 50)
        messages = []
        async for message in interaction.channel.history(limit=limit):
            if message.id != original_message_id:  # オリジナルのメッセージは削除しない
                messages.append(message)
        if not messages:
            break
        await interaction.channel.delete_messages(messages)
        deleted_count += len(messages)
        await asyncio.sleep(1)  # レート制限に引っかからないように待機

    await interaction.channel.send(f"{deleted_count}個のメッセージを削除しました。")




# ここから予定投票、及び通知コード
@tree.command(name="time_add_comment", description="通知のために時間とコメントを設定してください")
async def set_time_and_comment(interaction: discord.Interaction, time: str, comment: str):
    if not re.match(r'^([0-1]\d|2[0-3]):([0-5]\d)$', time):
        await interaction.response.send_message("時間は半角数字で00:00の形式で入力してください。（00〜23の間）", ephemeral=True)
        return

    channel = interaction.channel
    message = await channel.send(f"> ```py\n> {time}に{comment}が予定されました！リアクションボタンを押してください。```\n")
    message_id = message.id
    message_data[message_id] = (time, comment, message, [], False, [], interaction.user)

    await message.add_reaction("⏰")
    await message.add_reaction("❌")

    await interaction.response.send_message(f"> ```py\n> 通知が{time}に設定されました。```\n", ephemeral=True) #メッセージを隠す

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
                notify_message = await channel.send(f"> {payload.member.mention} ```py\n> {time}に通知されます。```\n")
                users.append(payload.member.mention)
                cancelled_messages.append(notify_message)
                message_data[message_id] = (time, comment, message, users, cancelled, cancelled_messages, author)
            elif str(payload.emoji) == "❌" and payload.member == author:
                if not cancelled:
                    await message.reply("__:warning:予定をキャンセルされました:warning:__")  # メッセージに直接返信
                    for msg in cancelled_messages:
                        await msg.delete() # メッセージを削除
                    await message.clear_reactions() # リアクションを全削除
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
                if not users: # ユーザーがいない場合
                    await message.reply("__:warning:誰も居ませんね！予定をキャンセルします！:warning:__")
                    await message.clear_reactions()
                    if message_id in message_data: # KeyErrorを発生させないように
                        del message_data[message_id]
                else:
                    channel = client.get_channel(message.channel.id)
                    if channel:
                        mentions = ' '.join(users)
                    await channel.send(f"> {mentions} **予定の時間だよ！**")
                    await message.clear_reaction("⏰")
                    await message.clear_reaction("❌")
                    if message_id in message_data: # KeyErrorを発生させないように
                        del message_data[message_id]

        await asyncio.sleep(1)  # 1秒毎にチェック


# メンバー入場時の挨拶
async def send_greeting(member, private_channel):
    # 特定のメンバーのIDとメッセージを定義します
    specific_members = {
        # gacya
        "218412882986008576": f"{member.mention} 魔王が来たぞ！皆逃げよ！",
        "218412882986008576": f"{member.mention} 今日はナミが使えないでしょう",
        "218412882986008576": f"{member.mention} 今日はジャンナが使えないでしょう",

        # piko
        "319163497822945300": f"{member.mention} 飛べない鳥は只の鳥だ",
        "319163497822945300": f"{member.mention} 鳥の唐揚げ食す？",
        
        # shika
        "318979735822663681": f"{member.mention} 東山動植物園は鹿を管理しておりません。おかえりください",
        "318979735822663681": f"{member.mention} 貴方…。奈良公園から脱走してきたの?",
        "318979735822663681": f"{member.mention} :poop:",

        # gummy
        "284985396545454091": f"{member.mention} :poop:",
        "284985396545454091": f"{member.mention} スライムさんは転生者なんだ。大変だったね",
        "284985396545454091": f"{member.mention} 初めまして！　俺はスライムのぐみ！”。悪いスライムじゃ無いよ！",

        # miya
        "611618187540168725": f"{member.mention} マスター！Vcチャットはこちらですよ！",
        
    }

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

    # 特定のメンバーに対してメッセージを送信するか、ランダムなメッセージを送信します
    if str(member.id) in specific_members:
        await private_channel.send(specific_members[str(member.id)])
    else:
        await private_channel.send(random.choice(random_greetings))

# VC用プライベートチャンネル
@client.event
async def on_voice_state_update(member, before, after):
    if after.channel and not before.channel:  # ユーザーがボイスチャンネルに参加した場合
        guild = after.channel.guild
        private_channel = private_channels.get(after.channel.id)

        if private_channel is None:
            subadmin_role = discord.utils.get(guild.roles, name="sub_admin")
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
        await send_greeting(member, private_channel)

    elif before.channel and not after.channel:  # ユーザーがボイスチャンネルから退出した場合
        private_channel = private_channels.get(before.channel.id)
        if private_channel:
            await private_channel.set_permissions(member, read_messages=False)

            # ボイスチャンネルに誰もいない場合は、チャットをクリアする
            if len(before.channel.members) == 0:
                async for message in private_channel.history(limit=10):
                    await message.delete()

# ヘルプコマンド
@tree.command(name="help", description="このボットの使い方を表示します。")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="ボットの使い方", color=discord.Color.blue())

    embed.add_field(name="/sub_admin_add <@member>", value="指定されたメンバーにサブ管理者の役職を付与します。*1\n例: `/sub_admin_add @member`", inline=False)
    embed.add_field(name="/chat [prompt]", value="AIとチャットを楽しむためのコマンドです。\n[prompt]に質問や会話の内容を入力してください。", inline=False)
    embed.add_field(name="/time_add_comment <time> <comment>", value="指定した時刻とコメントで通知を設定します。\n例: `/time_add_comment 14:30 会議が始まります。`", inline=False)
    embed.add_field(name="/delete_message <n>", value="指定された数のメッセージを削除します。nに'all'を入力すると、チャンネル内のすべてのメッセージが削除されます。*2\n例: `/delete_message 10`", inline=False)
    embed.add_field(name="ボイスチャンネルへの参加/退出", value="ボイスチャンネルに参加すると、専用のプライベートテキストチャンネルが作成されます。ボイスチャンネルから退出すると、そのテキストチャンネルへのアクセスが解除されます。全員が退出するとプライベートチャンネル内のチャットは削除されます", inline=False)
    embed.add_field(name="*1", value="サブ管理者は管理者以外に/delete_messageを使うために必要な権限です。今後この権限を使ったコマンドを実装予定です", inline=False)
    embed.add_field(name="*2", value="APIレートが制限された場合、最小限の動作になります。/n詳しくはhttps://support-dev.discord.com/hc/ja/articles/6223003921559-%E7%A7%81%E3%81%AEBot%E3%81%8C%E3%83%AC%E3%83%BC%E3%83%88%E5%88%B6%E9%99%90%E3%81%95%E3%82%8C%E3%81%A6%E3%82%8B-　 ", inline=False)

    # ヘルプメッセージを送信します
    await interaction.response.send_message(embed=embed) # メッセージを隠す

client.run(TOKEN)
