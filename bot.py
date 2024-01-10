import os, logging, re
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
  MessageHandler,
  ApplicationBuilder,
  ContextTypes,
  CommandHandler,
  filters,
)

# Define custom class for chat_data
class ChatData:
    def __init__(self) -> None:
        self.users = list()
        self.expenditure = dict()
        self.shared_expenditure = dict()

    def clear(self) -> None:
        self.users.clear()
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
        else: # self.shared_expenditure = {creditor: {debtors: value, debtors1: value}}
            debtor_value_dict = self.shared_expenditure.get(key, {})  # gets dict of debtors and values
            debtor_value_dict[frozenset(others)] = debtor_value_dict.get(frozenset(others), 0) + value # gets value and increment
            self.shared_expenditure[key] = debtor_value_dict
    
    def avg_expenditure(self) -> float: 
        try:
            # Excludes special expenditure
            total_expenditure = sum(self.expenditure.values())
            num_people = len(self.expenditure)
            return total_expenditure/num_people
        except ZeroDivisionError:
            return 0
    
    def resolve_expenses(self) -> list:
        avg_expenditure = self.avg_expenditure()

        debts = {person: expense - avg_expenditure for person, expense in self.expenditure.items()}

        # Account for special expenditures
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
    preamble = "Here are all the commands available! Commands without any examples can be used as is, the other more complicated ones will be shown!\n\n"
    # start_message = "/start: Restarts the session and clears all previous record\nUsage: /start\n\n"
    # help_message = "/help: Displays all commands\nUsage: /help\n\n"
    include_message = "/include: Add users to be included in the receipt (as many as you want!). Always start with this!\n\ne.g.\nJohn, Adam and Sally agreed to share costs\n/include @john @adam @sally\n"
    add_message = "/add: Add expense. Names can be added at the end to specify that it is to be split amongst them.\n\ne.g.\nJohn paid $10, to be split amongst everyone\n/add John 10\n\nJohn paid $10, and the cost is to be split among John and Adam\n/add @john 10 @adam\n"
    view_message = "/view: Displays all expenses\n"
    resolve_message = "/resolve: Displays which individual needs to pay who\n"
    clear_message = "/clear: Clears all records\n"
    note_message = "\n*Note: When encountering an error, please re-enter the instruction and not edit the previous one.\n\n"
    credits = "Made by @nelthm"
    separator = "=====================================\n"

    await update.message.reply_text(
        f"{preamble}{separator}{include_message}{separator}{add_message}{separator}{view_message}{separator}{resolve_message}{separator}{clear_message}{separator}{note_message}{credits}"
    )

async def include(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Initializes all included users to zero
    Usage: /include @user1 @user2
    """
    users = ' '.join(context.args)
    num_users = len(context.args)

    if include_regex(num_users, users):
        context.chat_data.include(context.args)
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
            person_value = ' '.join(context.args[0:2])
            person = context.args[0]
            value = context.args[1]            
            others = context.args[2:]
            if not add_regex(person_value) or not include_regex(len(others), ' '.join(others)):
                raise Exception
            if person not in context.chat_data.users:
                raise Exception
            
            for user in others:
                if user not in context.chat_data.users:
                    raise Exception
                
        except:
            await update.message.reply_text("Error: the format should be '/add @name value @other1 @other2...'. Only specify users you've added using /include!")
            return
    else:
        try:
            person_value = ' '.join(context.args[0:2])
            person = context.args[0]
            value = context.args[-1]
            if not add_regex(person_value):
                raise Exception
            
            if person not in context.chat_data.users:
                raise Exception

        except: # User enters < and > 2 arguments
            await update.message.reply_text("Error: the format should be '/add @name value @other_name'. Only specify users you've added using /include!")
            return

    try:
        context.chat_data.update_expenditure(person, float(value), others)
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


async def _unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Internal use for unknown command handling
    """
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Error: Either a wrong command has been entered, or a previous message has been edited.\nPlease retype rather than editing the previous message :)")


# ================= HELPER FUNCTIONS =================
    
def include_regex(num_handles: int, users: str) -> bool:
    # The regex pattern for a Telegram handle
    handle_pattern = r'@[\w\d_]+'
    full_pattern = fr'{handle_pattern}(\s{handle_pattern}){{{num_handles - 1}}}'

    return re.fullmatch(full_pattern, users)

def add_regex(args: str) -> bool:
    # Regex pattern for @user numeral
    handle_pattern = r'@(\S+)\s+(\d+)$'
    return re.fullmatch(handle_pattern, args)

# ====================================================


if __name__ == '__main__':
    # Initialize environment variables
    load_dotenv()
    TOKEN = os.environ['BOT_TOKEN']

    # Build application
    context_types = ContextTypes(chat_data=ChatData)
    application = ApplicationBuilder().token(TOKEN).context_types(context_types).build()

    # Enable Logging
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Setup core-function handlers
    start_handler = CommandHandler('start', start, filters=~filters.UpdateType.EDITED_MESSAGE)
    include_handler = CommandHandler('include', include, filters=~filters.UpdateType.EDITED_MESSAGE)
    help_handler = CommandHandler('help', help, filters=~filters.UpdateType.EDITED_MESSAGE)
    add_handler = CommandHandler('add', add, filters=~filters.UpdateType.EDITED_MESSAGE)
    view_handler = CommandHandler('view', view, filters=~filters.UpdateType.EDITED_MESSAGE)
    resolve_handler = CommandHandler('resolve', resolve, filters=~filters.UpdateType.EDITED_MESSAGE)
    clear_handler = CommandHandler('clear', clear, filters=~filters.UpdateType.EDITED_MESSAGE)
    core_handlers = [start_handler, include_handler, help_handler, add_handler, view_handler, resolve_handler, clear_handler]

    # Add core-function handlers
    application.add_handlers(core_handlers)
                            
    # Setup and add handlers
    unknown_handler = MessageHandler(filters.COMMAND, _unknown)
    application.add_handler(unknown_handler)

    application.run_polling()
    
