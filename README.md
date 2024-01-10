# Introduction

This creation of this Telegram Bot was motivated after attending several outings which resulted in payment confusion amongst the group.

The bot features a number of commands to aid in settling debts. All expenses added into the receipt is assumed to be split evenly amongst members included. But special expenses meant to be split amongst a subgroup can be specified as well!

### Note

The Telegram is not currently being hosted, you may refer to the instructions below to test, or host it on your own!

# Installing (Dev)

> To begin, you'll need an Access Token. To generate an Access Token, you have to talk to [@BotFather](https://telegram.me/botfather) and follow a few simple steps (described [here](https://core.telegram.org/bots/features#botfather)).

You can install the Telegram bot via

```code: shell
$ git clone https://github.com/nealetham/split-later.git
$ cd split-later
$ pip install requirements.txt
```

Open up the `.env` file, and replace `<BOT_TOKEN>` with your own Access Token.

To start the bot, just run

```code: shell
$ python bot.py
```

You may now interact with the bot on Telegram!

# Hosting

In the other branch of the repository, the `bot.py` has been edited with the sole purpose of hosting on AWS Lambda.

References - [Hosting on AWS Lambda](https://github.com/havebeenfitz/om-random-coffee-bot/wiki/Hosting-the-bot-on-AWS-Lambda)
