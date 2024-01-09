import os, logging, datetime, pytz
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
  MessageHandler,
  ApplicationBuilder,
  ContextTypes,
  CommandHandler,
  filters,
)

class ChatData:
    """Custom class for chat_data."""
    def __init__(self) -> None:
        self.logs = list()
        self.expenditure = dict()

    def clear(self) -> None:
        self.logs.clear()
        self.expenditure.clear()
    
    def update_expenditure(self, key: str, value: float) -> None:
        p_value = self.expenditure.get(key, 0)
        self.expenditure[key] = p_value + value
        
    def update_log(self, update_time: datetime, log: str) -> None:
        sg_timezone = pytz.timezone('Asia/Singapore')
        sg_datetime = update_time.replace(tzinfo=pytz.utc).astimezone(sg_timezone)
        update_time = sg_datetime.strftime('%a %d %b, %I:%M%p')
        self.logs.append(f"{update_time} --- {log}")
    
    def avg_expenditure(self) -> float:
        total_expenditure = sum(self.expenditure.values())
        num_people = len(self.expenditure)
        return total_expenditure/num_people
    
    def resolve_expenses(self) -> list:
        avg_expenditure = self.avg_expenditure()

        debts = {person: expense - avg_expenditure for person, expense in self.expenditure.items()}
        creditors = {person: expense for person, expense in debts.items() if expense > 0}
        debtors = {person: expense for person, expense in debts.items() if expense < 0}

        transactions = list()

        for debtor, debtor_amount in debtors.items():
          for creditor, creditor_amount in creditors.items():
              if debtor_amount == 0:
                  break
              if creditor_amount == 0:
                  continue

              # Determine the amount to transfer
              transfer_amount = min(-debtor_amount, creditor_amount)

              # Update the balances
              debtors[debtor] += transfer_amount
              creditors[creditor] -= transfer_amount

              # Record the transaction
              transactions.append((debtor, creditor, transfer_amount))

        return transactions
        
        
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays salutation and clears all previous records
    """
    context.chat_data.clear()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="""I'm SplitLaterBot, here to help calculate who you should pay after a group evening out!\n\nType /help to view all commands\n\n*Note: When encountering an error, re-enter the instruction rather than editing the previous message.\n\nMade by: @nelthm"""
    )

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays all commands and their usages
    Usage: /help
    """
    preamble = "Here are all the commands available to you!\n\n"
    start_message = "/start: Restarts the session and clears all previous record\nUsage: /start\n\n"
    help_message = "/help: Displays all commands\nUsage: /help\n\n"
    add_message = "/add: Adds an individual's expense\nUsage: /add John 10\n\n"
    delete_message = "/del: Deletes individual and expenses from record\nUsage: /del John\n\n"
    view_message = "/view: Displays accumulated expenses of all individuals\nUsage: /view\n\n"
    resolve_message = "/resolve: Calculates which individual needs to pay who\nUsage: /resolve\n\n"
    logs_message = "/logs: Displays all transactions since the start\nUsage: /logs\n\n"

    await update.message.reply_text(
        f"{preamble}{start_message}{help_message}{add_message}{delete_message}{view_message}{resolve_message}{logs_message}"
    )
      

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Adds an expense made by the user
    Usage: /add value
    """
    try:
        person = ' '.join(context.args[:-1])
        value = context.args[-1]
    except: # User enters < and > 2 arguments
        await update.message.reply_text("Error: the format should be '/add name value'.")
        pass
  
    try:
        context.chat_data.update_expenditure(person, float(value))
        context.chat_data.update_log(update.message.date, update.message.text)
        await update.message.reply_text("Added!")
    except ValueError: # non-numeric value found as expense argument
        await update.message.reply_text("Error: non-numeric value found.")
        pass


async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Deletes an entire person's record
    Usage: /del person
    """
    person = context.args[0]
    if person in context.chat_data:
      del context.chat_data[person]

    await update.message.reply_text("Removed!")


async def view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Views the cumulative expenditure of all persons
    Usage: /view
    """
    try:
      message = ''
      for person, expense in context.chat_data.expenditure.items():
        message += f"{person} has paid {expense}\n"
      
      await update.message.reply_text(message)
    except:
        await update.message.reply_text(f"Error: No records have been added.")


async def resolve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Resolves all expenditures and splits among persons
    Usage: /resolve
    """
    try:
      transactions = context.chat_data.resolve_expenses()
      message = ''
      for debtor, creditor, amount in transactions:
        string = f"{debtor} pays {creditor} ${amount:.2f}\n"
        message += string
      
      await update.message.reply_text(message)
    except ZeroDivisionError:
        await update.message.reply_text(f"Error: Either no individuals added, no expenses added, or everyone has spent equal amounts.")


async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays all transactions since epoch
    Usage: /logs
    """
    message = ''
    for log in context.chat_data.logs:
        message += f"{log}\n"

    await update.message.reply_text(message)

async def _unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Internal use for unknown command handling
    """
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Error: Either a wrong command has been entered, or a previous message has been edited. Please retype as opposed to editing the previous message :)")

if __name__ == '__main__':
    # Initialize environment variables
    load_dotenv()
    TOKEN = os.environ['BOT_TOKEN']
    NAME = 'SplitLaterBot'

    # Port given by Heroku
    # PORT = os.environ['PORT']

    # Enable Logging
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Build application
    context_types = ContextTypes(chat_data=ChatData)
    application = ApplicationBuilder().token(TOKEN).context_types(context_types).build()

    # Setup core-function handlers
    start_handler = CommandHandler('start', start, filters=~filters.UpdateType.EDITED_MESSAGE)
    help_handler = CommandHandler('help', help, filters=~filters.UpdateType.EDITED_MESSAGE)
    add_handler = CommandHandler('add', add, filters=~filters.UpdateType.EDITED_MESSAGE)
    del_handler = CommandHandler('del', delete, filters=~filters.UpdateType.EDITED_MESSAGE)
    view_handler = CommandHandler('view', view, filters=~filters.UpdateType.EDITED_MESSAGE)
    resolve_handler = CommandHandler('resolve', resolve, filters=~filters.UpdateType.EDITED_MESSAGE)
    logs_handler = CommandHandler('logs', logs, filters=~filters.UpdateType.EDITED_MESSAGE)

    # Add core-function handlers
    application.add_handler(start_handler)
    application.add_handler(help_handler)
    application.add_handler(add_handler)
    application.add_handler(del_handler)
    application.add_handler(view_handler)
    application.add_handler(resolve_handler)
    application.add_handler(logs_handler)
                            
    # Setup and add handlers
    unknown_handler = MessageHandler(filters.COMMAND, _unknown)
    application.add_handler(unknown_handler)

    # Start the webhook
    # application.run_webhook(listen="0.0.0.0",
    #                       port=int(PORT),
    #                       url_path=TOKEN,
    #                       webhook_url=f"https://{NAME}.herokuapp.com/{TOKEN}")
    
    application.run_polling()
    
