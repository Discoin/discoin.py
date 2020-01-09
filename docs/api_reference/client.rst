######
Client
######

.. py:class:: discoin.Discoin(token, me, loop=None)

    Main used class for discoin

    :param token: (``str``) Your api token for discoin 
    :param me: (``me``) Your 3 letter currency code
    :param loop: (``asyncio.EventLoop``) (Optional) Asyncio event loop

    .. _fetch_transactions:
    .. py:function:: fetch_transactions(**kwargs)

        Get a list of transactions. It is recommended to run this every 5 minutes in a loop

        :param transaction_id: (``str``) (Optional) Filter results by a transaction id.
        :param amount: (``int``) (Optional) Filter results by the original amount
        :param user_id: (``int``) (Optional) Filter by the user's id
        :param handled: (``bool``) (Optional) Defaults to `False`. Will filter results to see if they are handled or not. `None` will fetch all 
        :param payout: (``int``) (Optional) Filter by the final amount 
        :param code: (``string``) (Optional) 3 letter currency code that you want to search for. `None` will just fetch all results. Default is `me`. 
        :param code_from: (``string``) (Optional) 3 letter currency code that the transaction is coming from
        :param advanced_filter: (``string``) (Optional) Optionally, you can create your own filter. Not recommended 

        :returns: `discoin.Transaction <objects.html#discoin.Transaction>`_

        :raises discoin.InternalServerError: If the discoin API returns a 5**
        :raises discoin.BadRequest: If the discoin API returns a 4**
        :raises discoin.WebTimeoutError: If the API times out

    .. _create_transaction:
    .. py:function:: create_transaction(code_to, amount, user_id)

        Create a transaction

        :param code_to: (``str``) The 3 letter code to send a transaction to. 
        :param amount: (``float``) The amount of currency in original format. 
        :param user_id: (``int``) The user_id from the user who requested the transaction

        :returns: `discoin.Transaction <objects.html#discoin.Transaction>`_

        :raises discoin.InternalServerError: If the discoin API returns a 5**
        :raises discoin.BadRequest: If the discoin API returns a 4**
        :raises discoin.WebTimeoutError: If the API times out
    
    .. _handle_transaction:
    .. py:function:: handle_transaction(transaction_id, handled=True)

        Handling a transaction just marks it as handled, or processed.

        :param id: (``str``) The id of the transaction you want to handle
        :handled: = (``bool``) (Optional) Defaults to `True`. If you want to mark a transaction as unhandled, then set this to `False`

        :returns: `discoin.Transaction <objects.html#discoin.Transaction>`_

        :raises discoin.InternalServerError: If the discoin API returns a 5**
        :raises discoin.BadRequest: If the discoin API returns a 4**
        :raises discoin.WebTimeoutError: If the API times out
    

    .. _fetch_currencies:
    .. py:function:: fetch_currencies()
        This allows you to fetch the available currencies from the API

        :returns: `discoin.Currency <objects.html#discoin.Currency>`_

        :raises discoin.InternalServerError: If the discoin API returns a 5**
        :raises discoin.WebTimeoutError: If the API times out
    
    .. _fetch_bots:
    .. py:function:: fetch_bots()

        Fetch a list of bots compatible with discoin.

        :returns: `discoin.Bot <objects.html#discoin.Bot>`_

        :raises discoin.InternalServerError: If the discoin API returns a 5**
        :raises discoin.WebTimeoutError: If the API times out
