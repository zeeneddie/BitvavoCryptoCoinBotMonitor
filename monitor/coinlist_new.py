import datetime
import time
import logging
import os
from collections import defaultdict
from csv import DictReader
from coin_new import Coin_new
from bitvavo_client import Bitvavo_client


logger = logging.getLogger(__name__)

markets = []


class Coinlist:
    def __init__(self):
        self.coins = []

        file_name = 'coin_info_new.csv'
        file_fullpath = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            file_name)
        # open file
        with open(file_fullpath, "r") as my_file:
            # pass the file object to reader()
            csv_dict_reader = DictReader(my_file)

            # iterating over each row
            for row in csv_dict_reader:
                # print the valuesmembers
                if not Coinlist.Coin_exist(row['Base']):
                    coin = Coin_new(row)

        # for row in csvreader:
        #     self.rows.append(row)

   # def addInList(self):
   #      pass

    def __str__(self):
        return "Name: {}\nCity: {}\n".format(self.name, self.city)
    
    def Coin_exist(self):
        pass

    def get_book(self):
        best = self.bitvavo.book(self.analysis_pair, {'depth': '1'})
        if 'error' in best.keys():
            while 'error' in best.keys():
                print(best['error'])
                best = self.bitvavo.book(self.analysis_pair, {'depth': '1'})
        return best['bids'][0][0]

def get_timestamp():
    return datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')

if __name__ == '__main__':
    coin_list = Coinlist()