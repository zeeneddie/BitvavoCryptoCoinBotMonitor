import logging
import os
import time
from core.markets.coin import Coin
from bitvavo_client import Bitvavo_client
from core.database.database import Database

logger = logging.getLogger(__name__)


class Monitor:
    def __init__(self):
        self.bitvavo_client = Bitvavo_client()
        self.coins = [["WIN", "EUR"], ["BTC", "EUR"],["ETH", "EUR"], ["ADA", "EUR"], ["HOT", "EUR"], ["DENT", "EUR"]]
        self.db = Database()
        self.coinlist = []
        self.create_coin_list()

    def get_exchange_login(self):
        self.api_key = os.environ['APIMON']
        self.secret_key = os.environ['SECMON']

    def create_coin_list(self):
        for coin in self.coins:
            c = Coin(self.db, self.bitvavo_client, coin[0], coin[1])
            self.coinlist.append(c)

    def start_monitoring(self):
        while True:
            for coin in self.coinlist:
                time.sleep(0.5)
                coin.check_action(self.db)


if __name__ == '__main__':
    monitor = Monitor()
    monitor.start_monitoring()
