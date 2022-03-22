import logging
import os
from python_bitvavo_api.bitvavo import Bitvavo

logger = logging.getLogger(__name__)
APIKEY = os.environ.get('BITVAVOAPIKEY')
APISECRET = os.environ.get('BITVAVOSECKEY')

bitvavo = Bitvavo({
    'APIKEY': APIKEY,
    'APISECRET': APISECRET  # ,
    # 'RESTURL': 'https://api.bitvavo.com/v2',
    # 'WSURL': 'wss://ws.bitvavo.com/v2/',
    # 'ACCESSWINDOW': 10000,
    # 'DEBUGGING': False
})

response = bitvavo.balance({})
for item in response:
    print(f"{item['symbol']}  \t{item['available']}")
    tradepair = item['symbol']+"-EUR"
    response = bitvavo.trades(tradepair, {})
    for item in response:
        print(f"{item['market']}, {item['side']}, {item['amount']}, {item['price']}")