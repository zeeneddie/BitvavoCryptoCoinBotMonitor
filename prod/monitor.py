import logging
import os
import time
from file import File
from coin import Coin
from bitvavo_client import Bitvavo_client
import threading
import queue
import time
import datetime


logger = logging.getLogger(__name__)

def time_ms() -> int:
    return int(time.time() * 1000)

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

def print_overview(input_queue, coin_list):
    mon_list = ['ADA', 'HOT', 'BTC', 'WIN', 'DENT', 'ZRX', 'XRP', 'ETH', 'SHIB']
    if (input_queue.qsize() > 0):
        input_str = input_queue.get()
        coin_list.sort(key = lambda b: b.base_currency)
        if input_str in mon_list:
            coin_list.sort(key=lambda b: b.current_price)
            for coin in coin_list:
                if input_str == coin.base_currency:
                    if coin.position:
                        print(
                        f"{coin.index}, {coin.last_update}, {coin.number_deals}, {coin.amount}: {coin.base_currency}, \t{coin.position}, \tS: {coin.current_price}, \tC: {coin.bid} = {round((coin.bid / coin.current_price) * 100, 2)}, \tH: {coin.high} = {round((coin.high / coin.current_price) * 100, 2)}, \tD: {coin.gain}/{coin.trail}")
                    else:
                        print(
                            f"{coin.index}, {coin.last_update}, {coin.number_deals}, {coin.amount}: {coin.base_currency}, \t{coin.position}, \tS: {coin.current_price}, \tC: {coin.ask} = {round((coin.ask / coin.current_price) * 100, 2)}, \tL: {coin.low} = {round((coin.low / coin.current_price) * 100, 2)}, \tD: {coin.gain}/{coin.trail}")

        if (input_str == 'h'):
            for coin in coin_list:
                if coin.position:
                    if (round((coin.bid / coin.current_price)* 100, 2)) > 100:
                        print(
                            f"{coin.index}, {coin.last_update}, {coin.amount}: {coin.base_currency}, \t\t{coin.position}, \tS: {coin.current_price}, \tC: {coin.bid} = {round((coin.bid / coin.current_price) * 100, 2)}, \tH: {coin.high} = {round((coin.high / coin.current_price) * 100, 2)}, \tD: {coin.gain}/{coin.trail}")
                else:
                    if (round((coin.ask / coin.current_price) * 100, 2)) < 100:
                        print(
                            f"{coin.index}, {coin.last_update}, {coin.amount}: {coin.base_currency}, \t\t{coin.position}, \tS: {coin.current_price}, \tC: {coin.ask} = {round((coin.ask / coin.current_price) * 100, 2)}, \tL: {coin.low} = {round((coin.low / coin.current_price) * 100, 2)}, \tD: {coin.gain}/{coin.trail}")
        elif (input_str == 'n'):
            for coin in coin_list:
                if not coin.position:
                    print(
                        f"{coin.index}, {coin.last_update}, {coin.number_deals}, {coin.amount}: {coin.base_currency}, \t{coin.position}, \tS: {coin.current_price}, \tcurrent: {coin.ask} = {round((coin.ask / coin.current_price) * 100, 2)}, \ttemp_L: {coin.temp_low}\tL: {coin.low} = {round((coin.low / coin.current_price) * 100, 2)}, \tD: {coin.gain}/{coin.trail}")
        elif (input_str == 'a'):
           for coin in coin_list:
                 if coin.position:
                     print(
                        f"{coin.index}, {coin.last_update}, {coin.number_deals}, {coin.amount}: {coin.base_currency}, \t{coin.position}, \tS: {coin.current_price}, \tC: {coin.bid} = {round((coin.bid / coin.current_price) * 100, 2)}, \ttemp_H: {coin.temp_high}\tH: {coin.high} = {round((coin.high / coin.current_price) * 100, 2)}, \tD: {coin.gain}/{coin.trail}")
        elif (input_str == 'p'):
            for coin in coin_list:
                if coin.position:
                    print(
                        f"{coin.index}, {coin.last_update}, {coin.number_deals}, {coin.amount}: {coin.base_currency}, \t{coin.position}, \tS: {coin.current_price}, \tC: {coin.bid} = {round((coin.bid / coin.current_price) * 100, 2)}")
        elif (input_str == 't'):
            one_printed = False
            for coin in coin_list:
                if not coin.position:
                    if coin.buy_signal:
                        one_printed = True
                        print(
                            f"{coin.index}, {coin.last_update}, {coin.number_deals}, {coin.amount}: {coin.base_currency}, \t{coin.position}, \tS: {coin.current_price}, \tC: {coin.ask} = {round((coin.ask / coin.current_price) * 100, 2)}, \tL: {coin.low} = {round((coin.low / coin.current_price) * 100, 2)}, \tD: {coin.gain}/{coin.trail}")
                if coin.position:
                    if coin.sell_signal:
                        one_printed = True
                        print(
                            f"{coin.index}, {coin.last_update}, {coin.number_deals}, {coin.amount}: {coin.base_currency}, \t{coin.position}, \tS: {coin.current_price} = {round((coin.bid / coin.current_price) * 100, 2)}, \tC: {coin.bid}, \tH: {coin.high} = {round((coin.high / coin.current_price) * 100, 2)}, \tD: {coin.gain}/{coin.trail}")
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
            old_temp_high = coin.high
            old_temp_low = coin.low
            current_time = time_ms()
            if coin.sleep_till < current_time:
                coin.check_action()
            else:
                # dd/mm/YY H:M:S
                current_dt = datetime.datetime.fromtimestamp(current_time / 1000.0, tz=datetime.timezone.utc)
                sleep_dt = datetime.datetime.fromtimestamp(coin.sleep_till / 1000.0, tz=datetime.timezone.utc)
                current_string = current_dt.strftime("%Y-%m-%d %H:%M:%S")
                sleep_string = sleep_dt.strftime("%Y-%m-%d %H:%M:%S")
                print(f"sleep = {sleep_string} and time = {current_string}")
                a = datetime.datetime.strptime(sleep_string, "%Y-%m-%d %H:%M:%S")
                b = datetime.datetime.strptime(current_string, "%Y-%m-%d %H:%M:%S")
                c = a - b
                print(c)

            new_coin_position = coin.get_position()
            if new_coin_position == old_coin_position:
                pass
            else:
                file.write(coinlist)
            new_coin_temp_high = coin.high
            new_coin_temp_low = coin.low
            if new_coin_position == False:
                if new_coin_temp_low < old_temp_low:
                  file.write(coinlist)
            if new_coin_position == True:
                if new_coin_temp_high > old_temp_high:
                  file.write(coinlist)

if __name__ == '__main__':
    coin_list = create_coin_list()
    start_monitoring(coin_list)
