# This example needs discord.py 2.x
import discord

from discord.ext import commands, tasks
from discoin import BadRequest, Client, InternalServerError, WebTimeoutError

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.discoin_client = Client(token="XXXXXXXXXXXXXXX", me="{YOUR CURRENCY CODE}") # Initializes Discoin
        self.discoin_update.add_exception_type(InternalServerError, WebTimeoutError) # The task retries these with a growing wait instead of stopping

    async def cog_load(self):
        self.discoin_update.start() # Starts the background task

    async def cog_unload(self):
        self.discoin_update.cancel()
        await self.discoin_client.close() # Closes the session

    @tasks.loop(minutes=5.0) # A background task that runs every 5 minutes
    async def discoin_update(self):
        pending_transactions = await self.discoin_client.fetch_pending_transactions() # Grabs a list of pending transactions from the API
        for transaction in pending_transactions:
            await self.complete_transaction(transaction)

    async def complete_transaction(self, transaction):
        """
        Pays out one pending transaction sent to your currency.

        `id` = The ID or receipt of the transaction (`str`)
        `currency_from_id` = The UUID of the currency that the transaction is coming from (`str`)
        `currency_to_id` = The UUID of the currency that the transaction is going to (`str`)
        `currency_from` = The label of the currency that the transaction is coming from (`CurrencyLabel`)
        `currency_to` = The label of the currency that the transaction is going to (`CurrencyLabel`)
        `amount` = The original amount of the transaction (`float`)
        `user_id` = the id of the user who requested the transaction (`int`)
        `status` = The status of the transaction (`TransactionStatus`)
        `submitted_at` = When the transaction was submitted, in UTC (`datetime.datetime`)
        `handled_at` = When the transaction was handled, in UTC, or `None` (`datetime.datetime`)
        `payout` = The amount calculated to its final destination (`float`)
        """
        # WARNING! At this point, you will have to add `transaction.payout` into the user's balance.

        try:
            await self.discoin_client.mark_completed(transaction.id) # Marking the transaction as completed
        except BadRequest as error:
            if error.status != 400: raise # Any other error raises, which stops the task

            return # A 400 means the transaction is no longer `Pending`, for example because it was cancelled after the list was fetched

        try:
            user = await self.bot.fetch_user(transaction.user_id) # `get_user` reads the cache, which is empty until the bot is ready, and the task starts in `cog_load`, before that
            await user.send(f"Your transfer from {transaction.currency_from.name} (`{transaction.currency_from.abbreviation}`) has just been processed! \n`${transaction.payout}` has been added to your account. \nHere is your receipt: `{transaction.id}`") # Notify the user that their transaction went through
        except discord.HTTPException as error:
            print(f"Could not notify user {transaction.user_id} of transaction {transaction.id}: {error}") # A user with closed DMs makes `send` raise, which would stop the task

    @commands.group(invoke_without_command=True)
    async def transfer(self, ctx, amount: float, to: str):
        """Transfer currency to another bot that supports discoin"""
        # At this point, make sure the user has enough balance
        transaction = await self.discoin_client.create_transaction(to, amount, ctx.author.id) # Make the transaction. The currency code can be in any case
        # Remove {amount} from the user's balance
        await ctx.send(f"Your transfer to {transaction.currency_to.name} (`{transaction.currency_to.abbreviation}`) is on its way! \nYou will be getting `{transaction.payout} {transaction.currency_to.abbreviation}` \nHere is your receipt: `{transaction.id}`")

    @transfer.command()
    async def rates(self, ctx):
        """Show the value of every Discoin currency"""
        discoin_rates = await self.discoin_client.fetch_currencies()
        msg = ""

        for rate in discoin_rates:
            msg += f"{rate.name} (`{rate.abbreviation}`) has a value of `{rate.value}`\n"

        await ctx.send(msg)

async def setup(bot):
    await bot.add_cog(Economy(bot))
