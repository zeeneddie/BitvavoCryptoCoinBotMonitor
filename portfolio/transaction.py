from monitor.bitvavo_client import Bitvavo_client
import datetime

class Transaction():
    def __init__(self):
        self.bitvavo = Bitvavo_client()

    def print_overview(self):
        response = self.bitvavo.bitvavo.trades('BTC-EUR', {})
        for item in response:
            print(self.get_timestamp(item['timestamp']),
                  item['market'],
                  item['side'],
                  item['amount'],
                  item['price'],
                  item['fee']
                  )


    def get_timestamp(self, t):
        return datetime.datetime.fromtimestamp(t/1000 ).strftime('%d-%m-%Y %H:%M:%S')


if __name__ == "__main__":
    trans = Transaction()

    trans.print_overview()

