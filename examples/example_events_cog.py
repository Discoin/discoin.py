# This example needs discord.py 2.x
import discord

from discord.ext import commands, tasks
from discoin import BadRequest, Client, InternalServerError, WebTimeoutError

class DiscoinClient(Client): # The event feed calls the `on_...` methods of this class, named after the event: `transaction.created` calls `on_transaction_created`
    def __init__(self, bot):
        super().__init__(token="XXXXXXXXXXXXXXX", me="{YOUR CURRENCY CODE}") # Initializes Discoin
        self.bot = bot

    async def on_transaction_created(self, event):
        """
        Called when a transaction is sent to your currency.
        Only the bot that runs the currency a transaction goes to gets events, the sending bot gets none.

        `event.id` = The ID of the event (`int`)
        `event.event` = The name of the event, here `"transaction.created"` (`str`)
        `event.triggered_by` = Who caused the event, or `None`. Only events caused by a block have it (`EventTrigger`)
        `event.transaction` = The transaction as it was when the event was written (`FeedTransaction`)

        `id` = The ID or receipt of the transaction (`str`)
        `currency_from_id` = The UUID of the currency that the transaction is coming from (`str`)
        `currency_to_id` = The UUID of the currency that the transaction is going to (`str`)
        `amount` = The original amount of the transaction (`float`)
        `user_id` = the id of the user who requested the transaction (`int`)
        `status` = The status of the transaction when the event was written (`TransactionStatus`)
        `submitted_at` = When the transaction was submitted, in UTC (`datetime.datetime`)
        `handled_at` = When the transaction was handled, in UTC, or `None` (`datetime.datetime`)
        `payout` = The amount calculated to its final destination (`float`)
        """
        transaction = event.transaction

        try:
            await self.mark_completed(transaction.id) # Marking the transaction as completed, before the balance, so that a transaction is only paid once
        except BadRequest as error:
            if error.status != 400: raise # Any other error raises, which stops the feed. See `events_error`

            return # A 400 means the transaction is no longer `Pending`. An event can be delivered more than once, and the owner can resend a transaction from the dashboard

        # WARNING! At this point, you will have to add `transaction.payout` into the user's balance.

        try:
            user = await self.bot.fetch_user(transaction.user_id) # `get_user` reads the cache, which is empty until the bot is ready, and the feed starts in `cog_load`, before that
            await user.send(f"Your transfer has just been processed! \n`${transaction.payout}` has been added to your account. \nHere is your receipt: `{transaction.id}`") # Notify the user that their transaction went through
        except discord.HTTPException as error:
            print(f"Could not notify user {transaction.user_id} of transaction {transaction.id}: {error}") # A user with closed DMs makes `send` raise, and a handler that raises stops the feed

    async def on_transaction_cancelled(self, event):
        """
        Called when a `Pending` transaction to your currency is cancelled.
        Your bot cannot cancel a transaction, and neither can the user who sent it. The API cancels it when an admin deactivates
        or removes a currency, when an admin removes a bot, or when the owner of a bot or an admin blocks the user.

        `event.triggered_by` = Who blocked the user, or `None` when the cancel was not caused by a block (`EventTrigger`)
        `event.triggered_by.kind` = `"owner"` or `"admins"`, see `TriggerKind` (`str`)
        `event.triggered_by.bot_id` = The UUID of the bot whose owner blocked the user, or `None` (`str`)
        `event.transaction` = The transaction as it was when the event was written, with the status `Cancelled` (`FeedTransaction`)
        """
        transaction = event.transaction

        # At this point, the transaction can no longer be marked as completed or refunded.
        # What your bot does about it is your choice.

        print(f"Transaction {transaction.id} of user {transaction.user_id} was cancelled")

    async def on_transaction_reversed(self, event):
        """
        Called when a `Completed` transaction to your currency is reversed.
        Your bot cannot reverse a transaction, and neither can the user who sent it. The API reverses it only when
        the owner of a bot or an admin blocks the user and chooses to reverse their past transactions.

        `event.triggered_by` = Who blocked the user, or `None` if the API sent none (`EventTrigger`)
        `event.triggered_by.kind` = `"owner"` or `"admins"`, see `TriggerKind` (`str`)
        `event.triggered_by.bot_id` = The UUID of the bot whose owner blocked the user, or `None` (`str`)
        `event.transaction` = The transaction as it was when the event was written, with the status `Reversed` (`FeedTransaction`)
        """
        transaction = event.transaction

        # At this point, the transaction was completed before, so in this example the user already got `transaction.payout`.
        # What your bot does about it is your choice.

        print(f"Transaction {transaction.id} of user {transaction.user_id} was reversed")

    async def on_transaction_test(self, event):
        """
        Called when the Test button of the bot owner page is pressed. Its transaction exists nowhere else,
        so `mark_completed` and `mark_refunded` on it raise a 404.
        """
        print(f"Test event {event.id} received, the event feed works")

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.discoin_client = DiscoinClient(bot) # Initializes Discoin with the event handlers above

        self.discoin_undone_update.add_exception_type(InternalServerError, WebTimeoutError) # The task retries these with a growing wait instead of stopping

    async def cog_load(self):
        await self.discoin_client.start() # Starts the event feed. It returns at once and the feed runs in the background
        self.discoin_undone_update.start() # Starts the background task for undone transactions

    async def cog_unload(self):
        self.discoin_undone_update.cancel()
        await self.discoin_client.close() # Closes the session and stops the event feed

    @tasks.loop(minutes=5.0) # A background task that runs every 5 minutes
    async def discoin_undone_update(self):
        undone_transactions = await self.discoin_client.fetch_undone_transactions() # Grabs up to 50 refunded, cancelled and reversed transactions your bot has not marked handled, the rest come on a later run
        for transaction in undone_transactions:
            # This list has the transactions your bot sent and those it received. It is the only place where
            # a sending bot sees that a transaction it sent was refunded, cancelled or reversed.
            # A refund is only listed for the bot that sent the transaction, since the receiving bot is the one that refunded it.
            # A cancel or reversal is listed for both bots, also when your bot already got it as an event,
            # and it is listed after its event was deleted, 24 hours after it was written.
            #
            # `id` = The ID or receipt of the transaction (`str`)
            # `currency_from` = The label of the currency that the transaction is coming from (`CurrencyLabel`)
            # `currency_to` = The label of the currency that the transaction is going to (`CurrencyLabel`)
            # `amount` = The original amount of the transaction (`float`)
            # `user_id` = the id of the user who requested the transaction (`int`)
            # `status` = `Refunded`, `Cancelled` or `Reversed` (`TransactionStatus`)
            # `submitted_at` = When the transaction was submitted, in UTC (`datetime.datetime`)
            # `handled_at` = When the transaction was undone, in UTC (`datetime.datetime`)
            # `payout` = The amount calculated to its final destination (`float`)
            #
            # At this point, what your bot does about the transaction is your choice.
            await self.discoin_client.mark_handled(transaction.id) # Takes the transaction off the list. Until then, it is listed on every call

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

    @transfer.command()
    async def status(self, ctx):
        """Show if the event feed is running, and the error that stopped it"""
        if self.discoin_client.events_running:
            await ctx.send("The Discoin event feed is running")

            return

        error = self.discoin_client.events_error # A handler that raises, an event that cannot be parsed, a 4** other than a 429, a 429 without a `Retry-After` header in whole seconds, or a webhook URL on the bot (a 409) stops the feed
        if error is None:
            await ctx.send("The Discoin event feed is stopped")

            return

        await ctx.send(f"The Discoin event feed was stopped by: `{error}`")

    @transfer.command()
    async def restart(self, ctx):
        """Start the event feed again after it stopped"""
        if self.discoin_client.events_running:
            await ctx.send("The Discoin event feed is already running")

            return

        await self.discoin_client.start() # Clears `events_error`. The API sends the events that were not acknowledged again
        await ctx.send("The Discoin event feed was started again")

async def setup(bot):
    await bot.add_cog(Economy(bot))
