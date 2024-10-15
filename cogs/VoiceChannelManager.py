import discord
from discord.ext import commands
import random
import os
import json
import sqlite3
import re
import time

DB_PATH = os.path.join('data', 'greetings.db')
DATA_FILE = 'private_channels.json'

def init_db():
    if not os.path.exists('data'):
        os.makedirs('data')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS greetings
        (guild_id text, member_id text, greeting text)''')
    conn.commit()
    conn.close()

class VoiceChannelManagerCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.private_channels = {}  # {voice_channel_id: text_channel_id}
        self.load_private_channels()
        self.specific_member_greetings = {}
        init_db()
        self.load_greetings()

    def load_private_channels(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                self.private_channels = json.load(f)
        else:
            self.private_channels = {}

    def save_private_channels(self):
        with open(DATA_FILE, 'w') as f:
            json.dump(self.private_channels, f)

    def load_greetings(self):
        # データベースから挨拶メッセージを読み込み
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT member_id, greeting FROM greetings')
        rows = c.fetchall()
        self.specific_member_greetings = {}
        for member_id, greeting in rows:
            if member_id in self.specific_member_greetings:
                self.specific_member_greetings[member_id].append(greeting)
            else:
                self.specific_member_greetings[member_id] = [greeting]
        conn.close()

    def save_greeting(self, member_id, greeting):
        # 挨拶メッセージをデータベースに保存
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('INSERT INTO greetings (guild_id, member_id, greeting) VALUES (?, ?, ?)', (str(self.bot.guilds[0].id), member_id, greeting))
        conn.commit()
        conn.close()

    def sanitize_channel_name(self, name):
        # 先頭と末尾の空白を削除
        name = name.strip()
        # スペースをハイフンに置き換え
        name = name.replace(" ", "-")
        # 複数のハイフンを一つのハイフンに統合
        name = re.sub(r'-+', '-', name)
        # 制御文字や印字できない文字を除去
        name = ''.join(c for c in name if c.isprintable() and not c.isspace())
        # チャンネル名の長さを1～100文字に制限
        name = name[:100]
        # チャンネル名が空の場合、デフォルトの名前を設定
        if not name:
            name = f"vc-{int(time.time())}"
        return name

    @commands.Cog.listener()
    async def on_ready(self):
        await self.initialize_private_channels()

    async def initialize_private_channels(self):
        for voice_channel_id, text_channel_id in list(self.private_channels.items()):
            voice_channel = self.bot.get_channel(int(voice_channel_id))
            text_channel = self.bot.get_channel(int(text_channel_id))
            if voice_channel and text_channel:
                for member in voice_channel.members:
                    await text_channel.set_permissions(member, read_messages=True, send_messages=True)
            else:
                # チャンネルが存在しない場合はデータを削除
                self.private_channels.pop(voice_channel_id)
        self.save_private_channels()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # ユーザーが新しいチャンネルに参加した場合
        if after.channel and (before.channel != after.channel):
            await self.handle_user_join(member, after.channel)
        # ユーザーがチャンネルから退出した場合
        if before.channel and (before.channel != after.channel):
            await self.handle_user_leave(member, before.channel)

    async def handle_user_join(self, member, channel):
        guild = channel.guild
        voice_channel_id = str(channel.id)
        text_channel_id = self.private_channels.get(voice_channel_id)

        if text_channel_id:
            # テキストチャンネルが既に存在する場合
            private_channel = guild.get_channel(int(text_channel_id))
            if not private_channel:
                # テキストチャンネルが削除されている場合は新たに作成
                private_channel = await self.create_private_text_channel(guild, channel, member)
                self.private_channels[voice_channel_id] = str(private_channel.id)
                self.save_private_channels()
        else:
            # テキストチャンネルが存在しない場合は新たに作成
            private_channel = await self.create_private_text_channel(guild, channel, member)
            self.private_channels[voice_channel_id] = str(private_channel.id)
            self.save_private_channels()

        if private_channel:
            await private_channel.set_permissions(member, read_messages=True, send_messages=True)
            if not member.bot:
                await self.send_greeting(member, private_channel)

    async def create_private_text_channel(self, guild, voice_channel, member):
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True),
            member: discord.PermissionOverwrite(read_messages=True),
        }
        sanitized_name = self.sanitize_channel_name(voice_channel.name)
        private_channel = await guild.create_text_channel(
            name=sanitized_name,
            overwrites=overwrites,
            category=voice_channel.category
        )
        return private_channel

    async def handle_user_leave(self, member, channel):
        guild = channel.guild
        voice_channel_id = str(channel.id)
        text_channel_id = self.private_channels.get(voice_channel_id)

        if text_channel_id:
            private_channel = guild.get_channel(int(text_channel_id))
            if private_channel:
                if not member.bot:
                    await private_channel.set_permissions(member, overwrite=None)
                # ボイスチャンネルにメンバーがいない場合、メッセージを削除
                if len(channel.members) == 0:
                    await private_channel.purge()
            else:
                # テキストチャンネルが存在しない場合、データを削除
                self.private_channels.pop(voice_channel_id)
                self.save_private_channels()
                

    async def send_greeting(self, member, private_channel):
        member_id = str(member.id)
        guild_id = str(member.guild.id)
    
        # データベースから挨拶を取得
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT greeting FROM greetings WHERE guild_id=? AND member_id=?", (guild_id, member_id))
        greetings = [row[0] for row in c.fetchall()]
        conn.close()
    
        if greetings:
            greeting = random.choice(greetings).format(member=member)
        else:
            # ランダムな挨拶メッセージのリストを定義
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
            greeting = random.choice(random_greetings).format(member=member)

        await private_channel.send(greeting)

async def setup(bot):
    init_db()
    await bot.add_cog(VoiceChannelManagerCog(bot))

