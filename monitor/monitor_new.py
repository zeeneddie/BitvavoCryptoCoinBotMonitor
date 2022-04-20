import logging
import os
import time
from core.database.file import File
from coin_new import Coin
from coinlist_new import Coinlist
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
        if
        c = Coin(bitvavo_client, coin)
        coinlist.append(c)
    return coinlist

def print_overview(input_queue, coin_list):
    mon_list = ['ADA', 'HOT', 'BTC', 'WIN', 'DENT', 'ZRX', 'XRP', 'ETH']
    if (input_queue.qsize() > 0):
        input_str = input_queue.get()
        coin_list.sort(key = lambda b: b.base_currency)
        if input_str in mon_list:
            coin_list.sort(key=lambda b: b.current_price)
            for coin in coin_list:
                if input_str == coin.base_currency:
                    if coin.position:
                        print(
                        f"{coin.index}, {coin.last_update}, {coin.number_deals}, {coin.amount}: {coin.base_currency}, \t{coin.position}, \tstart: {coin.current_price}, \tcurrent: {coin.bid} = {round((coin.bid / coin.current_price) * 100, 2)}, \thigh: {coin.high} = {round((coin.high / coin.current_price) * 100, 2)}, \tDrempel: {coin.gain}")
                    else:
                        print(
                            f"{coin.index}, {coin.last_update}, {coin.number_deals}, {coin.amount}: {coin.base_currency}, \t{coin.position}, \tstart: {coin.current_price}, \tcurrent: {coin.ask} = {round((coin.ask / coin.current_price) * 100, 2)}, \tlow: {coin.low} = {round((coin.low / coin.current_price) * 100, 2)}, \tdrempel: {coin.gain}")
        if (input_str == 'c'):
            for coin in coin_list:
                if coin.position:
                    print(
                        f"{coin.index}, {coin.last_update}, {coin.number_deals}: {coin.base_currency}, \t{coin.position}, \tStart: {coin.current_price}, \tCurrent: {coin.bid}, \tHigh: {coin.high} = {round((coin.bid / coin.current_price) * 100, 2)}")
                else:
                    print(
                        f"{coin.index}, {coin.last_update}, {coin.number_deals}: {coin.base_currency}, \t{coin.position}, \tStart: {coin.current_price}, \tCurrent: {coin.ask}, \tLow: {coin.low} = {round((coin.ask / coin.current_price) * 100, 2)}")

        elif (input_str == 'h'):
            for coin in coin_list:
                if coin.position:
                    if (round((coin.bid / coin.current_price)* 100, 2)) > 100:
                        print(
                            f"{coin.index}, {coin.last_update}, {coin.number_deals}, {coin.amount}: {coin.base_currency}, \t{coin.position}, \tstart: {coin.current_price}, \tcurrent: {coin.bid} = {round((coin.bid / coin.current_price) * 100, 2)}, \thigh: {coin.high} = {round((coin.high / coin.current_price) * 100, 2)}, \tDrempel: {coin.gain}")
                else:
                    if (round((coin.ask / coin.current_price) * 100, 2)) < 99:
                        print(
                            f"{coin.index}, {coin.last_update}, {coin.number_deals}, {coin.amount}: {coin.base_currency}, \t{coin.position}, \tstart: {coin.current_price}, \tcurrent: {coin.ask} = {round((coin.ask / coin.current_price) * 100, 2)}, \tlow: {coin.low} = {round((coin.low / coin.current_price) * 100, 2)}, \tdrempel: {coin.gain}")
        elif (input_str == 'n'):
            for coin in coin_list:
                if not coin.position:
                    print(
                        f"{coin.index}, {coin.last_update}, {coin.number_deals}, {coin.amount}: {coin.base_currency}, \t{coin.position}, \tstart: {coin.current_price}, \tcurrent: {coin.ask} = {round((coin.ask / coin.current_price) * 100, 2)}, \tlow: {coin.low} = {round((coin.low / coin.current_price) * 100, 2)}, \tdrempel: {coin.gain}")
        elif (input_str == 'p'):
            for coin in coin_list:
                if coin.position:
                    print(
                        f"{coin.index}, {coin.last_update}, {coin.number_deals}, {coin.amount}: {coin.base_currency}, \t{coin.position}, \tstart: {coin.current_price}, \tcurrent: {coin.bid} = {round((coin.bid / coin.current_price) * 100, 2)}, \thigh: {coin.high} = {round((coin.high / coin.current_price) * 100, 2)}, \tDrempel: {coin.gain}")
        elif (input_str == 't'):
            one_printed = False
            for coin in coin_list:
                if not coin.position:
                    if coin.buy_signal:
                        one_printed = True
                        print(
                            f"{coin.index}, {coin.last_update}, {coin.number_deals}, {coin.amount}: {coin.base_currency}, \t{coin.position}, \tStart: {coin.current_price}, \tCurrent: {coin.ask} = {round((coin.ask / coin.current_price) * 100, 2)}, \tLow: {coin.low} = {round((coin.low / coin.current_price) * 100, 2)}, \tDrempel: {coin.gain}")
                if coin.position:
                    if coin.sell_signal:
                        one_printed = True
                        print(
                            f"{coin.index}, {coin.last_update}, {coin.number_deals}, {coin.amount}: {coin.base_currency}, \t{coin.position}, \tStart: {coin.current_price} = {round((coin.bid / coin.current_price) * 100, 2)}, \tCurrent: {coin.bid}, \tLow: {coin.high} = {round((coin.high / coin.current_price) * 100, 2)}, \tDrempel: {coin.gain}")
            if not one_printed:
                print("No TRIGGERS")
        elif (input_str == 'f'):
            file.write(coinlist)

def start_monitoring(coin_list):
    EXIT_COMMAND = 'exit'
    input_queue = queue.Queue()

    input_thread = threading.Thread(target=read_kbd_input, args=(input_queue,), daemon=True)
    input_thread.start()
    while True:
        print_overview(input_queue, coin_list)

        for coin in coin_list:
            time.sleep(0.2)
            old_coin_position = coin.get_position()
            coin.check_action()
            new_coin_position = coin.get_position()
            if new_coin_position == old_coin_position:
                pass
            else:
                file.write(coinlist)


if __name__ == '__main__':
    coin_list = Coinlist()
    start_monitoring(coin_list)
