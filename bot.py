import os, logging, datetime, pytz, re
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
        self.users = list()
        self.logs = list()
        self.expenditure = dict()
        self.shared_expenditure = dict()

    def clear(self) -> None:
        self.users.clear()
        self.logs.clear()
        self.expenditure.clear()
        self.shared_expenditure.clear()

    def include(self, users) -> None:
        self.users = users
        for user in users:
            self.expenditure[user] = 0.0
    
    def update_expenditure(self, key: str, value: float, others: list = None):
        if others is None:
            p_value = self.expenditure.get(key, 0)
            self.expenditure[key] = p_value + value
        else:
            # self.shared_expenditure = {creditor: {debtors: value, debtors1: value}}
            debtor_value_dict = self.shared_expenditure.get(key, {})  # gets dict of debtors and values
            debtor_value_dict[frozenset(others)] = debtor_value_dict.get(frozenset(others), 0) + value # gets value and increment
            self.shared_expenditure[key] = debtor_value_dict

    def update_log(self, update_time: datetime, log: str) -> None:
        sg_timezone = pytz.timezone('Asia/Singapore')
        sg_datetime = update_time.replace(tzinfo=pytz.utc).astimezone(sg_timezone)
        update_time = sg_datetime.strftime('%a %d %b, %I:%M%p')
        self.logs.append(f"{update_time} --- {log}")
    
    def avg_expenditure(self) -> float: # excludes misc_expenditure
        try:
            total_expenditure = sum(self.expenditure.values())
            num_people = len(self.expenditure)
            return total_expenditure/num_people
        except ZeroDivisionError:
            return 0
    
    def remove(self, key: str) -> None:
        if key in self.expenditure:
            del self.expenditure[key]
            
        if key in self.shared_expenditure:
            del self.shared_expenditure[key]

        
    def resolve_expenses(self) -> list:
        avg_expenditure = self.avg_expenditure()

        debts = {person: expense - avg_expenditure for person, expense in self.expenditure.items()}

        for creditor, debtor_value_dict in self.shared_expenditure.items():
            for debtors, value in debtor_value_dict.items():
                shared_expense = value / (len(debtors) + 1)
                creditor_balance = debts.get(creditor, 0)
                debts[creditor] = creditor_balance + shared_expense

                for debtor in debtors:
                    debtor_balance = debts.get(debtor, 0)
                    debts[debtor] = debtor_balance - shared_expense

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
    Usage: /start
    """
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="""I'm SplitLaterBot, here to help calculate who you should pay after a group evening out!\n\nType /help to view all commands"""
    )

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Clears all records and users
    Usage: /clear
    """
    context.chat_data.clear()
    await update.message.reply_text(
        f"All records have been cleared!"
    )

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays all commands and their usages
    Usage: /help
    """
    preamble = "Here are all the commands available to you!\n\n"
    # start_message = "/start: Restarts the session and clears all previous record\nUsage: /start\n\n"
    # help_message = "/help: Displays all commands\nUsage: /help\n\n"
    include_message = "/include: Adds users to be included in the receipt. Always start with this!\nUsage: /include @john @adam\n\n"
    add_message = "/add: Adds an expense. Can be used to explicitly split cost with several others\nUsage: /add John 10 or /add @john 10 @adam\n\n"
    view_message = "/view: Displays the expenses of all individuals\nUsage: /view\n\n"
    resolve_message = "/resolve: Calculates which individual needs to pay who\nUsage: /resolve\n\n"
    clear_message = "/clear: Clears all previous records\nUsage: /clear\n\n"
    logs_message = "/logs: Displays all transactions since the start\nUsage: /logs\n\n"
    note_message = "*Note: When encountering an error, please re-enter the instruction and do not edit the previous one.\n\n"
    credits = "Made by: @nelthm"

    await update.message.reply_text(
        f"{preamble}{include_message}{add_message}{view_message}{resolve_message}{clear_message}{logs_message}{note_message}{credits}"
    )

async def include(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Initializes all included users to zero
    Usage: /include @user1 @user2
    """
    users = ' '.join(context.args)
    num_users = len(context.args)
    regex = handle_regex(num_users)

    if re.fullmatch(regex, users):
        context.chat_data.include(users)
        await update.message.reply_text(f"Alright! We detected {num_users}. You may now add transactions via the add command!")
    else:
        await update.message.reply_text("Error: the format should be /include @name @name @name...")

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Adds an expense made by the user
    Usage: /add @person value *
    Example: /add @john 10 @other
    """
    if len(context.chat_data.users) == 0:
        await update.message.reply_text("Error: Please use the /include command to add users first!")
        return

    others = None
    if len(context.args) > 2:
        try:
            person = context.args[0]
            value = context.args[1]
            others = context.args[2:]
        except:
            await update.message.reply_text("Error: the format should be '/add @name value @other1 @other2...'.")
            pass
    else:
        try:
            person = ' '.join(context.args[:-1])
            value = context.args[-1]
        except: # User enters < and > 2 arguments
            await update.message.reply_text("Error: the format should be '/add @name value @other_name'.")
            pass

    try:
        context.chat_data.update_expenditure(person, float(value), others)
        context.chat_data.update_log(update.message.date, update.message.text)
        await update.message.reply_text("Added!")
    except ValueError: # non-numeric value found as expense argument
        await update.message.reply_text("Error: non-numeric value for expense found.")
        pass

async def view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Views the cumulative expenditure of all persons
    Usage: /view
    """
    equal_preamble = 'Expenses intended to split equally:\n'
    equal_message = ''
    for person, expense in context.chat_data.expenditure.items():
        equal_message += f"{person} has paid {expense}\n"
    
    special_preamble = 'Expenses intended to split amongst certain individuals:\n'
    special_message = ''
    for creditor, debtor_value_dict in context.chat_data.shared_expenditure.items():
        for debtors, value in debtor_value_dict.items():
            debtors = ', '.join(debtors)
            special_message += f'{creditor} paid {value} to be shared with {debtors}\n'

    if equal_message != '' and special_message != '':
        await update.message.reply_text(f"{equal_preamble}{equal_message}\n\n{special_preamble}{special_message}")
    elif equal_message != '' and special_message == '':
        await update.message.reply_text(f"{equal_preamble}{equal_message}\n\n{special_preamble}None")
    elif equal_message == '' and special_message != '':
        await update.message.reply_text(f"{equal_preamble}None\n\n{special_preamble}{special_message}")
    else:
        await update.message.reply_text(f"No records have been added!")


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
    except:
        await update.message.reply_text(f"Either no individuals added, no expenses added, or everyone has spent equal amounts.")


async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays all transactions since epoch
    Usage: /logs
    """
    message = ''
    for log in context.chat_data.logs:
        message += f"{log}\n"

    if message == '':
        await update.message.reply_text(f"No records have been added.")
    else:
        await update.message.reply_text(message)

async def _unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Internal use for unknown command handling
    """
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Error: Either a wrong command has been entered, or a previous message has been edited. Please retype as opposed to editing the previous message :)")


# ================= HELPER FUNCTIONS =================
def handle_regex(num_handles):
    # The regex pattern for a Telegram handle
    handle_pattern = r'@[\w\d_]+'

    # Construct the full regex pattern for the specified number of handles
    full_pattern = fr'{handle_pattern}(\s{handle_pattern}){{{num_handles - 1}}}'

    return full_pattern
# ====================================================


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
    include_handler = CommandHandler('include', include, filters=~filters.UpdateType.EDITED_MESSAGE)
    help_handler = CommandHandler('help', help, filters=~filters.UpdateType.EDITED_MESSAGE)
    add_handler = CommandHandler('add', add, filters=~filters.UpdateType.EDITED_MESSAGE)
    view_handler = CommandHandler('view', view, filters=~filters.UpdateType.EDITED_MESSAGE)
    resolve_handler = CommandHandler('resolve', resolve, filters=~filters.UpdateType.EDITED_MESSAGE)
    clear_handler = CommandHandler('clear', clear, filters=~filters.UpdateType.EDITED_MESSAGE)
    logs_handler = CommandHandler('logs', logs, filters=~filters.UpdateType.EDITED_MESSAGE)

    # Add core-function handlers
    application.add_handler(start_handler)
    application.add_handler(include_handler)
    application.add_handler(help_handler)
    application.add_handler(add_handler)
    application.add_handler(view_handler)
    application.add_handler(resolve_handler)
    application.add_handler(clear_handler)
    application.add_handler(logs_handler)
                            
    # Setup and add handlers
    unknown_handler = MessageHandler(filters.COMMAND, _unknown)
    application.add_handler(unknown_handler)

    # inline_query_handler = InlineQueryHandler(inline_query)
    # application.add_handler(inline_query_handler)
    
    # Start the webhook
    # application.run_webhook(listen="0.0.0.0",
    #                       port=int(PORT),
    #                       url_path=TOKEN,
    #                       webhook_url=f"https://{NAME}.herokuapp.com/{TOKEN}")
    
    application.run_polling()
    
