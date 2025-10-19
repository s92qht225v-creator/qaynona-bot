"""
Language translations for the bot
Supports: Uzbek (uz) only
"""

TRANSLATIONS = {
    'uz': {
        # Start menu
        'start_greeting': 'Assalomu alaykum, men guruh QAYNONA siman!',
        'start_description': 'Men sizning guruhingizdagi yagona nazoratchi va detektiv bo\'laman',
        'start_instructions': 'Men qiladigan ishlar:',
        'start_list_1': '• Yangi kelganlarga "Xush kelibsiz xabari!" yuboraman',
        'start_list_2': '• Agar 2 daqiqa ichida bo\'tligini isbotlamasa, chiqarib yuboraman',
        'start_list_3': '• Kirdi chiqdi va boshqa keraksiz xabarlarni o\'chiraman',
        'start_list_4': '• Gap tushunmaganlarni: "Ogohlintaraman!" va gap qayatarishni davom etsa, ban qilaman',
        'start_list_5': '• Xavfli fayllar, sticker, gif, ovozli, video — hammasini nazorat qilib turaman',
        'start_list_6': '• Qoidalarni eslataman va "kim qoidalarni qayta qayta buzsa" jimlataman',
        'start_list_7': '• Kim qancha gapirganini ham hisoblab boraman',
        'start_footer': 'Xullas, men bor guruhda:',
        'start_footer_text': '• Tartib va intizom bo\'ladi lekin spam bo\'lmaydi',
        'start_commands_header': '👉 Meni guruhingizga qo\'shing va admin qiling (xabarlarni o\'chirish huquqini berishni unutmang) 👈',
        'start_commands_text': 'Barcha buyruq va funksiyalarni ko\'rish uchun quyidagi \'Barcha buyruqular\' tugmasini bosing',
        'add_to_group': '➕ Meni guruhga qo\'shing',
        'show_help': '📚 Barcha buyruqlar',
        'contact_admin': '👤 Admin bilan bog\'lanish',

        # Help menu
        'help_title': '📚 Asosiy buyruqlar',
        'help_admin_group': '👮 Administrator buyruqlari (guruh ichida foydalanish uchun):',
        'help_admin_private': '💬 Administrator buyruqlari (bot ichida foydalanish uchun):',
        'help_users': '👥 Foydalanuvchi buyruqlari:',
        'help_back_menu': '⬅️ Asosiy menyuga qaytish',
        'back': '◀️ Oldingi menyuga qaytish',

        # Group commands
        'help_ban': '/ban - Foydalanuvchini bloklash',
        'help_kick': '/kick - Foydalanuvchini haydash',
        'help_mute': '/mute - Foydalanuvchini ovozsizlash',
        'help_unmute': '/unmute - Ovozni yoqish',
        'help_warn': '/warn - Foydalanuvchini ogohlantirish',
        'help_unwarn': '/unwarn - Ogohlantirishni olib tashlash',
        'help_unban': '/unban - Foydalanuvchini blokdan chiqarish',

        # Private chat commands
        'help_settings': 'Bot va guruh sozlamalari',
        'help_stats': 'Guruh statistikasi',
        'help_setrules_button': 'Guruh qoidalarini o\'rnatish',
        'help_seerules_button': 'Guruh qoidalarini ko\'rish',
        'help_setwelcome_button': 'Xush kelibsiz xabarini o\'rnatish',
        'help_seewelcome_button': 'Xush kelibsiz xabarini ko\'rish',
        'help_setfilter_button': 'Filtrga so\'z qo\'shish',
        'help_removefilter_button': 'Filtrdagi so\'zni o\'chirish',
        'help_viewfilters_button': 'Filtrlangan so\'zlarni ko\'rish',

        # User commands
        'help_rules': '/rules - Guruh qoidalarini ko`rish',
        'help_info': '/info - Sizning holatingiz',
        'help_help': '/help - Ushbu yordamni ko`rsatish',

        # Settings menu
        'settings_title': '⚙️ **Guruh Sozlamalari**',
        'settings_protection': 'HIMOYA',
        'settings_cleanup': 'TOZALASH',
        'settings_quick': 'TEZKOR SOZLAMALAR',
        'settings_hint': 'Sozlamalarni yoqish yoki o\'chirish uchun pastdagi tugmalarni bosing.',
        'select_max_warnings': '⚠️ **Ban qilishdan oldin maksimal ogohlantirishlar sonini tanlang:**',
        'max_warnings_set': '✅ Maksimal ogohlantirishlar soni {} ga o\'rnatildi',
        'verification': '🔐 Bot emasligini tekshirish',
        'flood_control': '🌊 To\'fon funksiyasi',
        'welcome_msg': '👋 Xush kelibsiz xabari',
        'word_filter': '🚫 So\'z filtr funksiyasi',
        'antilink': '🔗 Havola yuborishni taqiqlash',
        'antifile': '📎 Fayl yuborishni taqiqlash',
        'media_photo': '📷 Rasm yuborishni taqiqlash',
        'media_video': '🎥 Video yuborishni taqiqlash',
        'media_audio': '🎵 Audio yuborishni taqiqlash',
        'media_voice': '🎤 Ovozli xabar yuborishni taqiqlash',
        'media_sticker': '🎭 Stiker yuborishni taqiqlash',
        'media_animation': '🎞️ Animatsiya yuborishni taqiqlash',
        'media_videonote': '🎬 Video xabar yuborishni taqiqlash',
        'max_warnings': '⚠️ Maksimal Ogohlantirishlar',
        'delete_join': '🚫 Kirish Xabarlarini O\'chirish',
        'delete_leave': '🚫 Chiqish Xabarlarini O\'chirish',
        'delete_service': '🚫 Xizmat xabarlarini o\'chirish',

        # Stats menu
        'stats_title': '📊 **Guruh Statistikasi**',
        'global_admin_only': '⛔ Bu buyruq faqat global administratorlar uchun.',
        'global_stats_title': 'Global Statistika',
        'total_groups': 'Jami guruhlar',
        'monthly_users': 'Oylik foydalanuvchilar',
        'groups_list': 'Guruhlar ro\'yxati',
        'language': 'Til',
        'group': 'Guruh',
        'member_activity': '👥 **A\'zolar Faolligi:**',
        'joined_7d': 'Qo\'shildi (7 kun)',
        'left_7d': 'Ketdi (7 kun)',
        'net_growth_7d': 'Aniq o\'sish (7k)',
        'joined_30d': 'Qo\'shildi (30 kun)',
        'left_30d': 'Ketdi (30 kun)',
        'net_growth_30d': 'Aniq o\'sish (30k)',
        'database': '**Ma\'lumotlar Bazasi:**',
        'total_warnings': 'Jami Ogohlantirishlar',
        'total_filters': 'Filtrlangan So\'zlar',
        'total_actions': 'Moderatsiya Harakatlari (jami)',
        'recent_actions': '**Yaqinda Harakatlar (oxirgi 24s):**',
        'bans': 'Bloklash',
        'kicks': 'Haydash',
        'mutes': 'Ovozsizlash',
        'warnings': 'Ogohlantirishlar',
        'current_session': '**Joriy Sessiya:**',
        'active_verifications': 'Faol Tekshiruvlar',
        'tracked_users': 'Kuzatilgan Foydalanuvchilar (to\'fon)',

        # Commands
        'only_private': '❌ Bu buyruq faqat bot bilan shaxsiy chatda ishlatilishi mumkin.\nIltimos, statistikani ko\'rish uchun menga shaxsiy xabar yuboring.',
        'select_group_stats': '📊 Statistikani ko\'rish uchun guruhni tanlang:',
        'select_group_settings': '🤖 **Boshqarish uchun guruhni tanlang:**\n\nQaysi guruh sozlamalarini sozlamoqchisiz:',
        'back_to_menu': '◀️ Oldingi menyuga qaytish',
        'settings_private_button': '⚙️ Sozlamalarni shaxsiy ochish',
        'settings_private_msg': '🔒 Guruh chatini toza saqlash uchun, sozlamalar endi shaxsiy chatda boshqariladi.\n\nSozlamalarni ochish uchun quyidagi tugmani bosing:',
        'no_admin_groups': '❌ Siz men boshqaradigan guruhlarda administrator emassiz.\n\nMeni guruhga qo\'shing va o\'zingizni admin qiling.',
        'no_admin_groups_add': '❌ Siz men boshqaradigan guruhlarda administrator emassiz.\n\nMeni guruhga qo\'shing va o\'zingizni admin qiling.',

        # Info command
        'info_title': '👤 Foydalanuvchi Ma\'lumoti',
        'info_name': 'Ism',
        'info_user_id': 'Foydalanuvchi ID',
        'info_username': 'Foydalanuvchi nomi',
        'info_status': 'Holat',
        'info_warnings': 'Ogohlantirishlar',
        'info_is_bot': 'Bot',
        'info_tenant_id': 'Guruh ID',
        'info_yes': 'Ha',
        'info_no': 'Yo\'q',
        'info_none': 'Yo\'q',

        # Rules
        'default_rules_title': '📜 Guruh Qoidalari',
        'default_rules': '''1. Barcha a'zolarga hurmat bilan muomala qiling
2. Spam yoki to'fon qilmang
3. Haqoratli til ishlatmang
4. Mavzuda qoling
5. Telegram shartnomasiga amal qiling

Qoidalarni buzish ogohlantirish yoki blokka olib kelishi mumkin.''',
        'seerules_title': '📜 O\'rnatilgan Qoidalar',
        'seerules_current': '**Guruh:** {group_title}\n\n{rules_text}',
        'seerules_not_set': '❌ Bu guruh uchun maxsus qoidalar o\'rnatilmagan.\n\n`/setrules` yordamida o\'rnating yoki `/rules` yordamida standart qoidalarni ko\'ring.',

        # Rate limiting
        'rate_limit_wait': '⏳ Iltimos, bu buyruqni qayta ishlatishdan oldin {remaining}s kuting.',

        # Permission errors
        'admin_only': '⛔ Bu buyruqni ishlatish uchun administrator bo\'lishingiz kerak.',
        'group_only': '❌ Bu buyruq faqat guruhlarda ishlatilishi mumkin.',
        'no_permission': '⛔ Siz bu guruhda administrator emassiz.',
        'permission_error': '❌ Xato: Sizning guruhda huquqlaringizni tasdiqlab bo\'lmadi.\n\nSabablar: Bot guruhda bo\'lmasligi yoki sizning admin huquqlaringiz yo\'qligi mumkin.',

        # Moderation actions - Ban
        'ban_reply_required': '❌ Foydalanuvchini bloklash uchun xabarga javob bering.',
        'ban_admin_error': '❌ Administratorni bloklash mumkin emas!',
        'user_banned': '🔨 **Bloklandi** {user}\n\n**Sabab:** {reason}',
        'user_banned_no_reason': '🔨 **Bloklandi** {user}',
        'ban_failed': '❌ Foydalanuvchini bloklashda xatolik: {error}',

        # Moderation actions - Unban
        'unban_usage': '❌ Foydalanish:\n`/unban` (xabarga javob sifatida)\nyoki `/unban <user_id>`',
        'user_unbanned': '✅ **Blokdan chiqarildi** {user}\n\nEndi guruhga qayta qo\'shilishi mumkin.',
        'unban_failed': '❌ Foydalanuvchini blokdan chiqarishda xatolik: {error}',

        # Moderation actions - Kick
        'kick_reply_required': '❌ Foydalanuvchini haydash uchun xabarga javob bering.',
        'kick_admin_error': '❌ Administratorni haydash mumkin emas!',
        'user_kicked': '👢 **Haydalgan** {user}',
        'kick_failed': '❌ Foydalanuvchini haydashda xatolik: {error}',

        # Moderation actions - Mute
        'mute_reply_required': '❌ Foydalanuvchini ovozsizlash uchun xabarga javob bering.\nFoydalanish: `/mute <daqiqalar>`',
        'mute_admin_error': '❌ Administratorni ovozsizlash mumkin emas!',
        'mute_positive_duration': '❌ Davomiyligi musbat bo\'lishi kerak!',
        'mute_invalid_duration': '❌ Noto\'g\'ri davomiyligi. Foydalanish: `/mute <daqiqalar>`',
        'user_muted': '🔇 **Ovozsizlashtirildi** {user} {duration} daqiqaga',
        'mute_failed': '❌ Foydalanuvchini ovozsizlashda xatolik: {error}',

        # Moderation actions - Unmute
        'unmute_reply_required': '❌ Foydalanuvchini ovozlash uchun xabarga javob bering.',
        'user_unmuted': '🔊 **Ovozli** {user}',
        'unmute_failed': '❌ Foydalanuvchini ovozlashda xatolik: {error}',

        # Moderation actions - Warn
        'warn_reply_required': '❌ Foydalanuvchini ogohlantirish uchun xabarga javob bering.',
        'warn_admin_error': '❌ Administratorni ogohantirish mumkin emas!',
        'user_warned_banned': '⚠️ {user} **{max_warnings}** ogohlantirishga yetdi va **bloklandi**!',
        'user_warned': '⚠️ **Ogohlangtirildi** {user}\n\n**Ogohlantirish:** {warnings}/{max_warnings}\n**Sabab:** {reason}',
        'warn_failed_ban': '❌ Foydalanuvchini bloklashda xatolik: {error}',

        # Moderation actions - Unwarn
        'unwarn_reply_required': '❌ Ogohlantirishni olib tashlash uchun xabarga javob bering.',
        'warning_removed': '✅ {user} dan ogohlantirish olib tashlandi\n\n**Qolgan ogohlantirishlar:** {warnings}/{max_warnings}',
        'no_warnings': '{user} da olib tashlanadigan ogohlantirishlar yo\'q.',

        # Moderation actions - Warnings info
        'warnings_info': '📊 **Ogohlantirishlar** {user}\n\n**Ogohlantirishlar:** {warnings}/{max_warnings}',

        # Word filter
        'filter_usage': '❌ Foydalanish: `/filter <so\'z yoki ibora>`',
        'filter_added': '✅ `{word}` filtr ro\'yxatiga qo\'shildi.',
        'filter_exists': '⚠️ `{word}` allaqachon filtr ro\'yxatida.',
        'unfilter_usage': '❌ Foydalanish: `/unfilter <so\'z yoki ibora>`',
        'filter_removed': '✅ `{word}` filtr ro\'yxatidan olib tashlandi.',
        'filter_not_found': '⚠️ `{word}` filtr ro\'yxatida yo\'q.',
        'no_filters': '📝 Hozirda hech qanday so\'z filtrlanmagan.',
        'filtered_words_title': '🚫 **Filtrlangan So\'zlar:**\n\n{filter_list}',
        'word_filtered': '🚫 {user} dan xabar o\'chirildi (filtrlangan so\'z)',

        # Purge
        'purge_usage': '❌ Foydalanish: `/purge <raqam>`',
        'purge_range_error': '❌ Iltimos, 1 dan 100 gacha raqam kiriting.',
        'purge_invalid_number': '❌ Noto\'g\'ri raqam.',
        'purge_failed': '❌ Xabarlarni o\'chirishda xatolik: {error}',

        # Rules
        'setrules_usage': '❌ Foydalanish: `/setrules <qoidalar matni>`\n\nYoki menga shaxsiy xabar yuboring va qoidalarni interaktiv ravishda o\'rnating.',
        'rules_updated': '✅ Guruh qoidalari muvaffaqiyatli yangilandi!',
        'setrules_private_only': '❌ Bu buyruq faqat bot bilan shaxsiy chatda ishlatilishi mumkin.\n\nFoydalanish: Menga shaxsiy xabar yuboring va `/setrules` yozing, so\'ngra qoidalar matnini yuboring.',
        'setrules_no_groups': '❌ Siz men boshqaradigan guruhlarda administrator emassiz.',
        'setrules_help': '📋 **Guruh qoidalarini o\'rnatish:**\n\nQaysi guruh uchun qoidalarni o\'rnatmoqchisiz? Guruhni tanlang va keyin qoidalar matnini yuboring.\n\nYoki guruhda bevosita `/setrules <qoidalar matni>` buyrug\'ini ishlatishingiz mumkin.',
        'setrules_prompt': '📝 **{group} uchun qoidalarni yuboring:**\n\nKeyingi xabaringiz bu guruh uchun qoidalar sifatida o\'rnatiladi.',
        'setrules_success': '✅ **Qoidalar o\'rnatildi!**\n\n**Guruh:** {group}\n\n**Yangi qoidalar:**\n{rules}',

        # Welcome message
        'setwelcome_usage': '❌ Foydalanish: `/setwelcome <xabar matni>`\n\nYoki menga shaxsiy xabar yuboring va xush kelibsiz xabarini interaktiv ravishda o\'rnating.\n\n**Maxsus teglar:**\n`[user]` - Foydalanuvchi ismi\n`[group]` - Guruh nomi\n`[time]` - Joriy vaqt',
        'welcome_set_preview': '✅ **Xush kelibsiz xabari o\'rnatildi!**\n\n**Ko\'rinish:**\n{preview}',
        'setwelcome_select_group': '📝 **Qaysi guruh uchun xush kelibsiz xabarini o\'rnatmoqchisiz?**',
        'viewwelcome_title': '👋 **Joriy Xush Kelibsiz Xabari**',
        'viewwelcome_current': '**Guruh:** {group_title}\n\n**Xabar:**\n{welcome_message}\n\n**Maxsus teglar:**\n`[user]` - Foydalanuvchi ismi\n`[group]` - Guruh nomi\n`[time]` - Joriy vaqt',
        'viewwelcome_not_set': '❌ Bu guruh uchun xush kelibsiz xabari o\'rnatilmagan.\n\n`/setwelcome` yordamida o\'rnating.',
        'viewwelcome_disabled': '⚠️ Xush kelibsiz xabari o\'chirilgan.\n\nUni sozlamalarda yoqing.',
        'welcome_duration': 'Xush kelibsiz xabarini ko\'rsatish',
        'welcome_duration_seconds': 'soniya',
        'select_welcome_duration': '⏱️ **Xush kelibsiz xabarini qancha vaqt ko\'rsatish kerak?**\n\n0 soniya = xabar o\'chirilmaydi',
        'welcome_duration_set': '✅ Xush kelibsiz xabari {duration} soniya ko\'rsatiladi',
        'settings_info': 'ℹ️ Sozlamalar haqida ma\'lumot',
        'settings_info_text': '''📚 **Sozlamalar haqida ma\'lumot**

**👋 Xush kelibsiz xabari**
Guruhga yangi a\'zo qo\'shilganda xush kelibsiz xabarini ko\'rsatadi.

**⏱️ Xush kelibsiz xabarini ko\'rsatish**
Xush kelibsiz xabarini qancha vaqt ko\'rsatish kerakligini belgilaydi (0 = o\'chirilmaydi).

**🌊 To\'fon funksiyasi**
Foydalanuvchilar juda ko\'p xabar yuborganda avtomatik cheklaydi (10 soniyada 5 xabar).

**🚫 So\'z filtr funksiyasi**
Filtrlangan so\'zlarni guruhdan o\'chiradi.

**🔗 Havola yuborishni taqiqlash**
Guruhdagi barcha havolalarni o\'chiradi va foydalanuvchini ogohlantiiradi.

**📎 Fayl yuborishni taqiqlash**
Hujjat va fayllarni yuborishni to\'sib qo\'yadi.

**🔐 Bot emasligini tekshirish**
Yangi a\'zolar 2 daqiqa ichida tekshiruvdan o\'tishlari kerak, aks holda guruhdan chiqariladi.

**📷🎥🎵 Rasm/Video/Audio yuborishni taqiqlash**
Turli xil media turlarini alohida-alohida nazorat qilish imkonini beradi.

**📢 Ovozli/Stiker/Animatsiya yuborishni taqiqlash**
Ovozli xabarlar, stikerlar va animatsiyalarni cheklash.

**🎬 Video xabar yuborishni taqiqlash**
Aylanma video xabarlarni (video note) yuborishni to\'sadi.

**🚪 Guruhga qo\'shildi/chiqdi xabarini o\'chirish**
Telegram xizmat xabarlarini avtomatik o\'chiradi.

**⚙️ Xizmat xabarlarini o\'chirish**
Guruh rasmini o\'zgartirish, nom o\'zgartirish kabi xabarlarni o\'chiradi.

**⚠️ Ogohlantirishlar soni**
Foydalanuvchi chetlatilishidan oldin nechta ogohlantirish berishni belgilaydi.''',

        # Flood control
        'flood_muted': '🚫 {user} 5 daqiqaga ovozsizlashtirildi (to\'fon)',

        # Verification
        'verify_button': '✅ Men bot emasman',
        'verify_welcome': '👋 Xush kelibsiz {user}!\n\n2 daqiqa ichida siz bot emasligingizni tasdiqlash uchun quyidagi tugmani bosing.',
        'verify_success': '✅ {user} tasdiqlandi!',
        'verify_kicked': '❌ {user} guruhdan chiqarildi (tasdiqlanmadi)',

        # Link filtering
        'link_warning': '⚠️ **Ogohlangtirildi** {user} (havola yuborish)\n\n**Ogohlantirish:** {warnings}/{max_warnings}\n**Sabab:** Havolalar taqiqlangan',

        # File filtering
        'file_warning': '⚠️ **Ogohlangtirildi** {user} (fayl yuborish)\n\n**Ogohlantirish:** {warnings}/{max_warnings}\n**Sabab:** Fayllar taqiqlangan',

        # Media filtering
        'media_warning': '⚠️ **Ogohlangtirildi** {user} (media yuborish)\n\n**Ogohlantirish:** {warnings}/{max_warnings}\n**Sabab:** {media_type} taqiqlangan',

        # Error messages
        'user_not_found': '❌ Foydalanuvchi topilmadi. Ular guruhni tark etgan bo\'lishi mumkin.',
        'insufficient_permissions': '❌ Menda bu amalni bajarish uchun yetarli huquq yo\'q.\n\nIltimos, menga quyidagi admin huquqlarini bering:\n• Foydalanuvchilarni bloklash\n• Xabarlarni o\'chirish\n• Foydalanuvchilarni cheklash',
        'rate_limit_telegram': '⏳ Juda ko\'p so\'rovlar. Iltimos, bir oz kutib qayta urinib ko\'ring.',
        'invalid_request': '❌ Noto\'g\'ri so\'rov. Iltimos, buyrug\'ingizni tekshiring.',
        'unexpected_error': '❌ Kutilmagan xatolik yuz berdi. Xatolik qayd etildi.',
    }
}

LANGUAGE_NAMES = {
    'uz': '🇺🇿 O\'zbekcha'
}

def get_text(lang: str, key: str, **kwargs) -> str:
    """Get translated text for a given language and key"""
    # Always use Uzbek since it's the only language
    lang = 'uz'

    text = TRANSLATIONS.get(lang, {}).get(key, key)

    # Format with kwargs if provided
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass

    return text
