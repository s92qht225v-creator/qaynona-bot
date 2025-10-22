#!/usr/bin/env python3
"""Check bot permissions in Story Time group"""

import asyncio
from telegram import Bot
from config import Config

STORY_TIME_ID = -1002601180669

async def main():
    bot = Bot(token=Config.BOT_TOKEN)

    try:
        # Initialize bot
        await bot.initialize()

        # Get bot info in the group
        bot_member = await bot.get_chat_member(STORY_TIME_ID, bot.id)

        print(f"Bot status: {bot_member.status}")
        print(f"Can delete messages: {bot_member.can_delete_messages if hasattr(bot_member, 'can_delete_messages') else 'N/A'}")
        print(f"Can restrict members: {bot_member.can_restrict_members if hasattr(bot_member, 'can_restrict_members') else 'N/A'}")

        # Get chat info
        chat = await bot.get_chat(STORY_TIME_ID)
        print(f"\nChat title: {chat.title}")
        print(f"Chat type: {chat.type}")
        print(f"Chat username: {chat.username}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
