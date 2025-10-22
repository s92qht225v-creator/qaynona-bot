#!/usr/bin/env python3
"""Check which groups the bot can access"""

import asyncio
from telegram import Bot
from config import Config

# Group IDs from your earlier list
GROUP_IDS = [
    -1003175985458,  # 💞ailem NAZARBEK FILIAL
    -1003147939740,  # 💞ailem SERGELI FILIAL
    -1002989401855,  # Penuar_Premum_N1
    -1002974824831,  # Test group
    -1002782503689,  # 💞ailem CHILONZOR FILIAL
    -1002749223529,  # 💞ailem SAMARQAND FILIAL
    -1002740541141,  # 💞ailem CHICHIQ FILIAL
    -1002601180669,  # Story Time
    -1002446958271,  # OnlineMadishop
    -1002201160050,  # Somga Yuan
    -1002102475368,  # Yuan sotish hizmati
    -1002003969374,  # Omina Shop
    -1001927929479,  # 𝚂𝚊𝚍𝚒𝚗𝚊 𝚘𝚗𝚕𝚊𝚢𝚗 𝚜𝚑𝚘𝚙
    -1001904727052,  # Kimga Yuan
    -1001771374906,  # Serya tavarlar
    -1001502125126,  # Sadi store Unversal Shop
    -1001417119670,  # 𝙋𝙊𝙎𝙏𝙀𝙇 𝙎𝙊𝙆𝙇𝘼𝘿 𝘾𝙃𝘼𝙏
    -1001279832948,  # Бепул ХИТОЙ тили
    -4759367262,     # Ali & Шерзодбек Балтабаев
]

async def main():
    bot = Bot(token=Config.BOT_TOKEN)

    accessible = []
    not_accessible = []

    print("🔍 Checking bot access to groups...\n")

    for group_id in GROUP_IDS:
        try:
            chat = await bot.get_chat(group_id)
            print(f"✅ {chat.title} (ID: {group_id})")
            accessible.append((group_id, chat.title))
        except Exception as e:
            print(f"❌ ID: {group_id} - {str(e)[:50]}")
            not_accessible.append(group_id)

    print(f"\n📊 Summary:")
    print(f"   Accessible: {len(accessible)}")
    print(f"   Not accessible: {len(not_accessible)}")

    if not_accessible:
        print(f"\n⚠️  Bot needs to be re-added to {len(not_accessible)} groups")

if __name__ == "__main__":
    asyncio.run(main())
