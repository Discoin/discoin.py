#######
Objects
#######

.. py:class:: discoin.Transaction()

    :param id: (``str``)The ID or receipt of the transaction 
    :param currency_from: (`Currency <#discoin.Currency>`_) The currency object that the transaction is coming from 
    :param currency_to: (`Currency <#discoin.Currency>`_) The currency object that the transaction is going to
    :param amount: (``float``) The original amount of the transaction 
    :param user_id: (``int``) the id of the user who requested the transaction 
    :param handled: (``bool``) if the transaction has been marked as proccessed 
    :param timestamp: (``datetime.datetime``) The timestamp for when the transaction took place 
    :param payout: (``float``) The amount calculated to its final destination 

.. py:class:: discoin.Currency()


    :param id: (``str``) The 3 letter id of the currency
    :param name: (``str``) The provided name of the currency
    :param value: (``float``) The value the currency has
    :param reserve: (``int``) The amount of currency trade left

.. py:class:: discoin.Bot()

    :param id: (``string``) The id of the bot. Can contain letters 
    :param currency: (`Currency <#discoin.Currency>`_) The currency of the bot 
