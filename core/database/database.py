import os
import datetime
import time
from sqlalchemy import create_engine
from sqlalchemy import Table, Column, Integer, String, Float, MetaData, ForeignKey
from threading import Lock
import logging

logger = logging.getLogger(__name__)

db_name = 'core.db'
db_fullpath = os.path.join(
    os.path.dirname(
        os.path.realpath(__file__)),
    db_name)
lock = Lock()
engine = create_engine(
    'sqlite:///{}'.format(db_fullpath),
    connect_args={
        'check_same_thread': False},
    echo=False)
metadata = MetaData()
conn = engine.connect()

OHLCV = Table('OHLCV', metadata,
              Column('ID', Integer, primary_key=True),
              Column('Exchange', String),
              Column('Pair', String),
              Column('Timestamp', String),
              Column('Open', Float),
              Column('High', Float),
              Column('Low', Float),
              Column('Close', Float),
              Column('Volume', Float),
              Column('Interval', String),
              Column('TimestampRaw', Integer),
              Column('PairID', String, ForeignKey('TradingPairs.ID')),
              )

TradingPairs = Table('TradingPairs', metadata,
                     Column('ID', Integer, primary_key=True),
                     Column('Exchange', String),
                     Column('BaseCurrency', String),
                     Column('QuoteCurrency', String),
                     Column('Gain', Float),
                     Column('Trail', Float),
                     Column('StopLoss', Float)
                     )

TraidingOrders = Table('TraidingOrders', metadata,
                       Column('Timestamp', String),
                       Column('Pair', String),
                       Column('Amount', Float),
                       Column('Price', Float)
                       )

Positions = Table('Positions', metadata,
                      Column('Timestamp', String),
                      Column('Pair', String),
                      Column('Position', String),
                      Column('Amount', Float),
                      Column('Price', Float),
                      Column('Gain', Float),
                      Column('Trail', Float),
                      Column('StopLoss', Float)
                      )

def drop_tables():
    print('Dropping tables...')
    metadata.drop_all(engine)


def create_tables():
    print('Creating tables...')
    metadata.create_all(engine)

def reset_db():
    print('Resetting database...')
    drop_tables()
    create_tables()

def insert_positions_to_db():

     #ins1 = Positions.insert().values(Timestamp=get_timestamp(), Pair='ADA/EUR', Position='Y', Amount=7, Price=0.94, Gain=0.03, Trail=0.01, StopLoss=0.10)
     ins1 = Positions.insert().values(Timestamp=get_timestamp(), Pair='ADA/EUR', Position='Y', Amount=1, Price=0.94, Gain=0.03, Trail=0.01, StopLoss=0.10)
     conn.execute(ins1)
     #ins2 = Positions.insert().values(Timestamp=get_timestamp(), Pair='BTC/EUR', Position='Y', Amount=0.00017, Price=35145, Gain=0.03, Trail=0.01, StopLoss=0.10)
     ins2 = Positions.insert().values(Timestamp=get_timestamp(), Pair='BTC/EUR', Position='Y', Amount=0.000001, Price=35145, Gain=0.03, Trail=0.01, StopLoss=0.10)
     conn.execute(ins2)
     #ins3 = Positions.insert().values(Timestamp=get_timestamp(), Pair='ETH/EUR', Position='N', Amount=0.00016,
     #                                 Price=2580, Gain=0.03, Trail=0.01, StopLoss=0.10)
     ins3 = Positions.insert().values(Timestamp=get_timestamp(), Pair='ETH/EUR', Position='N', Amount=0.000001,
                                      Price=2580, Gain=0.03, Trail=0.01, StopLoss=0.10)
     conn.execute(ins3)
     #ins4 = Positions.insert().values(Timestamp=get_timestamp(), Pair='WIN/EUR', Position='N', Amount=20000, Price=0.0002885, Gain=0.03, Trail=0.01, StopLoss=0.10)
     ins4 = Positions.insert().values(Timestamp=get_timestamp(), Pair='WIN/EUR', Position='N', Amount=10, Price=0.0002885, Gain=0.03, Trail=0.01, StopLoss=0.10)
     conn.execute(ins4)
     logger.info("Wrote open order to DB...")

def get_all_positions():
     logger.warning("Retrieving all Positions ")
     result = conn.execute("SELECT Timestamp, Pair, Position, Amount, Price, Gain, Trail, StopLoss FROM Positions")
     for row in result:
         logger.warning(row )
     return

def get_coin_positions(analysis_pair):
    result = conn.execute("SELECT Timestamp, Pair, Position, Amount, Price, Gain, Trail, StopLoss FROM Positions WHERE Pair = ?", analysis_pair)
    l0 = [row for row in result]
    l1 = list(l0[0])

    return l1

def get_timestamp():
    return datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')

if __name__ == '__main__':
    reset_db()
    insert_positions_to_db()
    get_all_positions()
    print(get_coin_positions("ADA/EUR"))