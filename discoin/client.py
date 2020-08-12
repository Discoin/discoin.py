import aiohttp
import asyncio

from .classes import Transaction, Currency, Bot
from .utils import api_request


class Client():
    '''
    Main used class for discoin
    '''

    def __init__(self, token: str, me: str, loop=None):
        '''
        Init client.

        :param token: (``str``) Your api token for discoin 
        :param me: (``me``) Your 3 letter currency code
        :param loop: (``asyncio.EventLoop``) (Optional) Asyncio event loop
        '''

        # Needed vars
        self._headers = {"Authorization": f"Bearer {token}"}
        self._me = me

        # Event loop Init
        self._loop = loop or asyncio.get_event_loop()

        # aiohttp Session Init
        self._session = aiohttp.ClientSession(loop=self._loop)

    async def fetch_transactions(self, **kwargs):
        '''
        Get a list of transactions. It is recommended to run this every 5 minutes in a loop

        :param transaction_id: (``str``) (Optional) Filter results by a transaction id.
        :param amount: (``int``) (Optional) Filter results by the original amount
        :param user_id: (``int``) (Optional) Filter by the user's id
        :param handled: (``bool``) (Optional) Defaults to `False`. Will filter results to see if they are handled or not. `None` will fetch all 
        :param payout: (``int``) (Optional) Filter by the final amount 
        :param code: (``str``) (Optional) 3 letter currency code that you want to search for. ``None`` will just fetch all results. Default is `me`. 
        :param code_from: (``str``) (Optional) 3 letter currency code that the transaction is coming from
        :param advanced_filter: (``str``) (Optional) Optionally, you can create your own filter. Not recommended 

        :rtype: [discoin.Transaction]

        :raises discoin.InternalServerError: If the discoin API returns a 5**
        :raises discoin.BadRequest: If the discoin API returns a 4**
        :raises discoin.WebTimeoutError: If the API times out
        '''

        transaction_id = kwargs.pop("transaction_id", None)
        amount = kwargs.pop("amount", None)
        user_id = kwargs.pop("user_id", None)
        handled = kwargs.pop("handled", False)
        payout = kwargs.pop("payout", None)
        code = kwargs.pop("code", self._me)
        code_from = kwargs.pop("code_from", None)
        advanced_filter = kwargs.pop("advanced_filter", None)

        if advanced_filter:
            transaction_filter = advanced_filter
        else:
            transaction_filter = f"""{f"filter=id||eq||{transaction_id}&" if transaction_id != None else ""}{f"filter=amount||eq||{amount}&" if amount != None else ""}{f"filter=user||eq||{user_id}&" if user_id != None else ""}{f"filter=handled||eq||{str(handled).lower()}&" if handled != None else ""}{f"filter=payout||eq||{payout}&" if payout != None else ""}{f"filter=to.id||eq||{code}&" if code != None else ""}{f"filter=from.id||eq||{code_from}&" if code_from != None else ""}"""
        url_path = f"/transactions?{transaction_filter}"

        api_response = await api_request(self._session, "GET", url_path)
        api_response_json = await api_response.json()
        transactions = []

        for transaction_obj in api_response_json:
            transactions.append(Transaction(transaction_obj))
        
        return transactions

    async def create_transaction(self, code_to: str, amount: float, user_id: int, code_from: str = None):
        '''
        Create a transaction

        :param code_to: (``str``) The 3 letter code to send a transaction to. 
        :param amount: (``float``) The amount of currency in original format. 
        :param user_id: (``int``) The user_id from the user who requested the transaction
        :param code_from: (``str``) (Optional) The 3 letter code to send a transaction from. 

        :rtype: discoin.Transaction

        :raises discoin.InternalServerError: If the discoin API returns a 5**
        :raises discoin.BadRequest: If the discoin API returns a 4**
        :raises discoin.WebTimeoutError: If the API times out
        '''

        code_from = self._me if code_from is None else code_from.upper()
        code_to = code_to.upper()
        json = {
            "amount": amount,
            "from": code_from,
            "to": code_to,
            "user": str(user_id),
        }

        api_response = await api_request(self._session, "POST", "/transactions", headers=self._headers, json=json)
        api_response_json = await api_response.json()

        return Transaction(api_response_json)

    async def handle_transaction(self, transaction_id, handled: bool=True):
        '''
        Handling a transaction just marks it as handled, or processed.

        :param code_to: (``str``) The 3 letter code to send a transaction to. 
        :param amount: (``float``) The amount of currency in original format. 
        :param user_id: (``int``) The user_id from the user who requested the transaction

        :rtype: discoin.Transaction

        :param id: (``str``) The id of the transaction you want to handle
        :handled: (``bool``) (Optional) Defaults to `True`. If you want to mark a transaction as unhandled, then set this to `False`
        '''

        json = {
            "handled": handled,
        }

        api_response = await api_request(self._session, "PATCH", f"/transactions/{transaction_id}", headers=self._headers, json=json)
        api_response_json = await api_response.json()

        return Transaction(api_response_json)

    async def fetch_currencies(self):
        '''
        This allows you to fetch the available currencies from the API

        :rtype: [discoin.Currency]

        :raises discoin.InternalServerError: If the discoin API returns a 5**
        :raises discoin.WebTimeoutError: If the API times out
        '''

        api_response = await api_request(self._session, "GET", f"/currencies")
        api_response_json = await api_response.json()
        currencies = []

        for currency_obj in api_response_json:
            currencies.append(Currency(currency_obj))
        
        return currencies
    
    async def fetch_bots(self):
        '''
        Fetch a list of bots compatible with discoin.

        :rtype: [discoin.Bot]

        :raises discoin.InternalServerError: If the discoin API returns a 5**
        :raises discoin.WebTimeoutError: If the API times out
        '''

        api_response = await api_request(self._session, "GET", f"/bots")
        api_response_json = await api_response.json()
        bots = []

        for bot_obj in api_response_json:
            bots.append(Bot(bot_obj))
        
        return bots