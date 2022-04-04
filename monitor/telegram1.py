# importing all required libraries
import requests
from datetime import datetime
import pytz


IST = pytz.timezone('Europe/Amsterdam')
raw_TS = datetime.now(IST)
curr_date = raw_TS.strftime("%d-%m-%Y")
curr_time = raw_TS.strftime("%H:%M:%S")

# get your api_id, api_hash, token
# from telegram as described above
api_id = '19737079' #'API_id'
api_hash = 'a15fda242697654c0f30ff40cad425e2' #'API_hash'
telegram_auth_token = '5146805833:AAEeUabUJRRpsoxxvT00HqvnFh4A--L5kcQ' #'bot token'
telegram_group_id = 'Mon_crpt'
#message = "Working..."

msg = f"Message received on ({curr_date} at {curr_time}."


# your phone number

phone = '+31614944134' #os.environ.get('PHONENUMBER') #YOUR_PHONE_NUMBER_WTH_COUNTRY_CODE
def telegram_bot_sendtext(bot_message):
    api_id = '19737079'  # 'API_id'
    telegram_auth_token = '5146805833:AAEeUabUJRRpsoxxvT00HqvnFh4A--L5kcQ'  # 'bot token'

    bot_token = '101XXXXXX:AAF50Nh75K0jf0cKN16SFpTqge2gijqMsAUV'
    bot_chatID = 'XXXXXXXX'
    send_text = 'https://api.telegram.org/bot' + telegram_auth_token + '/sendMessage?chat_id=' + api_id + '&parse_mode=Markdown&text=' + bot_message

    response = requests.get(send_text)

    return response.json()


test = telegram_bot_sendtext("Testing Telegram bot")
print(test)

def send_msg_on_telegram(message):
    tel_resp = requests.post(f"https://api.telegram.org/bot{telegram_auth_token}/sendMessage?chat_id={telegram_group_id}&text=Hello World!")
    telegram_api_url = f"https://api.telegram.org/bot{telegram_auth_token}/sendMessage?chat_id=@{telegram_group_id}%text={message}"
    print(telegram_api_url)
    tel_resp = requests.get(telegram_api_url)
    print(requests.Response())
    if tel_resp.status_code == 200:
        print("INFO : Notification has been sent on Telegram")
    else:
        print(tel_resp)
        print("ERROR : Could not send Message")

send_text = 'https://api.telegram.org/bot' + telegram_auth_token + '/sendMessage?chat_id=' + telegram_group_id + '&parse_mode=Markdown&text=' + msg

response = requests.get(send_text)
print(response.json())


#send_msg_on_telegram(msg)

"""
# creating a telegram session and assigning
# it to a variable client
client = TelegramClient('session', api_id, api_hash)

# connecting and building the session
client.connect()

# in case of script ran first time it will
# ask either to input token or otp sent to
# number or sent or your telegram id
if not client.is_user_authorized():
    client.send_code_request(phone)

    # signing in the client
    client.sign_in(phone, input('Enter the code: '))

try:
    # receiver user_id and access_hash, use
    # my user_id and access_hash for reference
    receiver = InputPeerUser('user_id', 'user_hash')

    # sending message using telegram client
    client.send_message(receiver, message, parse_mode='html')
except Exception as e:

    # there may be many error coming in while like peer
    # error, wrong access_hash, flood_error, etc
    print(e);

# disconnecting the telegram session
client.disconnect()
"""