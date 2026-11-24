import discord
import asyncio

from discord.ext import commands, tasks
from discord.ext.commands import Cog
from discoin import Client

class Economy(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.discoin_client = Client(token="XXXXXXXXXXXXXXX", me="{YOUR CURRENCY CODE}") # Initializes Discoin
        self.discoin_update.start() # Starts the background task

    def cog_unload(self):
        self.discoin_update.cancel()
        self.bot.loop.create_task(self.discoin_client.close()) # cog_unload is synchronous, so the session close is scheduled on the loop

    @tasks.loop(minutes=5.0) # A background task that runs every 5 minutes
    async def discoin_update(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(1) # Avoids any errors about the bot not fully being ready.

        pending_transactions = await self.discoin_client.fetch_pending_transactions() # Grabs a list of pending transactions from the API
        for transaction in pending_transactions:
            """
            WARNING! At this point, you will have to add currency into the user's balance.

            `id` = The ID or receipt of the transaction (`str`)
            `currency_from` = The label of the currency that the transaction is coming from (`CurrencyLabel`)
            `currency_to` = The label of the currency that the transaction is going to (`CurrencyLabel`)
            `amount` = The original amount of the transaction (`float`)
            `user_id` = the id of the user who requested the transaction (`int`)
            `status` = The status of the transaction (`TransactionStatus`)
            `submitted_at` = When the transaction was submitted, in UTC (`datetime.datetime`)
            `handled_at` = When the transaction was handled, in UTC, or `None` (`datetime.datetime`)
            `payout` = The amount calculated to its final destination (`float`)
            """
            await self.discoin_client.mark_completed(transaction.id) # Marking the transaction as completed

            user = self.bot.get_user(transaction.user_id)
            if user: await user.send(f"Your transfer from {transaction.currency_from.name} (`{transaction.currency_from.abbreviation}`) has just been processed! \n`${transaction.payout}` has been added to your account. \nHere is your receipt: `{transaction.id}`") # Notify the user that their transaction went through

    @commands.group(invoke_without_command=True)
    async def transfer(self, ctx, amount: float, to: str):
        """Transfer currency to another bot that supports discoin"""
        to = to.upper() # Make the currency code uppercase
        """At this point, make sure the user has enough balance"""
        transaction = await self.discoin_client.create_transaction(to, amount, ctx.author.id) # Make the transaction
        """Remove {amount} from the user's balance"""
        await ctx.send(f"Your transfer to {transaction.currency_to.name} (`{transaction.currency_to.abbreviation}`) is on its way! \nYou will be getting `{transaction.payout} {transaction.currency_to.abbreviation}` \nHere is your receipt: `{transaction.id}`")

    @transfer.command()
    async def rates(self, ctx):
        discoin_rates = await self.discoin_client.fetch_currencies()
        msg = ""

        for rate in discoin_rates:
            msg += f"{rate.name} (`{rate.abbreviation}`) has a value of `{rate.value}`\n"

        await ctx.send(msg)

def setup(bot):
    bot.add_cog(Economy(bot))