import csv


class file():
    def __init(self):
        self.rows = []

    def read(self):
        with open("coin_info.csv", 'r') as file:
            csvreader = csv.reader(file)

            for row in csvreader:
                self.rows.append(row)
        print(self.rows)

    def write(self):
        filename = 'coin_info.csv'
        with open(filename, 'w') as file:
            for row in self.rows:
                for x in row:
                    file.write(str(x) + ', ')
                file.write('n')