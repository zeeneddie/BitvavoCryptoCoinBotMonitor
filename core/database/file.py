import csv
import os


class File():
    def read(self):
        self.file_name = 'coin_info.csv'
        self.file_fullpath = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            self.file_name)
        self.rows = []
        with open(self.file_fullpath, 'r') as file:
            csvreader = csv.reader(file)

            for row in csvreader:
                self.rows.append(row)
        return (self.rows)

    def write(self, rows):
        filename = 'coin_info.csv'
        with open(filename, 'w') as file:
            for row in rows:
                for x in row:
                    file.write(str(x) + ', ')
                file.write('\n')


if __name__ == "__main__":
    f = File()
    r = f.read()
    f.write(r)