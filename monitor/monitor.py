import logging
import os
import time
from core.database.file import File
from core.markets.coin import Coin
from bitvavo_client import Bitvavo_client
from core.database.database import Database


logger = logging.getLogger(__name__)


class Monitor:
    def __init__(self):
        self.bitvavo_client = Bitvavo_client()
        self.file = File()
        self.coins = self.file.read() # [["WIN", "EUR"], ["BTC", "EUR"],["ETH", "EUR"], ["ADA", "EUR"], ["HOT", "EUR"], ["DENT", "EUR"]]
        #self.db = Database()
        self.coinlist = []
        self.create_coin_list()

    def create_coin_list(self):
        for coin in self.coins:
            c = Coin(self.bitvavo_client, coin)
            self.coinlist.append(c)

    def start_monitoring(self):
        while True:
            for coin in self.coinlist:
                time.sleep(0.2)
                coin_position = coin.get_position()
                coin.check_action()
                if coin_position == coin_position():
                    pass
                else:
                    self.file.write()


if __name__ == '__main__':
    monitor = Monitor()
    monitor.start_monitoring()
