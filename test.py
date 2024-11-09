# import time
from datetime import datetime
from datetime import time
from datetime import timedelta


# res = timedelta(days=1)

if time(hour=datetime.now().hour, minute=datetime.now().minute, second=datetime.now().second) < time(hour=12):
    print('ok')
    print(timedelta(hours=10 - datetime.now().hour, minutes=0 - datetime.now().minute, seconds=0-datetime.now().second).seconds)


# if time.clock() < timedelta(hours=10):
#     print('меньше')

# print(datetime.now())