from sqlalchemy import MetaData, Table, Column, String, Integer, Text, DateTime, Boolean, create_engine, select, insert, \
    update, delete
from threading import Lock

import os


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


        self.employees = Table('Employee', self.metadata,
                          Column('Id', Integer(), primary_key=True),
                          Column('LastName', String(8000)),
                          Column('FirstName', String(8000)),
                          Column('BirthDate', String(8000))
                          )


    def show_metadata(self):
        for t in self.metadata.sorted_tables:
            print(f"Table {t.name}:")
            for c in t.columns:
                print(f"{c} ({c.type})")


    def do_insert(self):
        stmt = insert(self.employees).values(
            LastName='Collins',
            FirstName='Arnold',
            BirthDate='2000-01-31')
        new_id = 0

        with self.engine.begin() as con:
            result = con.execute(stmt)
            new_id = result.inserted_primary_key['Id']
            print(f"New Id: {new_id}")

        return new_id


    def select_by_id(self, id):
        stmt = select(self.employees).where(self.employees.c.Id == id)

        with self.engine.begin() as con:
            result = con.execute(stmt).first()
            if result:
                print(result)
            else:
                print(f"no rows found with Id == {id}")


    def do_update(self, id):
        stmt = update(self.employees).values(
            FirstName="Michael"
        ).where(self.employees.c.Id == id)

        with self.engine.begin() as con:
            self.con.execute(stmt)


    def do_delete(self, id):
        stmt = delete(self.employees).where(self.employees.c.Id == id)

        with self.engine.begin() as con:
            self.con.execute(stmt)


    def statement_infos(self):
        stmt = select(self.employees.c.LastName, self.employees.c.FirstName).where(self.employees.c.Id == 30)
        print(f"statement with placeholder: \n{str(stmt)}")
        print(f"\nparams: \n{str(stmt.compile().params)}")


if __name__ == '__main__':
    db = Database()
    print("---- show_metadata() ----")
    db.show_metadata()
    print("---- do_insert() ----")
    id = db.do_insert()
    print("---- select_by_id() ----")
    db.select_by_id(id)
    print("---- do_update() ----")
    db.do_update(id)
    db.select_by_id(id)
    print("---- do_delete() ----")
    db.do_delete(id)
    db.select_by_id(id)
    print("---- end ----")
