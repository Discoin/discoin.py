from discord.ext.commands import Cog
from discoin import Client, EventType

class Economy(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.discoin_client = Client(token="XXXXXXXXXXXXXXX", me="{YOUR CURRENCY CODE}") # Initializes Discoin

        @self.discoin_client.listen(EventType.CREATED) # Registers the handler for `transaction.created` events
        async def on_transaction_created(event):
            """
            `event.id` = The ID of the event (`int`)
            `event.event` = The name of the event (`str`)
            `event.triggered_by` = Who caused the event, or `None` (`EventTrigger`)
            `event.transaction` = The transaction as it was when the event was written (`FeedTransaction`)

            `id` = The ID or receipt of the transaction (`str`)
            `currency_from_id` = The UUID of the currency that the transaction is coming from (`str`)
            `currency_to_id` = The UUID of the currency that the transaction is going to (`str`)
            `amount` = The original amount of the transaction (`float`)
            `user_id` = the id of the user who requested the transaction (`int`)
            `status` = The status of the transaction (`TransactionStatus`)
            `submitted_at` = When the transaction was submitted, in UTC (`datetime.datetime`)
            `handled_at` = When the transaction was handled, in UTC, or `None` (`datetime.datetime`)
            `payout` = The amount calculated to its final destination (`float`)
            """

        self.bot.loop.create_task(self.start_discoin_events()) # __init__ is synchronous, so the start is scheduled on the loop

    def cog_unload(self):
        self.bot.loop.create_task(self.discoin_client.close()) # cog_unload is synchronous, so the close is scheduled on the loop

    async def start_discoin_events(self):
        await self.bot.wait_until_ready()
        await self.discoin_client.start() # Starts the event feed, which runs in the background

def setup(bot):
    bot.add_cog(Economy(bot))
