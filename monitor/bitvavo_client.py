from python_bitvavo_api.bitvavo import Bitvavo
import os
from tkinter import *


class Bitvavo_client():
    def __init__(self):
        APIKEY=os.environ.get('APIKET')
        APISECRET = os.environ.get('SECKET')
        self.bitvavo = Bitvavo({
          'APIKEY': APIKEY,
          'APISECRET': APISECRET#,
          # 'RESTURL': 'https://api.bitvavo.com/v2',
          # 'WSURL': 'wss://ws.bitvavo.com/v2/',
          # 'ACCESSWINDOW': 10000,
          # 'DEBUGGING': False
        })