import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import os

DB_PATH = os.path.join('DATA', 'greetings.db')

class GreetingsCommandsCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(
        name='add_greeting',
        description='特定のメンバーに対する挨拶を追加します'
    )
    async def add_greeting(self, ctx: discord.Interaction, member: discord.Member, greeting: str):
        guild_id = str(ctx.guild_id)
        member_id = str(member.id)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO greetings VALUES (?, ?, ?)", (guild_id, member_id, greeting))
        conn.commit()
        conn.close()
        embed = discord.Embed(
            title="挨拶を追加しました",
            description=f"{member.mention}: {greeting}",
            color=0x00FF00
        )
        await ctx.response.send_message(embed=embed, ephemeral=True)  # メッセージを実行者にのみ表示

    @app_commands.command(
        name='remove_greeting',
        description='特定のメンバーに対する挨拶を削除します'
    )
    async def remove_greeting(self, ctx: discord.Interaction, member: discord.Member, index: int):
        guild_id = str(ctx.guild_id)
        member_id = str(member.id)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT greeting FROM greetings WHERE guild_id=? AND member_id=?", (guild_id, member_id))
        greetings = c.fetchall()
        if 0 <= index < len(greetings):
            removed_greeting = greetings.pop(index)
            c.execute("DELETE FROM greetings WHERE guild_id=? AND member_id=? AND greeting=?", (guild_id, member_id, removed_greeting[0]))
            conn.commit()
            embed = discord.Embed(
                title="削除された挨拶",
                description=f"{member.mention}: {removed_greeting[0]}",
                color=0xFF0000
            )
            await ctx.response.send_message(embed=embed, ephemeral=True)  # メッセージを実行者にのみ表示
        else:
            embed = discord.Embed(
                title="エラー",
                description="無効なインデックスです。`/list_greetings` を使って正しいインデックスを確認してください。",
                color=0xFF0000
            )
            await ctx.response.send_message(embed=embed, ephemeral=True)  # メッセージを実行者にのみ表示
        conn.close()
        
    @app_commands.command(
        name='list_greetings',
        description='特定のメンバーに対する挨拶のリストを表示します'
    )
    async def list_greetings(self, ctx: discord.Interaction, member: discord.Member):
        guild_id = str(ctx.guild_id)
        member_id = str(member.id)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT greeting FROM greetings WHERE guild_id=? AND member_id=?", (guild_id, member_id))
        greetings = c.fetchall()
        conn.close()
        if not greetings:
            embed = discord.Embed(
                title="エラー",
                description="このメンバーには追加された挨拶がありません。",
                color=0xFF0000
            )
            await ctx.response.send_message(embed=embed, ephemeral=True)  # メッセージを実行者にのみ表示
            return
        
        greetings_list = "\n".join(f"{idx}: {greeting[0]}" for idx, greeting in enumerate(greetings))
        embed = discord.Embed(
            title=f"{member.name} に対する挨拶のリスト",
            description=greetings_list,
            color=0x00FF00
        )
        await ctx.response.send_message(embed=embed, ephemeral=True)  # メッセージを実行者にのみ表示
        
async def setup(bot):
    await bot.add_cog(GreetingsCommandsCog(bot))
