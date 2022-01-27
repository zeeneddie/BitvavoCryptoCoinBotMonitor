import os
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
                     Column('Interval', String)
                     )


TradingOrders = Table('TradingOrders', metadata,
                      Column('Timestamp', String),
                      Column('OrderID', Integer, primary_key=True),
                      Column('Exchange', String),
                      Column('Pair', String),
                      Column('Position', String),
                      Column('Amount', Float),
                      Column('Price', Float),
                      Column('Simulated', String)
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


if __name__ == '__main__':
    reset_db()