import discord
from discord.ext import commands
import random
import asyncio
import os
import sqlite3
from .Greetings import GreetingsCommandsCog

private_channels = {}
specific_member_greetings = {}

DB_PATH = os.path.join('data', 'greetings.db')

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
        self.initialize_private_channels()
        self.specific_member_greetings = {
            "1234567890": [
                "{member.mention} sample text",
            ],
        }

    def initialize_private_channels(self):
        for guild in self.bot.guilds:
            for category in guild.categories:
                for voice_channel in category.voice_channels:
                    text_channel_name = f"{voice_channel.name}"
                    text_channel = discord.utils.get(category.text_channels, name=text_channel_name)
                    if text_channel:
                        private_channels[voice_channel.id] = text_channel
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel != after.channel:
            if after.channel: 
                guild = after.channel.guild
                private_channel = private_channels.get(after.channel.id)

                if private_channel is None:
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(read_messages=False),
                        guild.me: discord.PermissionOverwrite(read_messages=True),
                        member: discord.PermissionOverwrite(read_messages=True),
                    }

                    text_channel_name = f"{after.channel.name}-private"
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

                if not member.bot:
                    await self.send_greeting(member, private_channel)

        if before.channel and before.channel != after.channel:
            private_channel = private_channels.get(before.channel.id)
            if private_channel:

                if not member.bot:
                    await private_channel.set_permissions(member, read_messages=None)

                if len(before.channel.members) == 0:
                    while True:
                        deleted_messages = await private_channel.purge(limit=20)
                        await asyncio.sleep(1)
                        if len(deleted_messages) < 20:
                            break

    async def send_greeting(self, member, private_channel):
        member_id = str(member.id)

        if member_id in self.specific_member_greetings:
            greetings = self.specific_member_greetings[member_id]
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