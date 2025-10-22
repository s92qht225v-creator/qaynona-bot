#!/usr/bin/env python3
"""Check bot admin status in all groups"""

import asyncio
from telegram import Bot
from config import Config
import sqlite3

async def main():
    bot = Bot(token=Config.BOT_TOKEN)
    await bot.initialize()

    # Get all groups from database
    conn = sqlite3.connect('multi_tenant_moderation.db')
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id, chat_title FROM tenants WHERE is_active = 1 ORDER BY chat_title")
    groups = cursor.fetchall()
    conn.close()

    print("Checking bot permissions in all groups...\n")

    admin_groups = []
    member_groups = []

    for chat_id, chat_title in groups:
        try:
            bot_member = await bot.get_chat_member(chat_id, bot.id)
            status = bot_member.status

            if status in ['administrator', 'creator']:
                admin_groups.append((chat_title, chat_id))
                print(f"✅ ADMIN: {chat_title}")
            else:
                member_groups.append((chat_title, chat_id))
                print(f"❌ MEMBER: {chat_title}")
        except Exception as e:
            print(f"⚠️  ERROR: {chat_title} - {str(e)[:50]}")

    print(f"\n📊 Summary:")
    print(f"   Admin in: {len(admin_groups)} groups")
    print(f"   Member in: {len(member_groups)} groups")

    if member_groups:
        print(f"\n⚠️  Bot needs admin rights in these {len(member_groups)} groups:")
        for title, chat_id in member_groups:
            print(f"   - {title} (ID: {chat_id})")

    await bot.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
