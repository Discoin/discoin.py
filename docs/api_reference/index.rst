#############
API Reference
#############

|

Client
------

.. autosummary::
   :toctree: stubs
   
   discoin.Client
   discoin.Client.fetch_pending_transactions
   discoin.Client.create_transaction
   discoin.Client.fetch_quote
   discoin.Client.mark_completed
   discoin.Client.mark_refunded
   discoin.Client.fetch_currencies
   discoin.Client.fetch_undone_transactions
   discoin.Client.mark_handled
   discoin.Client.start
   discoin.Client.listen
   discoin.Client.add_listener
   discoin.Client.remove_listener
   discoin.Client.fetch_events
   discoin.Client.acknowledge_events
   discoin.Client.close

|

Classes
-------

.. autosummary::
   :toctree: stubs
   
   discoin.Transaction
   discoin.TransactionStatus
   discoin.Currency
   discoin.CurrencyLabel
   discoin.TransactionEvent
   discoin.FeedTransaction
   discoin.EventTrigger
   discoin.EventType
   discoin.TriggerKind

|

Errors
------

.. autosummary::
   :toctree: stubs

   discoin.InternalServerError
   discoin.BadRequest
   discoin.RateLimited
   discoin.InvalidMethod
   discoin.WebTimeoutError