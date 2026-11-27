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
   discoin.Client.on_error
   discoin.Client.claim_events
   discoin.Client.report_event
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
   discoin.EventStatus
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