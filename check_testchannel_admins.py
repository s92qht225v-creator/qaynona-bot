#!/usr/bin/env python3
import asyncio
from telegram import Bot
from config import Config

async def main():
    bot = Bot(token=Config.BOT_TOKEN)
    await bot.initialize()

    chat_id = -1002914389106  # testchannel Chat

    admins = await bot.get_chat_administrators(chat_id)
    print('Admins in testchannel Chat:')
    for admin in admins:
        username = admin.user.username if admin.user.username else "no username"
        print(f'  - {admin.user.first_name} (@{username}) - ID: {admin.user.id}')

    await bot.shutdown()

asyncio.run(main())
