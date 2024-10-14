import discord
from discord import app_commands
from discord.ext import commands

class HelpCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name='help',
        description='このボットの使い方を表示します。'
    )
    async def help_command(self, ctx: discord.Interaction):
        embed = discord.Embed(title="ボットの使い方", color=discord.Color.blue())

        embed.add_field(name="ボイスチャンネルへの参加/退出", value="ボイスチャンネルに参加すると、専用のプライベートテキストチャンネルが作成されます。ボイスチャンネルから退出すると、そのテキストチャンネルへのアクセスが解除されます。全員が退出するとプライベートチャンネル内のチャットは削除されます。", inline=False)
        embed.add_field(name="入場時の挨拶", value="ユーザーがボイスチャンネルに入ると、ボットが設定された挨拶メッセージを送信します。個別のメンバーに対してカスタム挨拶メッセージを設定することができます。", inline=False)
        embed.add_field(name="/add_greeting <member> <greeting>", value="特定のメンバーに対する挨拶を追加します。メンバーは@メンションまたはユーザーIDで指定できます。例: `/add_greeting @username こんにちは、ようこそ！`", inline=False)
        embed.add_field(name="/remove_greeting <member> <index>", value="特定のメンバーに対する挨拶を削除します。\nindexに削除する番号をlistから調べて入力してください。", inline=False)
        embed.add_field(name="/list_greetings <member>", value="特定のメンバーに対する挨拶のリストを表示します。", inline=False)

        await ctx.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(HelpCommands(bot))