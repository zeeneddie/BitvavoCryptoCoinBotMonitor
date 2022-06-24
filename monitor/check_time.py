from time import time
from urllib.request import urlopen
import json
import datetime

def time_ms() -> int:
    return int(time() * 1000)


def calculate_lag():
    url = "https://api.bitvavo.com/v2/time"
    result = json.loads(urlopen(url).read())
    server_time = result["time"]
    local_time = time_ms()
    time_delta_ms = result["time"] - local_time

    serv_dt = datetime.datetime.fromtimestamp(server_time / 1000.0, tz=datetime.timezone.utc)
    local_dt = datetime.datetime.fromtimestamp(local_time / 1000.0, tz=datetime.timezone.utc)

    print(f"server_time: {server_time} = {serv_dt}")
    print(f"local_time: {local_time} = {local_dt}")
    print(f"difference: {time_delta_ms}")


if __name__ == "__main__":
    local_time = time_ms()
    print(local_time)
    oude_tijd = 1655710700716
    time_delta_ms = local_time - oude_tijd

    serv_dt = datetime.datetime.fromtimestamp(oude_tijd / 1000.0, tz=datetime.timezone.utc)
    print(f"server_time: {oude_tijd} = {serv_dt}")

    local_dt = datetime.datetime.fromtimestamp(local_time / 1000.0, tz=datetime.timezone.utc)
    print(f"local_time: {local_time} = {local_dt}")
    # dd/mm/YY H:M:S
    serv_string = serv_dt.strftime("%Y-%m-%d %H:%M:%S")
    local_string = local_dt.strftime("%Y-%m-%d %H:%M:%S")
    print("date and time =", serv_string, " ", local_string)
    a = datetime.datetime.strptime(serv_string, "%Y-%m-%d %H:%M:%S")
    b = datetime.datetime.strptime(local_string, "%Y-%m-%d %H:%M:%S")
    c = b - a
    print(a)
    print(b)
    print(f"difference: {time_delta_ms}")
    print(c)
    print(type(c))