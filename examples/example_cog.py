import discord
import asyncio

from discord.ext import commands
from discord.ext.commands import Cog
from discoin import Discoin

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.discoin_client = Discoin(token="XXXXXXXXXXXXXXX", me="{YOUR CURRENCY CODE}", loop=bot.loop) # Initializes Discoin.py
        self.discoin_update_task = self.bot.loop.create_task(self.discoin_update()) # Creates a background task

    def cog_unload(self):
        self.discoin_update_task.cancel()

    async def discoin_update(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(1)

        while True:
            unhandled_transactions = await self.discoin_client.fetch_transactions() # Grabs a list of unhandled transactions from the API
            for transaction in unhandled_transactions:
                '''
                WARNING! At this point, you will have to add currency into the user's balance.

                `id` = The ID or receipt of the transaction (`str`)
                `currency_from` = The currency object that the transaction is coming from (`Currency`)
                `currency_to` = The currency object that the transaction is going to (`Currency`)
                `amount` = The original amount of the transaction (`float`)
                `user_id` = the id of the user who requested the transaction (`int`)
                `handled` = if the transaction has been marked as proccessed (`bool`)
                `timestamp` = The timestamp for when the transaction took place (`datetime.datetime`)
                `payout` = The amount calculated to its final destination (`float`)
                '''
                await self.discoin_client.handle_transaction(transaction.id) # Marking the transaction as handled, or processed

                user = self.bot.get_user(transaction.user_id)
                if user: await user.send(f"Your transfer from {transaction.currency_from.name} (`{transaction.currency_from.id}`) has just been processed! \n`${transaction.payout}` has been added to your account. \nHere is your receipt: `{transaction.id}`") # Notify the user that their transaction went through

            await asyncio.sleep(1*60*5) # Sleep every 5 minutes

    @commands.command()
    async def transfer(self, ctx, amount: float, to: int):
        '''Transfer currency to another bot that supports discoin'''
        to = to.upper() # Make the currency code uppercase
        transaction = await self.discoin_client.create_transaction(to, amount, ctx.author.id) # Make the transaction
        await ctx.send(f"Your transfer to {transaction.currency_to.name} (`{transaction.currency_to.id}`) is on its way! \nYou will be getting `{transaction.payout} {transaction.currency_to.id}` \nHere is your receipt: `{transaction.id}`")

def setup(bot):
    bot.add_cog(Economy(bot))