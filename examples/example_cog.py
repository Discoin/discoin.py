# This example needs discord.py 2.x
import discord

from discord.ext import commands, tasks
from discoin import BadRequest, Client, InternalServerError, WebTimeoutError

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Initializes Discoin
        self.discoin_client = Client(token="XXXXXXXXXXXXXXX", me="{YOUR CURRENCY CODE}")
        # The task retries these with a growing wait instead of stopping
        self.discoin_update.add_exception_type(InternalServerError, WebTimeoutError)

    async def cog_load(self):
        # Starts the background task
        self.discoin_update.start()

    async def cog_unload(self):
        self.discoin_update.cancel()
        # Closes the session
        await self.discoin_client.close()

    # A background task that runs every 5 minutes
    @tasks.loop(minutes=5.0)
    async def discoin_update(self):
        # Grabs a list of pending transactions from the API
        pending_transactions = await self.discoin_client.fetch_pending_transactions()
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
            # Marking the transaction as completed
            await self.discoin_client.mark_completed(transaction.id)
        except BadRequest as error:
            if error.status != 400:
                # Any other error raises, which stops the task
                raise

            # A 400 means the transaction is no longer `Pending`, for example because it was cancelled after the list was fetched
            return

        try:
            # `get_user` reads the cache, which is empty until the bot is ready, and the task starts in `cog_load`, before that
            user = await self.bot.fetch_user(transaction.user_id)
            # Notify the user that their transaction went through
            await user.send(f"Your transfer from {transaction.currency_from.name} (`{transaction.currency_from.abbreviation}`) has just been processed! \n`${transaction.payout}` has been added to your account. \nHere is your receipt: `{transaction.id}`")
        except discord.HTTPException as error:
            # A user with closed DMs makes `send` raise, which would stop the task
            print(f"Could not notify user {transaction.user_id} of transaction {transaction.id}: {error}")

    @commands.group(invoke_without_command=True)
    async def transfer(self, ctx, amount: float, to: str):
        """Transfer currency to another bot that supports discoin"""
        # At this point, make sure the user has enough balance

        # Make the transaction. The currency code can be in any case
        transaction = await self.discoin_client.create_transaction(to, amount, ctx.author.id)

        # At this point, remove {amount} from the user's balance

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
