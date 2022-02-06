import ccxt
import logging
import os
import time
from core.markets.coin import Coin

logger = logging.getLogger(__name__)


class Monitor:
    def __init__(self):
        self.api_key = None
        self.secret_key = None
        exchange = getattr(ccxt, 'bitvavo')
        self.get_exchange_login()
        self.exchange = exchange({'apiKey': self.api_key, 'secret': self.secret_key, })
        self.coins = [["ADA", "EUR"], ["BTC", "EUR"],["ETH", "EUR"], ["WIN", "EUR"]]
        self.coinlist = []
        self.create_coin_list()

    def get_exchange_login(self):
        self.api_key = os.environ['APIKET']
        self.secret_key = os.environ['SECKET']

    def create_coin_list(self):
        for coin in self.coins:
            c = Coin(self.exchange, coin[0], coin[1])
            self.coinlist.append(c)

    def start_monitoring(self):
        while True:
            for coin in self.coinlist:
                time.sleep(0.5)
                coin.check_action()


if __name__ == '__main__':
    monitor = Monitor()
    monitor.start_monitoring()
