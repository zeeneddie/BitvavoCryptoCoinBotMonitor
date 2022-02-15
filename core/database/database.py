import os
import datetime
import time
from sqlalchemy import create_engine
from sqlalchemy import Table, Column, Integer, String, Float, MetaData, ForeignKey
from sqlalchemy.sql import update
from sqlalchemy.sql import select
from threading import Lock
import logging

logger = logging.getLogger(__name__)


class Database():
    def __init__(self):
        self.db_name = 'core.db'
        self.db_fullpath = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            self.db_name)
        self.lock = Lock()
        self.engine = create_engine(
            'sqlite:///{}'.format(self.db_fullpath),
            connect_args={'check_same_thread': False},
            echo=False)
        self.metadata = MetaData()
        self.conn = self.engine.connect()


        self.TradingPairs = Table('TradingPairs', self.metadata,
                                  Column('ID', Integer, primary_key=True),
                                  Column('Exchange', String),
                                  Column('BaseCurrency', String),
                                  Column('QuoteCurrency', String),
                                  Column('Gain', Float),
                                  Column('Trail', Float),
                                  Column('StopLoss', Float)
                                  )

        self.TradingOrders = Table('TradingOrders', self.metadata,
                                    Column('Timestamp', String),
                                    Column('Pair', String),
                                    Column('Side', String),
                                    Column('Amount', Float),
                                    Column('Price', Float)
                                    )

        self.Positions = Table('Positions', self.metadata,
                               Column('Timestamp', String),
                               Column('Pair', String),
                               Column('Position', String),
                               Column('Amount', Float),
                               Column('Price', Float),
                               Column('Gain', Float),
                               Column('Trail', Float),
                               Column('StopLoss', Float)
                               )

        self.employees = Table('Employee', self.metadata,
                               Column('Id', Integer(), primary_key=True),
                               Column('LastName', String(8000)),
                               Column('FirstName', String(8000)),
                               Column('BirthDate', String(8000))
                               )

    def drop_tables(self):
        print('Dropping tables...')
        self.metadata.drop_all(self.engine)

    def create_tables(self):
        print('Creating tables...')
        self.metadata.create_all(self.engine)

    def reset_db(self):
        print('Resetting database...')
        self.drop_tables()
        self.create_tables()

    def insert_positions_to_db(self):
        ins1 = self.Positions.insert().values(Timestamp=self.get_timestamp(), Pair='ADA-EUR', Position='Y', Amount=10,
                                         Price=0.963, Gain=0.03, Trail=0.01, StopLoss=0.10)
        #ins1 = self.Positions.insert().values(Timestamp=self.get_timestamp(), Pair='ADA-EUR', Position='Y', Amount=1,
        #                                     Price=0.94, Gain=0.01, Trail=0.005, StopLoss=0.10)
        self.conn.execute(ins1)
        ins2 = self.Positions.insert().values(Timestamp=self.get_timestamp(), Pair='BTC-EUR', Position='Y', Amount=10,
                                         Price=38245, Gain=0.03, Trail=0.01, StopLoss=0.10)
        #ins2 = self.Positions.insert().values(Timestamp=self.get_timestamp(), Pair='BTC-EUR', Position='Y',
        #                                      Amount=0.000001, Price=35145, Gain=0.01, Trail=0.005, StopLoss=0.10)
        self.conn.execute(ins2)
        ins3 = self.Positions.insert().values(Timestamp=self.get_timestamp(), Pair='ETH-EUR', Position='N', Amount=10,
                                         Price=2731, Gain=0.03, Trail=0.01, StopLoss=0.10)
        #ins3 = self.Positions.insert().values(Timestamp=self.get_timestamp(), Pair='ETH-EUR', Position='N',
        #                                      Amount=0.000001,
        #                                      Price=2580, Gain=0.03, Trail=0.01, StopLoss=0.10)
        self.conn.execute(ins3)
        ins4 = self.Positions.insert().values(Timestamp=self.get_timestamp(), Pair='WIN-EUR', Position='N', Amount=10,
                                         Price=0.00029569, Gain=0.03, Trail=0.01, StopLoss=0.10)
        #ins4 = self.Positions.insert().values(Timestamp=self.get_timestamp(), Pair='WIN-EUR', Position='N', Amount=35000,
        #                                     Price=0.0003150, Gain=0.03, Trail=0.01, StopLoss=0.10)
        self.conn.execute(ins4)
        ins5 = self.Positions.insert().values(Timestamp=self.get_timestamp(), Pair='HOT-EUR', Position='Y', Amount=10,
                                              Price=0.00443, Gain=0.03, Trail=0.01, StopLoss=0.10)
        self.conn.execute(ins5)
        ins6 = self.Positions.insert().values(Timestamp=self.get_timestamp(), Pair='DENT-EUR', Position='N', Amount=10,
                                              Price=0.0026984, Gain=0.03, Trail=0.01, StopLoss=0.10)
        self.conn.execute(ins6)
        logger.info("Wrote open order to DB...")

    def get_all_positions(self):
        logger.warning("Retrieving all Positions ")
        result = self.conn.execute(
            "SELECT Timestamp, Pair, Position, Amount, Price, Gain, Trail, StopLoss FROM Positions")
        for row in result:
            logger.warning(row)
        return

    def get_coin_positions(self, analysis_pair):
        result = self.conn.execute(
            "SELECT Timestamp, Pair, Position, Amount, Price, Gain, Trail, StopLoss FROM Positions WHERE Pair = ?",
            analysis_pair)
        l0 = [row for row in result]
        l1 = list(l0[0])
        return l1

    # def update_position(self, coin, result):
    #     r = self.conn.execute(
    #         "UPDATE Positions WHERE Pair == "

    def get_orders(self):
        result = self.conn.execute("SELECT Timestamp, Pair, Side, Amount, Price FROM TradingOrders")
        l0 = [row for row in result]
        l1 = list(l0[0])
        return l1

    def write_order(self, pair, side, amount, price):
        with self.lock:
            ins = self.TradingOrders.insert().values(Timestamp=self.get_timestamp(), Pair=pair, Side=side,
                                                              Amount=amount, Price=price)
            self.conn.execute(ins)
            logger.info("Wrote order to DB...")

    def get_timestamp(self):
        return datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')

    def update_position(self, pair, position, price):

        update_statement = self.Positions.update() \
            .where \
                (self.Positions.c.Pair == pair) \
            .values(Position = position, \
                    Price = price)

        self.conn.execute(update_statement)



if __name__ == '__main__':
    db = Database()
    #db.update_position( "ADA-EUR", "N", 0.964)
    #b = db.get_orders()
    #print(b)
    #db.reset_db()
    db.drop_tables()
    db.create_tables()
    db.insert_positions_to_db()
    db.get_all_positions()
    print(db.get_coin_positions("WIN-EUR"))
