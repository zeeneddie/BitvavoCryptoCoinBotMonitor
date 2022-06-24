import csv
import os


class File():
    def read(self):
        self.file_name = 'coin_info.csv'
        self.file_fullpath = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            self.file_name)
        print(self.file_fullpath)
        self.rows = []
        with open(self.file_fullpath, 'r') as file:
            csvreader = csv.reader(file)

            for row in csvreader:
                self.rows.append(row)
                print(row)

        return (self.rows)

    def write(self, coinlist):
        coins = []
        for coin in coinlist:
            c = []
            c.append(coin.index)
            c.append(coin.base_currency)
            c.append(coin.quote_currency)
            if coin.position == True:
                coin.pos_txt = 'Y'
            else:
                coin.pos_txt = 'N'
            c.append(coin.pos_txt)
            c.append(coin.amount)
            c.append(coin.current_price)
            c.append(coin.gain)
            c.append(coin.trail)
            c.append(coin.stoploss)
            c.append(coin.number_deals)
            c.append(coin.last_update)
            c.append(coin.sleep_till)
            coins.append(c)
        filename = 'coin_info.csv'
        self.file_fullpath = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            self.file_name)
        with open(self.file_fullpath, 'w') as file:
            for row in coins:
                file.write(str(row[0]) + ',' + str(row[1]) + ',' + str(row[2]) + ',' + str(row[3]) + ',' + str(row[4]) + ',' + str(row[5]) + ',' + str(row[6]) + ',' + str(row[7]) + ',' + str(row[8]) + ',' + str(row[9]) + ',' + str(row[10] + ',' + str(row[11])))
                file.write('\n')


if __name__ == "__main__":
    f = File()
    r = f.read()
    print(r)
    f.write(r)