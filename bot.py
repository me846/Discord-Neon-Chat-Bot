import re
import os
import discord
import asyncio
from datetime import datetime
from collections import defaultdict
import random
import asyncio
from dotenv import load_dotenv
import pytz

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
openai.api_key = os.getenv("OPENAI_API_KEY")

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
        await interaction.followup.send("トークンの仕様上限に達しています。", ephemeral=True)
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
        limit = 100 if is_all else min(n - deleted_count, 100)
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
@tree.command(name="time_add_comment", description="Set a time and comment for a notification")
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
        f"{member.mention} VCチャットはこちらにございますわ",
        f"{member.mention} VCチャットの場所は、こちらですわ。お役に立てれば幸いです",
        # ツンデレ
        f"{member.mention} …ったく、VCチャットなんて、私が教えなきゃダメなの？ そんなもの、こっちよ",
        f"{member.mention} な、VCチャットだって、普通は自分で探すものじゃないの？…でも、仕方ないわね、こっちよ",
        f"{member.mention} VCチャット？もちろん、こっちよ。わざわざ教えてあげるから、感謝しなさいよ",
        # ボク娘
        f"{member.mention} えっと、VCチャット、こっちの方がありますよ～。使ってみますか？",
        f"{member.mention} VCチャットの機能が必要でしたら、こちらを使ってもいいですよ。私がお手伝いします",
        f"{member.mention} VCチャットの場所は、こっちの方にありますよ。使い方が分からなかったら、私に聞いてくださいね",
        # 中二病
        f"{member.mention} 呼吸を整えよう。VCチャットの場所は、ここにある…！",
        f"{member.mention} 見たまえ！VCチャットの場所は、ここにあるぞ！",
        f"{member.mention} 何ということだ…VCチャットの場所は、ここにあったとは…！",
        # 幼馴染
        f"{member.mention} ねえねえ、VCチャットって、こっちにあるんだよ。使ってみる？」",
        f"{member.mention} ねえ、VCチャットの場所知ってる？こっちにあるんだよ。使ってみたい？",
        # イケメン
        f"{member.mention} Yo、VCチャットだぜ。場所はこっちだ。使ってみる？",
        f"{member.mention} Hey、VCチャットだ。場所はこっちだ。使うか？",
        f"{member.mention} What's up、VCチャットだぜ。場所はこっちだ。使ってみる？",
        # 俺様
        f"{member.mention} …フッ、VCチャットか。その場所はここだ。使うか？",
        f"{member.mention} 俺が教える必要のあることか？VCチャットなら、ここだ。使うか？",
        f"{member.mention} VCチャットって…場所はここだ。使いたかったらどうぞ",
        # メスガキ
        f"{member.mention} VCチャット？場所はこっちにあるんだよ。ほんと、はずかしくないのぉ?こんな簡単なことで！ざっこ〜♥",
        f"{member.mention} VCチャットの場所はここだよ。オジサン、わかってる？",
        # ヤンデレ
        f"{member.mention} VCチャットはここだよ。ねえ、私がいないとダメなんでしょ？私以外の人と話したら、許さないわ。",
        f"{member.mention} VCチャット、ここにあるの。私と話して、他の誰とも話さないでね。そうでないと、大変なことになるわよ？",
        # 大阪弁
        f"{member.mention} VCチャットやなぁ、ここにあるわ。しゃべりたいことあったら言うてや。",
        f"{member.mention} VCチャット、ここにあるわ。話したいことあったら、どんどん言うてくれ。",
        
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

    embed.add_field(name="/time_add_comment <time> <comment>", value="指定した時刻とコメントで通知を設定します。\n例: `/time_add_comment 14:30 会議が始まります。`", inline=False)
    embed.add_field(name="/sub_admin_add <@member>", value="指定されたメンバーにサブ管理者の役職を付与します。\n例: `/sub_admin_add @member`", inline=False)
    embed.add_field(name="/delete_message <n>", value="指定された数のメッセージを削除します。nに'all'を入力すると、チャンネル内のすべてのメッセージが削除されます。\n例: `/delete_message 10`", inline=False)
    embed.add_field(name="ボイスチャンネルへの参加/退出", value="ボイスチャンネルに参加すると、専用のプライベートテキストチャンネルが作成されます。ボイスチャンネルから退出すると、そのテキストチャンネルへのアクセスが解除されます。全員が退出するとプライベートチャンネル内のチャットは削除されます", inline=False)

    # ヘルプメッセージを送信します
    await interaction.response.send_message(embed=embed) # メッセージを隠す

client.run(TOKEN)
