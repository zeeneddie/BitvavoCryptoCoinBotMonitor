import logging
import os
import time
from core.database.file import File
from core.markets.coin import Coin
from bitvavo_client import Bitvavo_client
import threading
import queue
import time


logger = logging.getLogger(__name__)


def read_kbd_input(input_queue):
    print("Ready for keyboard input!!")
    while (True):
        input_str = input()
        input_queue.put(input_str)


#class Monitor:

#    def __init__(self):
bitvavo_client = Bitvavo_client()
file = File()
coins = file.read()
coinlist = []

def create_coin_list():
    for coin in coins:
        c = Coin(bitvavo_client, coin)
        coinlist.append(c)
    return coinlist

def start_monitoring(coin_list):
    EXIT_COMMAND = 'exit'
    input_queue = queue.Queue()

    input_thread = threading.Thread(target=read_kbd_input, args=(input_queue,), daemon=True)
    input_thread.start()
    while True:
        if(input_queue.qsize() > 0):
            input_str = input_queue.get()
            if (input_str == EXIT_COMMAND):
                print("Exiting serial monitoring")
                #save settings
                break
            elif (input_str == 'o'):
                for coin in coin_list:
                    if coin.position:
                        print(f"{coin.base_currency}, \t{coin.position}, \tStart: {coin.current_price}, \tBid: {coin.ask} = {round((coin.ask / coin.current_price)* 100, 2)   }")
                    else:
                        print(f"{coin.base_currency}, \t{coin.position}, \tStart: {coin.current_price}, \tAsk: {coin.bid} = {round((coin.bid / coin.current_price) * 100, 2)   }")
            elif (input_str == 'c'):
                for coin in coin_list:
                    if coin.position:
                        print(
                            f"{coin.base_currency}, \t{coin.position}, \tStart: {coin.current_price}, \tCurrent: {coin.bid}, \tHigh: {coin.high} = {round((coin.bid / coin.current_price) * 100, 2)}")
                    else:
                        print(
                            f"{coin.base_currency}, \t{coin.position}, \tStart: {coin.current_price}, \tCurrent: {coin.ask}, \tLow: {coin.low} = {round((coin.ask / coin.current_price) * 100, 2)}")
            elif (input_str == 'f'):
                for coin in coin_list:
                    if coin.position:
                        print(f"{coin.base_currency}, {coin.position}, Start: {coin.current_price}, Bid: {coin.bid}, Amount: {coin.amount}, Gain: {coin.gain}, trail: sell-{coin.trail_stop_sell_drempel}")
                    else:
                        print(f"{coin.base_currency}, {coin.position}, Start: {coin.current_price}, Ask: {coin.ask}, Amount: {coin.amount}, Gain: {coin.gain}, trail: buy-{coin.trail_stop_buy_drempel}")

            elif (input_str == 'h'):
                for coin in coin_list:
                    if coin.position:
                        print(f"{coin.base_currency}, {coin.position}, Start: {coin.current_price}, High: {coin.high} = {round((coin.high / coin.current_price) * 100, 2)}")
                    else:
                        print(f"{coin.base_currency}, {coin.position}, Start: {coin.current_price}, Low: {coin.low} = {round((coin.low / coin.current_price) * 100, 2)}")

        for coin in coin_list:
            time.sleep(0.1)
            old_coin_position = coin.get_position()
            coin.check_action()
            new_coin_position = coin.get_position()
            if new_coin_position == old_coin_position:
                pass
            else:
                pass #self.file.write(self.coinlist)


if __name__ == '__main__':
    coin_list = create_coin_list()
    start_monitoring(coin_list)
