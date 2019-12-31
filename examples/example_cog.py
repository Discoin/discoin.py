import discord
import asyncio

from discord.ext import commands, tasks
from discord.ext.commands import Cog
from discoin import Discoin

class Economy(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.discoin_client = Discoin(token="XXXXXXXXXXXXXXX", me="{YOUR CURRENCY CODE}", loop=bot.loop) # Initializes Discoin
        self.discoin_update.start() # Starts the background task

    def cog_unload(self):
        self.discoin_update.cancel()

    @tasks.loop(minutes=5.0) # A background task that runs every 5 minutes
    async def discoin_update(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(1) # Avoids any errors about the bot not fully being ready.

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

    @commands.group(invoke_without_command=True)
    async def transfer(self, ctx, amount: float, to: int):
        '''Transfer currency to another bot that supports discoin'''
        to = to.upper() # Make the currency code uppercase
        '''At this point, make sure the user has enough balance'''
        transaction = await self.discoin_client.create_transaction(to, amount, ctx.author.id) # Make the transaction
        '''Remove {amount} from the user's balance'''
        await ctx.send(f"Your transfer to {transaction.currency_to.name} (`{transaction.currency_to.id}`) is on its way! \nYou will be getting `{transaction.payout} {transaction.currency_to.id}` \nHere is your receipt: `{transaction.id}`")
    
    @transfer.command()
    async def reverse(self, ctx, transaction_id):
        '''Reverse a transaction'''
        transaction = await self.discoin_client.fetch_transactions(advanced_filter=f"filter=id||eq||{transaction_id}")
        transaction = transaction[0]

        new_transaction = await self.discoin_client.create_transaction(transaction.currency_from.id, transaction.payout, ctx.author.id)
        '''Add {transaction.payout} from your user's balance'''
        await ctx.send(f"Your refund to {new_transaction.currency_to.name} (`{new_transaction.currency_to.id}`)is on its way! \nYou will be getting `{new_transaction.payout} {new_transaction.currency_to.id}` \n\nHere is your receipt: `{new_transaction.id}`")

    @transfer.command()
    async def rates(self, ctx):
        discoin_rates = self.discoin_client.fetch_currencies()
        msg = ""
        for rate in discoin_rates:
            msg += f"{rate.name} (`{rate.id}`) has a value of `{rate.value}`"
        await ctx.send(msg)

def setup(bot):
    bot.add_cog(Economy(bot))