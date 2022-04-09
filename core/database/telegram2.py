import logging
import os
import csv
from logging import debug, info


from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)
AUTHORIZED_USERS = ['EddieZeen']


# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
def start(update, context):
    """Send a message when the command /start is issued."""
    update.message.reply_text('Hi!')


def help(update, context):
    """Send a message when the command /help is issued."""
    update.message.reply_text('Help!')


def echo(update, context):
    """Echo the user message."""
    msg = update.message
    user = msg.from_user
    debug(f'Quiz bot entered by user: {user.id} @{user.username} "{user.first_name} {user.last_name}"')

    if AUTHORIZED_USERS and user.username not in AUTHORIZED_USERS:
        return

    if update.message.text == "file":
        file_name = 'coin_info.csv'
        file_fullpath = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            file_name)
        rows = []
        with open(file_fullpath, 'r') as file:
            csvreader = csv.reader(file)

            for row in csvreader:
                rows.append(row)
        for i in rows:
            message = i[0] + " " + i[1] + " " + i[3] + " " + i[4] + " " + i[5] + " " + str(round(float(i[6])*100,2)) + "% " + i[9] + " "+ i[10]
            update.message.reply_text (message) #(update.message.text)
    else:
        update.message.reply_text (message)


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main():
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    TOKEN=os.environ.get('TELEGRAMTOKEN')

    print(TOKEN)
    updater = Updater(TOKEN, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))

    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(Filters.text, echo))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()