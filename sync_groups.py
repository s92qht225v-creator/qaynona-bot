#!/usr/bin/env python3
"""Sync accessible groups to database"""

import asyncio
from telegram import Bot
from config import Config
from database import get_or_create_tenant

# Group IDs that the bot can access
GROUP_IDS = [
    -1003175985458,  # 💞ailem NAZARBEK FILIAL
    -1003147939740,  # 💞ailem SERGELI FILIAL
    -1002989401855,  # 💋𝗝𝗼𝘇𝗶𝗯𝗮𝗹𝗶_𝗣𝗲𝗻𝘂𝗮𝗿𝗹𝗮𝗿💋
    -1002974824831,  # Test group
    -1002782503689,  # 💞ailem CHILONZOR FILIAL
    -1002749223529,  # 💞ailem SAMARQAND FILIAL
    -1002740541141,  # 💞ailem CHICHIQ FILIAL
    -1002601180669,  # Story Time
    -1002446958271,  # OnlineMadishop
    -1002201160050,  # Somga Yuan
    -1002102475368,  # Yuan sotish hizmati
    -1001904727052,  # Kimga Yuan
    -1001771374906,  # Serya tavarlar
    -1001502125126,  # Sadi store Unversal Shop
    -1001417119670,  # 𝙋𝙊𝙎𝙏𝙀𝙇 𝙎𝙆𝙇𝘼𝘿 𝘾𝙃𝘼𝙏
    -1001279832948,  # Бепул ХИТОЙ тили
    -4759367262,     # Ali & Шерзодбек Балтабаев
]

async def main():
    bot = Bot(token=Config.BOT_TOKEN)

    print("🔄 Syncing groups to database...\n")

    added = 0
    skipped = 0

    for group_id in GROUP_IDS:
        try:
            chat = await bot.get_chat(group_id)

            # Get or create tenant - this will add to database if not exists
            tenant = get_or_create_tenant(group_id, chat.title, chat.type)

            print(f"✅ {chat.title}")
            added += 1

        except Exception as e:
            print(f"❌ ID: {group_id} - {str(e)[:50]}")
            skipped += 1

    print(f"\n📊 Summary:")
    print(f"   Added/Verified: {added}")
    print(f"   Skipped: {skipped}")
    print(f"\n✅ Database sync complete!")

if __name__ == "__main__":
    asyncio.run(main())
