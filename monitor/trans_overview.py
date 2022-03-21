import logging
import os
from python_bitvavo_api.bitvavo import Bitvavo

logger = logging.getLogger(__name__)
APIKEY = os.environ.get('BITVAVOAPIKEY')
APISECRET = os.environ.get('BITVAVOSECKEY')
print(APIKEY)
print(APISECRET)
bitvavo = Bitvavo({
    'APIKEY': APIKEY,
    'APISECRET': APISECRET  # ,
    # 'RESTURL': 'https://api.bitvavo.com/v2',
    # 'WSURL': 'wss://ws.bitvavo.com/v2/',
    # 'ACCESSWINDOW': 10000,
    # 'DEBUGGING': False
})

response = bitvavo.balance({})
print(response)
for item in response:
  print(item)
response = bitvavo.trades('BTC-EUR', {})
for item in response:
  print(item)