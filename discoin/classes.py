import datetime

class Transaction():
    '''
    Transaction object

    :param id: (``str``) The ID or receipt of the transaction 
    :param currency_from: (``discoin.Currency``) The currency object that the transaction is coming from 
    :param currency_to: (``discoin.Currency``) The currency object that the transaction is going to
    :param amount: (``float``) The original amount of the transaction 
    :param user_id: (``int``) the id of the user who requested the transaction 
    :param handled: (``bool``) if the transaction has been marked as proccessed 
    :param timestamp: (``datetime.datetime``) The timestamp for when the transaction took place 
    :param payout: (``float``) The amount calculated to its final destination 
    '''

    def __init__(self, transaction_obj):
        self.id = transaction_obj['id']
        self.currency_from = Currency(transaction_obj['from'])
        self.currency_to = Currency(transaction_obj['to'])

        if transaction_obj['amount'] == None: # This is implemented due to a bug with discoin's API
            self.amount = 0.0
        else:
            self.amount = float(transaction_obj['amount']) # This is the amount from the original source

        self.user_id = int(transaction_obj['user'])
        self.handled = transaction_obj['handled']
        self.timestamp = datetime.datetime.strptime(transaction_obj['timestamp'], "%Y-%m-%dT%H:%M:%S.%fZ")
        
        if transaction_obj['payout'] == None: # This is implemented due to a bug with discoin's API
            self.payout = 0.0
        else:
            self.payout = float(transaction_obj['payout']) # This is the amount calculated to its final destination

    def __str__(self):
        return f"Transaction({self.id})"


class Currency():
    '''
    Currency Object
    
    :param id: (``str``) The 3 letter id of the currency
    :param name: (``str``) The provided name of the currency
    :param value: (``float``) The value the currency has
    :param reserve: (``int``) The amount of currency trade left
    '''

    def __init__(self, currency_obj):
        self.id = currency_obj['id']
        self.name = currency_obj['name']
        self.value = currency_obj.get('value')

        if currency_obj['reserve'] == None: # This is implemented due to a bug with discoin's API
            self.reserve = None
        else:
            self.reserve = float(currency_obj.get('reserve'))

    def __str__(self):
        return f"Currency({self.id})"


class Bot():
    '''
    Discoin Bot Object

    :param id: (``string``) The id of the bot. Can contain letters 
    :param currency: (``discoin.Currency``) The currency of the bot 
    '''
    def __init__(self, bot_obj):
        self.id = bot_obj['id']
        self.currency = Currency(bot_obj['currency'])

    def __str__(self):
        return f"Bot({self.id})"