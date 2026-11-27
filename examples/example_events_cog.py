# This example needs discord.py 2.x
import discord

from discord.ext import commands, tasks
from discoin import Client, EventStatus, InternalServerError, WebTimeoutError

# The event feed calls the `on_...` methods of this class, named after the event: `transaction.created` calls `on_transaction_created`
class DiscoinClient(Client):
    def __init__(self, bot):
        # Initializes Discoin
        super().__init__(token="XXXXXXXXXXXXXXX", me="{YOUR CURRENCY CODE}")
        self.bot = bot

    async def on_transaction_created(self, event):
        """
        Called when a transaction is sent to your currency.
        Only the bot that runs the currency a transaction goes to gets events, the sending bot gets none.
        What it returns tells the feed what to do with the event, see `EventStatus`.

        `event.id` = The ID of the event (`int`)
        `event.event` = The name of the event, here `"transaction.created"` (`str`)
        `event.attempt` = How many times the API has sent the event, this time included. Above 1, an earlier try may already have paid the user (`int`)
        `event.test` = If the event was sent by the Test button of the bot owner page (`bool`)
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

        if event.test:
            # A test event pays nobody. The feed marks its transaction as completed, which passes the test of the bot owner page
            return EventStatus.COMPLETED

        # WARNING! At this point, you will have to add `transaction.payout` into the user's balance.
        # The API sends an event again when an earlier try was not reported handled, so `event.attempt` can be above 1 here.
        # Keeping the IDs of the transactions you paid is what stops a second payout.
        #
        # When your bot can't pay right now, `return EventStatus.UNHANDLED` here and the API sends the event again after a wait.

        try:
            # `get_user` reads the cache, which is empty until the bot is ready, and the feed starts in `cog_load`, before that
            user = await self.bot.fetch_user(transaction.user_id)
            # Notify the user that their transaction went through
            await user.send(f"Your transfer has just been processed! \n`${transaction.payout}` has been added to your account. \nHere is your receipt: `{transaction.id}`")
        except discord.HTTPException as error:
            # A user with closed DMs makes `send` raise, and a handler that raises has its event sent again
            print(f"Could not notify user {transaction.user_id} of transaction {transaction.id}: {error}")

        # The feed marks the transaction as completed, then reports the event handled. `EventStatus.REFUNDED` marks it as refunded instead
        return EventStatus.COMPLETED

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

        # The feed reports the event handled and marks nothing
        return EventStatus.HANDLED

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

        return EventStatus.HANDLED

    async def on_error(self, error, event):
        """
        Called with an error of the event feed that did not stop it: a handler that raised or returned no `EventStatus`,
        a mark that failed, a report the API refused, or an event that could not be parsed.
        Without this method, the library logs the error with the `discoin.client` logger.

        `error` = The error (`Exception`)
        `event` = The event the error is about, or `None` if it could not be parsed (`TransactionEvent`)
        """
        print(f"The Discoin event feed failed on {event}: {error!r}")

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Initializes Discoin with the event handlers above
        self.discoin_client = DiscoinClient(bot)

        # The task retries these with a growing wait instead of stopping
        self.discoin_undone_update.add_exception_type(InternalServerError, WebTimeoutError)

    async def cog_load(self):
        # Starts the event feed. It returns at once and the feed runs in the background
        await self.discoin_client.start()
        # Starts the background task for undone transactions
        self.discoin_undone_update.start()

    async def cog_unload(self):
        self.discoin_undone_update.cancel()
        # Closes the session and stops the event feed
        await self.discoin_client.close()

    # A background task that runs every 5 minutes
    @tasks.loop(minutes=5.0)
    async def discoin_undone_update(self):
        # Grabs up to 50 refunded, cancelled and reversed transactions your bot has not marked handled, the rest come on a later run
        undone_transactions = await self.discoin_client.fetch_undone_transactions()
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

            # Takes the transaction off the list. Until then, it is listed on every call
            await self.discoin_client.mark_handled(transaction.id)

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

    @transfer.command()
    async def status(self, ctx):
        """Show if the event feed is running, and the error that stopped it"""
        if self.discoin_client.events_running:
            await ctx.send("The Discoin event feed is running")

            return

        # A webhook URL on the bot (a 409), another 4** on the claim, or a claim or report that still fails after `max_retries` retries stops the feed. A handler that raises does not
        error = self.discoin_client.events_error
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

        # Clears `events_error`. The API sends the events that were not reported again, once their lease and wait are over
        await self.discoin_client.start()
        await ctx.send("The Discoin event feed was started again")

async def setup(bot):
    await bot.add_cog(Economy(bot))
