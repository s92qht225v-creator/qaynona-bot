#!/usr/bin/env python3
"""
Multi-Tenant Telegram Moderation Bot
Handles multiple groups with isolated configurations and data
"""

import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from functools import wraps

from telegram import (
    Update,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Chat
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.error import TelegramError

from config import Config
from database import (
    init_db,
    get_or_create_tenant,
    update_tenant_config,
    add_warning,
    get_warnings,
    remove_warning,
    reset_warnings,
    add_filter_word,
    remove_filter_word,
    get_filter_words,
    log_action,
    get_tenant_stats,
    is_global_admin,
    log_member_activity,
    get_member_activity_stats,
    get_user_language,
    set_user_language,
    get_all_tenants
)
from translations import get_text, LANGUAGE_NAMES

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# In-memory storage for rate limiting (per tenant)
tenant_flood_tracking: Dict[int, Dict[int, List[float]]] = {}
tenant_pending_verifications: Dict[int, Dict[int, int]] = {}

# ==================== DECORATORS ====================

def rate_limit(seconds: int = 2):
    """Rate limit decorator to prevent command spam"""
    last_called = {}

    def decorator(func):
        @wraps(func)
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user_id = update.effective_user.id
            now = datetime.now().timestamp()

            if user_id in last_called and now - last_called[user_id] < seconds:
                remaining = int(seconds - (now - last_called[user_id]))
                # Get user's language preference
                if update.effective_chat.type in ['group', 'supergroup']:
                    tenant = get_or_create_tenant(update.effective_chat.id)
                    lang = tenant.language
                else:
                    lang = get_user_language(user_id)
                await update.message.reply_text(
                    get_text(lang, 'rate_limit_wait', remaining=remaining)
                )
                return

            last_called[user_id] = now
            return await func(update, context)
        return wrapped
    return decorator

def admin_only(func):
    """Decorator to restrict commands to admins only"""
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await is_admin(update, context):
            # Get user's language preference
            if update.effective_chat.type in ['group', 'supergroup']:
                tenant = get_or_create_tenant(update.effective_chat.id)
                lang = tenant.language
            else:
                lang = get_user_language(update.effective_user.id)
            await update.message.reply_text(get_text(lang, 'admin_only'))
            return
        return await func(update, context)
    return wrapped

def group_only(func):
    """Decorator to restrict commands to group chats only"""
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.type not in ['group', 'supergroup']:
            lang = get_user_language(update.effective_user.id)
            await update.message.reply_text(get_text(lang, 'group_only'))
            return
        return await func(update, context)
    return wrapped

# ==================== HELPER FUNCTIONS ====================

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int = None) -> bool:
    """Check if user is admin in the group"""
    if user_id is None:
        user_id = update.effective_user.id

    # Check if global admin
    if is_global_admin(user_id):
        return True

    try:
        chat_member = await context.bot.get_chat_member(
            chat_id=update.effective_chat.id,
            user_id=user_id
        )
        return chat_member.status in ['creator', 'administrator']
    except TelegramError:
        return False

async def show_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Show settings menu for a specific group (can be called from private chat)"""
    tenant = get_or_create_tenant(chat_id)

    # Get chat info
    try:
        chat = await context.bot.get_chat(chat_id)
        chat_title = chat.title
    except TelegramError:
        chat_title = "Unknown Group"

    lang = tenant.language

    def status_icon(enabled: bool) -> str:
        return '✅' if enabled else '❌'

    # Button labels (keep them short for buttons)
    welcome_btn = get_text(lang, 'welcome_msg').replace('👋 ', '').replace('Xush Kelibsiz Xabari', 'Xush Kelibsiz').replace('Приветственное Сообщение', 'Приветствие').replace('Welcome Message', 'Welcome')
    flood_btn = get_text(lang, 'flood_control').replace('🌊 ', '').replace('To\'fon Nazorati', 'To\'fon').replace('Контроль Флуда', 'Флуд').replace('Flood Control', 'Flood')
    filter_btn = get_text(lang, 'word_filter').replace('🚫 ', '').replace('So\'z Filtri', 'Filtr').replace('Фильтр Слов', 'Фильтр').replace('Word Filter', 'Filter')
    antilink_btn = get_text(lang, 'antilink').replace('🔗 ', '').replace('Havolalar Filtri', 'Havolalar').replace('Link Filter', 'Links')
    antifile_btn = get_text(lang, 'antifile').replace('📎 ', '').replace('Fayllar Filtri', 'Fayllar').replace('File Filter', 'Files')
    verify_btn = get_text(lang, 'verification').replace('🔐 ', '').replace('Tekshiruv', 'Tekshir').replace('Проверка', 'Проверка').replace('Verification', 'Verify')

    # Media button labels (short versions)
    photo_btn = get_text(lang, 'media_photo').replace('📷 ', '')
    video_btn = get_text(lang, 'media_video').replace('🎥 ', '')
    audio_btn = get_text(lang, 'media_audio').replace('🎵 ', '')
    voice_btn = get_text(lang, 'media_voice').replace('🎤 ', '')
    sticker_btn = get_text(lang, 'media_sticker').replace('🎭 ', '')
    animation_btn = get_text(lang, 'media_animation').replace('🎞️ ', '')
    videonote_btn = get_text(lang, 'media_videonote').replace('🎬 ', '')

    keyboard = [
        # Info button at the top
        [InlineKeyboardButton(
            get_text(lang, 'settings_info'),
            callback_data=f"settings_info_{chat_id}"
        )],
        # Protection settings
        [InlineKeyboardButton(
            f"{status_icon(tenant.welcome_enabled)} {welcome_btn}",
            callback_data=f"toggle_welcome_{chat_id}"
        )],
        [InlineKeyboardButton(
            f"⏱️ {get_text(lang, 'welcome_duration')}: {tenant.welcome_message_duration} {get_text(lang, 'welcome_duration_seconds')}",
            callback_data=f"change_welcome_duration_{chat_id}"
        )],
        [InlineKeyboardButton(
            f"{status_icon(tenant.antiflood_enabled)} {flood_btn}",
            callback_data=f"toggle_antiflood_{chat_id}"
        )],
        [InlineKeyboardButton(
            f"{status_icon(tenant.filter_enabled)} {filter_btn}",
            callback_data=f"toggle_filter_{chat_id}"
        )],
        [InlineKeyboardButton(
            f"{status_icon(tenant.antilink_enabled)} {antilink_btn}",
            callback_data=f"toggle_antilink_{chat_id}"
        )],
        [InlineKeyboardButton(
            f"{status_icon(tenant.antifile_enabled)} {antifile_btn}",
            callback_data=f"toggle_antifile_{chat_id}"
        )],
        [InlineKeyboardButton(
            f"{status_icon(tenant.verification_enabled)} {verify_btn}",
            callback_data=f"toggle_verification_{chat_id}"
        )],
        # Media settings
        [InlineKeyboardButton(
            f"{status_icon(tenant.antimedia_photo)} {photo_btn}",
            callback_data=f"toggle_antimedia_photo_{chat_id}"
        )],
        [InlineKeyboardButton(
            f"{status_icon(tenant.antimedia_video)} {video_btn}",
            callback_data=f"toggle_antimedia_video_{chat_id}"
        )],
        [InlineKeyboardButton(
            f"{status_icon(tenant.antimedia_audio)} {audio_btn}",
            callback_data=f"toggle_antimedia_audio_{chat_id}"
        )],
        [InlineKeyboardButton(
            f"{status_icon(tenant.antimedia_voice)} {voice_btn}",
            callback_data=f"toggle_antimedia_voice_{chat_id}"
        )],
        [InlineKeyboardButton(
            f"{status_icon(tenant.antimedia_sticker)} {sticker_btn}",
            callback_data=f"toggle_antimedia_sticker_{chat_id}"
        )],
        [InlineKeyboardButton(
            f"{status_icon(tenant.antimedia_animation)} {animation_btn}",
            callback_data=f"toggle_antimedia_animation_{chat_id}"
        )],
        [InlineKeyboardButton(
            f"{status_icon(tenant.antimedia_videonote)} {videonote_btn}",
            callback_data=f"toggle_antimedia_videonote_{chat_id}"
        )],
        # Cleanup settings
        [InlineKeyboardButton(
            f"{status_icon(tenant.delete_join_messages)} Guruhga qo\'shildi xabarini o\'chirish",
            callback_data=f"toggle_delete_join_{chat_id}"
        )],
        [InlineKeyboardButton(
            f"{status_icon(tenant.delete_leave_messages)} Guruhdan chiqdi xabarini o\'chirish",
            callback_data=f"toggle_delete_leave_{chat_id}"
        )],
        [InlineKeyboardButton(
            f"{status_icon(tenant.delete_service_messages)} Xizmat xabarlarini o'chirish",
            callback_data=f"toggle_delete_service_{chat_id}"
        )],
        # Quick settings
        [InlineKeyboardButton(
            f"⚠️ Ogohlantirishlar soni: {tenant.max_warnings}",
            callback_data=f"change_warnings_{chat_id}"
        )],
        # Back button
        [InlineKeyboardButton(
            get_text(lang, 'back_to_menu'),
            callback_data="help_settings"
        )]
    ]

    # Button labels stripped of emojis for cleaner display
    welcome_label = get_text(lang, 'welcome_msg').replace('👋 ', '')
    flood_label = get_text(lang, 'flood_control').replace('🌊 ', '')
    filter_label = get_text(lang, 'word_filter').replace('🚫 ', '')
    antilink_label = get_text(lang, 'antilink').replace('🔗 ', '')
    antifile_label = get_text(lang, 'antifile').replace('📎 ', '')
    verification_label = get_text(lang, 'verification').replace('🔐 ', '')

    # Media labels
    photo_label = get_text(lang, 'media_photo').replace('📷 ', '')
    video_label = get_text(lang, 'media_video').replace('🎥 ', '')
    audio_label = get_text(lang, 'media_audio').replace('🎵 ', '')
    voice_label = get_text(lang, 'media_voice').replace('🎤 ', '')
    sticker_label = get_text(lang, 'media_sticker').replace('🎭 ', '')
    animation_label = get_text(lang, 'media_animation').replace('🎞️ ', '')
    videonote_label = get_text(lang, 'media_videonote').replace('🎬 ', '')

    delete_join_label = get_text(lang, 'delete_join').replace('🚫 ', '')
    delete_leave_label = get_text(lang, 'delete_leave').replace('🚫 ', '')
    delete_service_label = get_text(lang, 'delete_service').replace('🚫 ', '')

    text = (
        f"{get_text(lang, 'settings_title')}: {chat_title}\n\n"
        f"[{status_icon(tenant.welcome_enabled)}] {welcome_label}\n"
        f"[{status_icon(tenant.antiflood_enabled)}] {flood_label}\n"
        f"[{status_icon(tenant.filter_enabled)}] {filter_label}\n"
        f"[{status_icon(tenant.antilink_enabled)}] {antilink_label}\n"
        f"[{status_icon(tenant.antifile_enabled)}] {antifile_label}\n"
        f"[{status_icon(tenant.verification_enabled)}] {verification_label}\n"
        f"[{status_icon(tenant.antimedia_photo)}] {photo_label}\n"
        f"[{status_icon(tenant.antimedia_video)}] {video_label}\n"
        f"[{status_icon(tenant.antimedia_audio)}] {audio_label}\n"
        f"[{status_icon(tenant.antimedia_voice)}] {voice_label}\n"
        f"[{status_icon(tenant.antimedia_sticker)}] {sticker_label}\n"
        f"[{status_icon(tenant.antimedia_animation)}] {animation_label}\n"
        f"[{status_icon(tenant.antimedia_videonote)}] {videonote_label}\n"
        f"[{status_icon(tenant.delete_join_messages)}] {delete_join_label}\n"
        f"[{status_icon(tenant.delete_leave_messages)}] {delete_leave_label}\n"
        f"[{status_icon(tenant.delete_service_messages)}] {delete_service_label}\n\n"
        f"{get_text(lang, 'max_warnings')}: {tenant.max_warnings}\n\n"
        f"────────────────\n"
        f"{get_text(lang, 'settings_hint')}"
    )

    # Check if this is from a callback query or a message
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        except TelegramError as e:
            # Message wasn't modified (same content)
            if "message is not modified" not in str(e).lower():
                raise
    else:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

def is_flooding(tenant_id: int, user_id: int, limit: int = 5, time_window: int = 10) -> bool:
    """Check if user is flooding messages in a specific tenant"""
    now = datetime.now().timestamp()

    # Initialize tenant tracking if needed
    if tenant_id not in tenant_flood_tracking:
        tenant_flood_tracking[tenant_id] = {}

    if user_id not in tenant_flood_tracking[tenant_id]:
        tenant_flood_tracking[tenant_id][user_id] = []

    # Remove old messages outside time window
    tenant_flood_tracking[tenant_id][user_id] = [
        t for t in tenant_flood_tracking[tenant_id][user_id]
        if now - t < time_window
    ]

    # Add current message
    tenant_flood_tracking[tenant_id][user_id].append(now)

    return len(tenant_flood_tracking[tenant_id][user_id]) > limit

# ==================== COMMAND HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - send welcome message or handle deep links"""

    # Check for deep link (settings_CHATID)
    if context.args and len(context.args) > 0:
        if context.args[0].startswith('settings_'):
            # Extract chat_id from deep link
            try:
                chat_id = int(context.args[0].replace('settings_', ''))

                # Verify user is admin in that group
                try:
                    chat_member = await context.bot.get_chat_member(
                        chat_id=chat_id,
                        user_id=update.effective_user.id
                    )

                    if chat_member.status not in ['creator', 'administrator']:
                        lang = get_user_language(update.effective_user.id)
                        await update.message.reply_text(
                            get_text(lang, 'no_permission')
                        )
                        return

                    # Show settings for this specific group in private chat
                    await show_settings_menu(update, context, chat_id)
                    return

                except TelegramError as e:
                    lang = get_user_language(update.effective_user.id)
                    await update.message.reply_text(
                        get_text(lang, 'permission_error')
                    )
                    return

            except ValueError:
                pass  # Invalid format, show normal welcome

    # Normal welcome message - show new layout with language selection
    # Get user's saved language preference or default to English
    lang = get_user_language(update.effective_user.id)

    # Build the welcome text
    welcome_text = (
        f"{get_text(lang, 'start_greeting')}\n\n"
        f"{get_text(lang, 'start_description')}\n\n"
        f"{get_text(lang, 'start_instructions')}\n\n"
        f"{get_text(lang, 'start_list_1')}\n"
        f"{get_text(lang, 'start_list_2')}\n"
        f"{get_text(lang, 'start_list_3')}\n"
        f"{get_text(lang, 'start_list_4')}\n"
        f"{get_text(lang, 'start_list_5')}\n"
        f"{get_text(lang, 'start_list_6')}\n"
        f"{get_text(lang, 'start_list_7')}\n\n"
        f"{get_text(lang, 'start_footer')}\n"
        f"{get_text(lang, 'start_footer_text')}\n\n"
        f"{get_text(lang, 'start_commands_header')}\n\n"
        f"{get_text(lang, 'start_commands_text')}"
    )

    # Get bot username for the "Add to group" link
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username

    # Create keyboard with "Add to group" button and help button (no language selector - only Uzbek supported)
    keyboard = [
        [InlineKeyboardButton(
            get_text(lang, 'add_to_group'),
            url=f"https://t.me/{bot_username}?startgroup=true"
        )],
        [InlineKeyboardButton(
            get_text(lang, 'show_help'),
            callback_data=f"show_help_{lang}"
        )]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help menu with all available commands"""
    # Use group language if in a group, or user's saved preference in private chat
    if update.effective_chat.type in ['group', 'supergroup']:
        tenant = get_or_create_tenant(update.effective_chat.id)
        lang = tenant.language
    else:
        lang = get_user_language(update.effective_user.id)

    # Build help text with commands organized by location
    help_text = (
        f"{get_text(lang, 'help_title')}\n\n"
        f"{get_text(lang, 'help_admin_group')}\n"
        f"{get_text(lang, 'help_ban')}\n"
        f"{get_text(lang, 'help_kick')}\n"
        f"{get_text(lang, 'help_mute')}\n"
        f"{get_text(lang, 'help_unmute')}\n"
        f"{get_text(lang, 'help_warn')}\n"
        f"{get_text(lang, 'help_unwarn')}\n"
        f"{get_text(lang, 'help_unban')}\n"
        f"{get_text(lang, 'help_info')}\n\n"
        f"{get_text(lang, 'help_users')}\n"
        f"{get_text(lang, 'help_rules')}"
    )

    # Create keyboard with settings, stats and back buttons
    keyboard = [
        [InlineKeyboardButton("⚙️ " + get_text(lang, 'help_settings'), callback_data="help_settings")],
        [InlineKeyboardButton("📋 " + get_text(lang, 'help_setrules_button'), callback_data="help_setrules")],
        [InlineKeyboardButton("👁️ " + get_text(lang, 'help_seerules_button'), callback_data="help_viewrules")],
        [InlineKeyboardButton("👋 " + get_text(lang, 'help_setwelcome_button'), callback_data="help_setwelcome")],
        [InlineKeyboardButton("👁️ " + get_text(lang, 'help_seewelcome_button'), callback_data="help_viewwelcome")],
        [InlineKeyboardButton("➕ " + get_text(lang, 'help_setfilter_button'), callback_data="help_setfilter")],
        [InlineKeyboardButton("➖ " + get_text(lang, 'help_removefilter_button'), callback_data="help_removefilter")],
        [InlineKeyboardButton("👁️ " + get_text(lang, 'help_viewfilters_button'), callback_data="help_viewfilters")],
        [InlineKeyboardButton("📊 " + get_text(lang, 'help_stats'), callback_data="help_stats")],
        [InlineKeyboardButton(get_text(lang, 'help_back_menu'), callback_data=f"help_back_{lang}")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(help_text, reply_markup=reply_markup)

@rate_limit(3)
@admin_only
@group_only
async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a user from the group"""
    chat_id = update.effective_chat.id
    tenant = get_or_create_tenant(chat_id)
    lang = tenant.language

    if not update.message.reply_to_message:
        await update.message.reply_text(get_text(lang, 'ban_reply_required'))
        return

    user_to_ban = update.message.reply_to_message.from_user
    admin_id = update.effective_user.id

    # Don't ban admins
    if await is_admin(update, context, user_to_ban.id):
        await update.message.reply_text(get_text(lang, 'ban_admin_error'))
        return

    reason = ' '.join(context.args) if context.args else None

    try:
        await context.bot.ban_chat_member(
            chat_id=chat_id,
            user_id=user_to_ban.id
        )

        # Log the action
        log_action(chat_id, user_to_ban.id, admin_id, "BAN", reason or "No reason provided")

        if reason:
            await update.message.reply_text(
                get_text(lang, 'user_banned', user=user_to_ban.mention_html(), reason=reason),
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                get_text(lang, 'user_banned_no_reason', user=user_to_ban.mention_html()),
                parse_mode='HTML'
            )
        logger.info(f"User {user_to_ban.id} banned from tenant {chat_id} by {admin_id}")
    except TelegramError as e:
        await update.message.reply_text(get_text(lang, 'ban_failed', error=str(e)))

@rate_limit(3)
@admin_only
@group_only
async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a user from the group"""
    chat_id = update.effective_chat.id
    tenant = get_or_create_tenant(chat_id)
    lang = tenant.language
    admin_id = update.effective_user.id

    # Check if replying to a message
    if update.message.reply_to_message:
        user_to_unban = update.message.reply_to_message.from_user
        user_id = user_to_unban.id
        user_name = user_to_unban.mention_html()
    elif context.args and context.args[0].isdigit():
        # Unban by user ID
        user_id = int(context.args[0])
        user_name = f"User ID: {user_id}"
    else:
        await update.message.reply_text(
            get_text(lang, 'unban_usage'),
            parse_mode='Markdown'
        )
        return

    try:
        await context.bot.unban_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            only_if_banned=True
        )

        # Log the action
        log_action(chat_id, user_id, admin_id, "UNBAN", "User unbanned")

        msg = await update.message.reply_text(
            get_text(lang, 'user_unbanned', user=user_name),
            parse_mode='HTML'
        )
        logger.info(f"User {user_id} unbanned from tenant {chat_id} by {admin_id}")

        # Delete the unban message after 5 seconds
        await asyncio.sleep(5)
        await msg.delete()
        # Also delete the command message
        try:
            await update.message.delete()
        except TelegramError:
            pass
    except TelegramError as e:
        await update.message.reply_text(get_text(lang, 'unban_failed', error=str(e)))

@rate_limit(3)
@admin_only
@group_only
async def kick_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kick a user from the group"""
    chat_id = update.effective_chat.id
    tenant = get_or_create_tenant(chat_id)
    lang = tenant.language

    if not update.message.reply_to_message:
        await update.message.reply_text(get_text(lang, 'kick_reply_required'))
        return

    user_to_kick = update.message.reply_to_message.from_user
    admin_id = update.effective_user.id

    if await is_admin(update, context, user_to_kick.id):
        await update.message.reply_text(get_text(lang, 'kick_admin_error'))
        return

    try:
        await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_to_kick.id)
        await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_to_kick.id)

        # Log the action
        log_action(chat_id, user_to_kick.id, admin_id, "KICK", "Kicked from group")

        await update.message.reply_text(
            get_text(lang, 'user_kicked', user=user_to_kick.mention_html()),
            parse_mode='HTML'
        )
        logger.info(f"User {user_to_kick.id} kicked from tenant {chat_id}")
    except TelegramError as e:
        await update.message.reply_text(get_text(lang, 'kick_failed', error=str(e)))

@rate_limit(2)
@admin_only
@group_only
async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mute a user temporarily"""
    chat_id = update.effective_chat.id
    tenant = get_or_create_tenant(chat_id)
    lang = tenant.language

    if not update.message.reply_to_message:
        await update.message.reply_text(get_text(lang, 'mute_reply_required'), parse_mode='Markdown')
        return

    user_to_mute = update.message.reply_to_message.from_user
    admin_id = update.effective_user.id

    if await is_admin(update, context, user_to_mute.id):
        await update.message.reply_text(get_text(lang, 'mute_admin_error'))
        return

    # Parse duration
    duration_minutes = 60  # default 1 hour
    if context.args:
        try:
            duration_minutes = int(context.args[0])
            if duration_minutes <= 0:
                await update.message.reply_text(get_text(lang, 'mute_positive_duration'))
                return
        except ValueError:
            await update.message.reply_text(get_text(lang, 'mute_invalid_duration'), parse_mode='Markdown')
            return

    try:
        until_date = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_to_mute.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date
        )

        # Log the action
        log_action(chat_id, user_to_mute.id, admin_id, "MUTE", f"Muted for {duration_minutes} minutes", duration_minutes)

        await update.message.reply_text(
            get_text(lang, 'user_muted', user=user_to_mute.mention_html(), duration=duration_minutes),
            parse_mode='HTML'
        )
        logger.info(f"User {user_to_mute.id} muted in tenant {chat_id} for {duration_minutes} minutes")
    except TelegramError as e:
        await update.message.reply_text(get_text(lang, 'mute_failed', error=str(e)))

@rate_limit(2)
@admin_only
@group_only
async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unmute a user"""
    chat_id = update.effective_chat.id
    tenant = get_or_create_tenant(chat_id)
    lang = tenant.language

    if not update.message.reply_to_message:
        await update.message.reply_text(get_text(lang, 'unmute_reply_required'))
        return

    user_to_unmute = update.message.reply_to_message.from_user
    admin_id = update.effective_user.id

    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_to_unmute.id,
            permissions=ChatPermissions.all_permissions()
        )

        # Log the action
        log_action(chat_id, user_to_unmute.id, admin_id, "UNMUTE", "Unmuted by admin")

        await update.message.reply_text(
            get_text(lang, 'user_unmuted', user=user_to_unmute.mention_html()),
            parse_mode='HTML'
        )
    except TelegramError as e:
        await update.message.reply_text(get_text(lang, 'unmute_failed', error=str(e)))

@rate_limit(2)
@admin_only
@group_only
async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Warn a user"""
    chat_id = update.effective_chat.id
    tenant = get_or_create_tenant(chat_id, update.effective_chat.title, update.effective_chat.type)
    lang = tenant.language

    if not update.message.reply_to_message:
        await update.message.reply_text(get_text(lang, 'warn_reply_required'))
        return

    user_to_warn = update.message.reply_to_message.from_user
    admin_id = update.effective_user.id

    if await is_admin(update, context, user_to_warn.id):
        await update.message.reply_text(get_text(lang, 'warn_admin_error'))
        return

    reason = ' '.join(context.args) if context.args else "No reason provided"

    # Add warning
    warnings = add_warning(chat_id, user_to_warn.id, reason)

    if warnings >= tenant.max_warnings:
        try:
            # Kick user (ban then immediately unban - allows rejoin with invite link)
            await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_to_warn.id)
            await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_to_warn.id)
            log_action(chat_id, user_to_warn.id, admin_id, "AUTO-KICK", f"Reached {tenant.max_warnings} warnings")

            await update.message.reply_text(
                get_text(lang, 'user_warned_banned', user=user_to_warn.mention_html(), max_warnings=tenant.max_warnings),
                parse_mode='HTML'
            )
            reset_warnings(chat_id, user_to_warn.id)
        except TelegramError as e:
            await update.message.reply_text(get_text(lang, 'warn_failed_ban', error=str(e)))
    else:
        log_action(chat_id, user_to_warn.id, admin_id, "WARN", reason)

        await update.message.reply_text(
            get_text(lang, 'user_warned', user=user_to_warn.mention_html(), warnings=warnings, max_warnings=tenant.max_warnings, reason=reason),
            parse_mode='HTML'
        )

@rate_limit(2)
@admin_only
@group_only
async def unwarn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove warnings from a user"""
    chat_id = update.effective_chat.id
    tenant = get_or_create_tenant(chat_id)
    lang = tenant.language

    if not update.message.reply_to_message:
        await update.message.reply_text(get_text(lang, 'unwarn_reply_required'))
        return

    user_to_unwarn = update.message.reply_to_message.from_user
    admin_id = update.effective_user.id

    current_warnings = get_warnings(chat_id, user_to_unwarn.id)

    if current_warnings > 0:
        new_count = remove_warning(chat_id, user_to_unwarn.id)

        log_action(chat_id, user_to_unwarn.id, admin_id, "UNWARN", "Warning removed by admin")

        await update.message.reply_text(
            get_text(lang, 'warning_removed', user=user_to_unwarn.mention_html(), warnings=new_count, max_warnings=tenant.max_warnings),
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            get_text(lang, 'no_warnings', user=user_to_unwarn.mention_html()),
            parse_mode='HTML'
        )

@rate_limit(5)
@group_only
async def check_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check user's warnings"""
    chat_id = update.effective_chat.id
    tenant = get_or_create_tenant(chat_id)
    lang = tenant.language

    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
    else:
        user = update.effective_user

    warnings = get_warnings(chat_id, user.id)

    await update.message.reply_text(
        get_text(lang, 'warnings_info', user=user.mention_html(), warnings=warnings, max_warnings=tenant.max_warnings),
        parse_mode='HTML'
    )

@rate_limit(3)
async def add_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a word to filter (private chat only)"""
    # Only allow in private chat
    if update.effective_chat.type != 'private':
        return

    lang = get_user_language(update.effective_user.id)

    if not context.args:
        await update.message.reply_text(get_text(lang, 'filter_usage'), parse_mode='Markdown')
        return

    word = ' '.join(context.args).lower()
    admin_id = update.effective_user.id

    # Get all groups where user is admin
    all_tenants = get_all_tenants()
    managed_groups = []

    for tenant in all_tenants:
        try:
            member = await context.bot.get_chat_member(tenant.chat_id, admin_id)
            if member.status in ['creator', 'administrator']:
                managed_groups.append((tenant.chat_id, tenant.chat_title))
        except TelegramError:
            continue

    if not managed_groups:
        await update.message.reply_text("❌ Siz hech qanday guruhda administrator emassiz.")
        return

    if len(managed_groups) == 1:
        # Only one group - add filter directly
        chat_id = managed_groups[0][0]
        if add_filter_word(chat_id, word, admin_id):
            await update.message.reply_text(get_text(lang, 'filter_added', word=word), parse_mode='Markdown')
        else:
            await update.message.reply_text(get_text(lang, 'filter_exists', word=word), parse_mode='Markdown')
    else:
        # Multiple groups - show selection buttons
        keyboard = []
        for group_chat_id, group_title in managed_groups:
            keyboard.append([
                InlineKeyboardButton(
                    f"➕ {group_title}",
                    callback_data=f"addfilter_{group_chat_id}"
                )
            ])

        # Store the word in context for later use
        context.user_data['pending_filter_word'] = word

        await update.message.reply_text(
            f"📝 Qaysi guruhga `{word}` so'zini filtrlash kerak?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

@rate_limit(3)
async def remove_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a word from filter (private chat only)"""
    # Only allow in private chat
    if update.effective_chat.type != 'private':
        return

    lang = get_user_language(update.effective_user.id)

    if not context.args:
        await update.message.reply_text(get_text(lang, 'unfilter_usage'), parse_mode='Markdown')
        return

    word = ' '.join(context.args).lower()
    admin_id = update.effective_user.id

    # Get all groups where user is admin
    all_tenants = get_all_tenants()
    managed_groups = []

    for tenant in all_tenants:
        try:
            member = await context.bot.get_chat_member(tenant.chat_id, admin_id)
            if member.status in ['creator', 'administrator']:
                managed_groups.append((tenant.chat_id, tenant.chat_title))
        except TelegramError:
            continue

    if not managed_groups:
        await update.message.reply_text("❌ Siz hech qanday guruhda administrator emassiz.")
        return

    if len(managed_groups) == 1:
        # Only one group - remove filter directly
        chat_id = managed_groups[0][0]
        if remove_filter_word(chat_id, word):
            await update.message.reply_text(get_text(lang, 'filter_removed', word=word), parse_mode='Markdown')
        else:
            await update.message.reply_text(get_text(lang, 'filter_not_found', word=word), parse_mode='Markdown')
    else:
        # Multiple groups - show selection buttons
        keyboard = []
        for group_chat_id, group_title in managed_groups:
            keyboard.append([
                InlineKeyboardButton(
                    f"➖ {group_title}",
                    callback_data=f"removefilter_{group_chat_id}"
                )
            ])

        # Store the word in context for later use
        context.user_data['pending_unfilter_word'] = word

        await update.message.reply_text(
            f"📝 Qaysi guruhdan `{word}` so'zini o'chirish kerak?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

@rate_limit(5)
async def list_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all filtered words (private chat only)"""
    # Only allow in private chat
    if update.effective_chat.type != 'private':
        return

    lang = get_user_language(update.effective_user.id)
    admin_id = update.effective_user.id

    # Get all groups where user is admin
    all_tenants = get_all_tenants()
    managed_groups = []

    for tenant in all_tenants:
        try:
            member = await context.bot.get_chat_member(tenant.chat_id, admin_id)
            if member.status in ['creator', 'administrator']:
                managed_groups.append((tenant.chat_id, tenant.chat_title))
        except TelegramError:
            continue

    if not managed_groups:
        await update.message.reply_text("❌ Siz hech qanday guruhda administrator emassiz.")
        return

    if len(managed_groups) == 1:
        # Only one group - show filters directly
        chat_id = managed_groups[0][0]
        filters = get_filter_words(chat_id)

        if not filters:
            await update.message.reply_text(get_text(lang, 'no_filters'))
            return

        filter_list = '\n'.join([f"• `{word}`" for word in filters])
        await update.message.reply_text(
            get_text(lang, 'filtered_words_title', filter_list=filter_list),
            parse_mode='Markdown'
        )
    else:
        # Multiple groups - show selection buttons
        keyboard = []
        for group_chat_id, group_title in managed_groups:
            keyboard.append([
                InlineKeyboardButton(
                    f"📋 {group_title}",
                    callback_data=f"listfilters_{group_chat_id}"
                )
            ])

        await update.message.reply_text(
            "📝 Qaysi guruhning filtrlangan so'zlarini ko'rish kerak?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def filter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle filter command callbacks"""
    query = update.callback_query
    await query.answer()

    lang = get_user_language(query.from_user.id)
    admin_id = query.from_user.id

    # Parse callback data
    if query.data.startswith('addfilter_'):
        chat_id = int(query.data.replace('addfilter_', ''))
        word = context.user_data.get('pending_filter_word')

        if not word:
            await query.edit_message_text("❌ Xatolik: So'z topilmadi. Qaytadan urinib ko'ring.")
            return

        # Verify user is admin
        try:
            member = await context.bot.get_chat_member(chat_id, admin_id)
            if member.status not in ['creator', 'administrator']:
                await query.edit_message_text("❌ Siz bu guruhda administrator emassiz.")
                return
        except TelegramError:
            await query.edit_message_text("❌ Guruhga kirish xatosi.")
            return

        if add_filter_word(chat_id, word, admin_id):
            await query.edit_message_text(get_text(lang, 'filter_added', word=word), parse_mode='Markdown')
        else:
            await query.edit_message_text(get_text(lang, 'filter_exists', word=word), parse_mode='Markdown')

        context.user_data.pop('pending_filter_word', None)

    elif query.data.startswith('removefilter_'):
        chat_id = int(query.data.replace('removefilter_', ''))
        word = context.user_data.get('pending_unfilter_word')

        if not word:
            await query.edit_message_text("❌ Xatolik: So'z topilmadi. Qaytadan urinib ko'ring.")
            return

        # Verify user is admin
        try:
            member = await context.bot.get_chat_member(chat_id, admin_id)
            if member.status not in ['creator', 'administrator']:
                await query.edit_message_text("❌ Siz bu guruhda administrator emassiz.")
                return
        except TelegramError:
            await query.edit_message_text("❌ Guruhga kirish xatosi.")
            return

        if remove_filter_word(chat_id, word):
            await query.edit_message_text(get_text(lang, 'filter_removed', word=word), parse_mode='Markdown')
        else:
            await query.edit_message_text(get_text(lang, 'filter_not_found', word=word), parse_mode='Markdown')

        context.user_data.pop('pending_unfilter_word', None)

    elif query.data.startswith('listfilters_'):
        chat_id = int(query.data.replace('listfilters_', ''))

        # Verify user is admin
        try:
            member = await context.bot.get_chat_member(chat_id, admin_id)
            if member.status not in ['creator', 'administrator']:
                await query.edit_message_text("❌ Siz bu guruhda administrator emassiz.")
                return
        except TelegramError:
            await query.edit_message_text("❌ Guruhga kirish xatosi.")
            return

        filters = get_filter_words(chat_id)

        if not filters:
            await query.edit_message_text(get_text(lang, 'no_filters'))
            return

        filter_list = '\n'.join([f"• `{word}`" for word in filters])
        await query.edit_message_text(
            get_text(lang, 'filtered_words_title', filter_list=filter_list),
            parse_mode='Markdown'
        )

@rate_limit(5)
@admin_only
@group_only
async def purge_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete last N messages"""
    chat_id = update.effective_chat.id
    tenant = get_or_create_tenant(chat_id)
    lang = tenant.language

    if not context.args:
        await update.message.reply_text(get_text(lang, 'purge_usage'), parse_mode='Markdown')
        return

    try:
        count = int(context.args[0])
        if count <= 0 or count > 100:
            await update.message.reply_text(get_text(lang, 'purge_range_error'))
            return
    except ValueError:
        await update.message.reply_text(get_text(lang, 'purge_invalid_number'))
        return

    try:
        deleted = 0
        current_message_id = update.message.message_id

        for i in range(count):
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=current_message_id - i - 1
                )
                deleted += 1
            except TelegramError:
                continue

        # Delete the purge command itself
        await update.message.delete()

        # Send confirmation (auto-delete after 5 seconds)
        msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"🗑️ Deleted {deleted} messages."
        )

        await asyncio.sleep(5)
        await msg.delete()

    except TelegramError as e:
        await update.message.reply_text(get_text(lang, 'purge_failed', error=str(e)))

@rate_limit(10)
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show and modify group settings"""
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    user_id = update.effective_user.id

    # Get user's language preference
    lang = get_user_language(user_id)

    # If command used in a group, send deep link button for private chat
    if chat_type in ['group', 'supergroup']:
        # Get bot username for deep link
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username
        deep_link = f"https://t.me/{bot_username}?start=settings_{chat_id}"

        keyboard = [
            [InlineKeyboardButton(get_text(lang, 'settings_private_button'), url=deep_link)]
        ]

        await update.message.reply_text(
            get_text(lang, 'settings_private_msg'),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # If in private chat, show list of groups where user is admin
    # Get all groups this bot is in and check if user is admin
    managed_groups = []

    # Import database directly to query all tenants
    import sqlite3
    conn = sqlite3.connect('multi_tenant_moderation.db')
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id, chat_title FROM tenants WHERE chat_type IN ('group', 'supergroup')")
    all_groups = cursor.fetchall()
    conn.close()

    # Check which groups the user is admin in
    for group_chat_id, group_title in all_groups:
        try:
            chat_member = await context.bot.get_chat_member(
                chat_id=group_chat_id,
                user_id=user_id
            )
            if chat_member.status in ['creator', 'administrator']:
                managed_groups.append((group_chat_id, group_title))
        except TelegramError:
            # Bot might have been removed from group or can't check permissions
            continue

    if not managed_groups:
        await update.message.reply_text(
            get_text(lang, 'no_admin_groups')
        )
        return

    # Show list of groups with buttons
    keyboard = []
    for group_chat_id, group_title in managed_groups:
        keyboard.append([
            InlineKeyboardButton(
                f"⚙️ {group_title}",
                callback_data=f"show_settings_{group_chat_id}"
            )
        ])

    # Add back button at the bottom
    keyboard.append([
        InlineKeyboardButton(
            get_text(lang, 'back_to_menu'),
            callback_data="back_to_start"
        )
    ])

    await update.message.reply_text(
        get_text(lang, 'select_group_settings'),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle settings button callbacks"""
    query = update.callback_query
    await query.answer()

    action = query.data
    logging.info(f"Settings callback received: {action}")

    # Handle "back_to_start" button - return to help menu
    if action == "back_to_start":
        lang = get_user_language(query.from_user.id)

        # Build help text with commands organized by location
        help_text = (
            f"{get_text(lang, 'help_title')}\n\n"
            f"{get_text(lang, 'help_admin_group')}\n"
            f"{get_text(lang, 'help_ban')}\n"
            f"{get_text(lang, 'help_kick')}\n"
            f"{get_text(lang, 'help_mute')}\n"
            f"{get_text(lang, 'help_unmute')}\n"
            f"{get_text(lang, 'help_warn')}\n"
            f"{get_text(lang, 'help_unwarn')}\n"
            f"{get_text(lang, 'help_unban')}\n"
            f"{get_text(lang, 'help_info')}\n\n"
            f"{get_text(lang, 'help_users')}\n"
            f"{get_text(lang, 'help_rules')}"
        )

        # Create keyboard with settings, stats and back buttons
        keyboard = [
            [InlineKeyboardButton("⚙️ " + get_text(lang, 'help_settings'), callback_data="help_settings")],
            [InlineKeyboardButton("📋 " + get_text(lang, 'help_setrules_button'), callback_data="help_setrules")],
            [InlineKeyboardButton("👁️ " + get_text(lang, 'help_seerules_button'), callback_data="help_viewrules")],
            [InlineKeyboardButton("👋 " + get_text(lang, 'help_setwelcome_button'), callback_data="help_setwelcome")],
            [InlineKeyboardButton("👁️ " + get_text(lang, 'help_seewelcome_button'), callback_data="help_viewwelcome")],
            [InlineKeyboardButton("➕ " + get_text(lang, 'help_setfilter_button'), callback_data="help_setfilter")],
            [InlineKeyboardButton("➖ " + get_text(lang, 'help_removefilter_button'), callback_data="help_removefilter")],
            [InlineKeyboardButton("👁️ " + get_text(lang, 'help_viewfilters_button'), callback_data="help_viewfilters")],
            [InlineKeyboardButton("📊 " + get_text(lang, 'help_stats'), callback_data="help_stats")],
            [InlineKeyboardButton(get_text(lang, 'help_back_menu'), callback_data=f"help_back_{lang}")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(help_text, reply_markup=reply_markup)
        return

    # Handle "show_settings_CHATID" from group selection
    if action.startswith('show_settings_'):
        target_chat_id = int(action.replace('show_settings_', ''))

        # Verify user is admin in that group
        try:
            chat_member = await context.bot.get_chat_member(
                chat_id=target_chat_id,
                user_id=query.from_user.id
            )
            if chat_member.status not in ['creator', 'administrator']:
                tenant = get_or_create_tenant(target_chat_id)
                await query.answer(get_text(tenant.language, 'no_permission'), show_alert=True)
                return
        except TelegramError:
            lang = get_user_language(query.from_user.id)
            await query.answer(get_text(lang, 'permission_error'), show_alert=True)
            return

        # Show settings for this group
        await show_settings_menu(update, context, target_chat_id)
        return

    # Extract chat_id from callback data (format: action_CHATID)
    # Parse the callback data to get the target chat_id
    if '_' in action and action.split('_')[-1].lstrip('-').isdigit():
        parts = action.rsplit('_', 1)
        base_action = parts[0]
        target_chat_id = int(parts[1])
    else:
        # Fallback for backwards compatibility (shouldn't happen with new implementation)
        base_action = action
        target_chat_id = query.message.chat_id

    logging.info(f"Parsed - base_action: {base_action}, target_chat_id: {target_chat_id}")

    # Verify user is admin in the target group
    try:
        chat_member = await context.bot.get_chat_member(
            chat_id=target_chat_id,
            user_id=query.from_user.id
        )
        tenant = get_or_create_tenant(target_chat_id)
        if chat_member.status not in ['creator', 'administrator']:
            await query.answer(get_text(tenant.language, 'admin_only'), show_alert=True)
            return
    except TelegramError:
        lang = get_user_language(query.from_user.id)
        await query.answer(get_text(lang, 'permission_error'), show_alert=True)
        return

    # Toggle settings based on callback
    if base_action == "toggle_welcome":
        update_tenant_config(target_chat_id, welcome_enabled=not tenant.welcome_enabled)
    elif base_action == "toggle_antiflood":
        update_tenant_config(target_chat_id, antiflood_enabled=not tenant.antiflood_enabled)
    elif base_action == "toggle_filter":
        update_tenant_config(target_chat_id, filter_enabled=not tenant.filter_enabled)
    elif base_action == "toggle_antilink":
        update_tenant_config(target_chat_id, antilink_enabled=not tenant.antilink_enabled)
    elif base_action == "toggle_antifile":
        update_tenant_config(target_chat_id, antifile_enabled=not tenant.antifile_enabled)
    elif base_action == "toggle_verification":
        update_tenant_config(target_chat_id, verification_enabled=not tenant.verification_enabled)
    elif base_action == "toggle_antimedia_photo":
        update_tenant_config(target_chat_id, antimedia_photo=not tenant.antimedia_photo)
    elif base_action == "toggle_antimedia_video":
        update_tenant_config(target_chat_id, antimedia_video=not tenant.antimedia_video)
    elif base_action == "toggle_antimedia_audio":
        update_tenant_config(target_chat_id, antimedia_audio=not tenant.antimedia_audio)
    elif base_action == "toggle_antimedia_voice":
        update_tenant_config(target_chat_id, antimedia_voice=not tenant.antimedia_voice)
    elif base_action == "toggle_antimedia_sticker":
        update_tenant_config(target_chat_id, antimedia_sticker=not tenant.antimedia_sticker)
    elif base_action == "toggle_antimedia_animation":
        update_tenant_config(target_chat_id, antimedia_animation=not tenant.antimedia_animation)
    elif base_action == "toggle_antimedia_videonote":
        update_tenant_config(target_chat_id, antimedia_videonote=not tenant.antimedia_videonote)
    elif base_action == "toggle_delete_join":
        update_tenant_config(target_chat_id, delete_join_messages=not tenant.delete_join_messages)
    elif base_action == "toggle_delete_leave":
        update_tenant_config(target_chat_id, delete_leave_messages=not tenant.delete_leave_messages)
    elif base_action == "toggle_delete_service":
        update_tenant_config(target_chat_id, delete_service_messages=not tenant.delete_service_messages)
    elif base_action == "change_warnings":
        # Show warning options with chat_id embedded
        warning_label = get_text(tenant.language, 'warnings')
        keyboard = [
            [InlineKeyboardButton(f"{i} {warning_label}", callback_data=f"set_warnings_{i}_{target_chat_id}") for i in range(1, 4)],
            [InlineKeyboardButton(f"{i} {warning_label}", callback_data=f"set_warnings_{i}_{target_chat_id}") for i in range(4, 7)],
            [InlineKeyboardButton(get_text(tenant.language, 'back'), callback_data=f"back_to_settings_{target_chat_id}")]
        ]
        await query.edit_message_text(
            get_text(tenant.language, 'select_max_warnings'),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    elif base_action.startswith("set_warnings_"):
        # Extract the warning number from "set_warnings_N"
        new_max = int(base_action.split('_')[2])
        update_tenant_config(target_chat_id, max_warnings=new_max)
        await query.answer(
            get_text(tenant.language, 'max_warnings_set').format(new_max),
            show_alert=True
        )
    elif base_action == "change_welcome_duration":
        # Show duration options
        duration_label = get_text(tenant.language, 'welcome_duration_seconds')
        keyboard = [
            [InlineKeyboardButton(f"0 {duration_label}", callback_data=f"set_welcome_duration_0_{target_chat_id}")],
            [InlineKeyboardButton(f"10 {duration_label}", callback_data=f"set_welcome_duration_10_{target_chat_id}")],
            [InlineKeyboardButton(f"15 {duration_label}", callback_data=f"set_welcome_duration_15_{target_chat_id}")],
            [InlineKeyboardButton(f"20 {duration_label}", callback_data=f"set_welcome_duration_20_{target_chat_id}")],
            [InlineKeyboardButton(get_text(tenant.language, 'back_to_menu'), callback_data=f"back_to_settings_{target_chat_id}")]
        ]
        await query.edit_message_text(
            get_text(tenant.language, 'select_welcome_duration'),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    elif base_action.startswith("set_welcome_duration_"):
        # Extract the duration from "set_welcome_duration_N"
        new_duration = int(base_action.split('_')[3])
        update_tenant_config(target_chat_id, welcome_message_duration=new_duration)
        await query.answer(
            get_text(tenant.language, 'welcome_duration_set').format(duration=new_duration),
            show_alert=True
        )
    elif base_action == "settings_info":
        # Show settings information page
        keyboard = [
            [InlineKeyboardButton(get_text(tenant.language, 'back_to_menu'), callback_data=f"back_to_settings_{target_chat_id}")]
        ]
        await query.edit_message_text(
            get_text(tenant.language, 'settings_info_text'),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    elif base_action == "back_to_settings":
        pass  # Just refresh the settings

    # Refresh settings display using the helper function
    await show_settings_menu(update, context, target_chat_id)

async def start_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle language selection from the start menu"""
    query = update.callback_query
    await query.answer()

    action = query.data
    logging.info(f"Start language callback received: {action}")

    if action.startswith("start_lang_"):
        # Extract language code from "start_lang_LANG"
        new_lang = action.replace("start_lang_", "")

        # Save user's language preference for private chat
        set_user_language(query.from_user.id, new_lang)

        user_name = query.from_user.first_name

        # Build the welcome text in the selected language
        welcome_text = (
            f"{get_text(new_lang, 'start_greeting').format(name=user_name)}\n\n"
            f"{get_text(new_lang, 'start_description')}\n\n"
            f"{get_text(new_lang, 'start_instructions')}\n\n"
            f"{get_text(new_lang, 'start_commands_header')}\n"
            f"{get_text(new_lang, 'start_commands_text')}"
        )

        # Since we only have Uzbek, this callback shouldn't be triggered
        # Just acknowledge the callback
        pass

async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle help menu button callbacks"""
    query = update.callback_query
    await query.answer()

    action = query.data
    logging.info(f"Help callback received: {action}")

    # Handle back to help button
    if action == "back_to_help":
        lang = get_user_language(query.from_user.id)

        # Build help text
        help_text = (
            f"{get_text(lang, 'help_title')}\n\n"
            f"{get_text(lang, 'help_admin_group')}\n"
            f"{get_text(lang, 'help_ban')}\n"
            f"{get_text(lang, 'help_kick')}\n"
            f"{get_text(lang, 'help_mute')}\n"
            f"{get_text(lang, 'help_unmute')}\n"
            f"{get_text(lang, 'help_warn')}\n"
            f"{get_text(lang, 'help_unwarn')}\n"
            f"{get_text(lang, 'help_unban')}\n"
            f"{get_text(lang, 'help_info')}\n\n"
            f"{get_text(lang, 'help_users')}\n"
            f"{get_text(lang, 'help_rules')}"
        )

        # Create keyboard with settings, stats and back buttons
        keyboard = [
            [InlineKeyboardButton("⚙️ " + get_text(lang, 'help_settings'), callback_data="help_settings")],
            [InlineKeyboardButton("📋 " + get_text(lang, 'help_setrules_button'), callback_data="help_setrules")],
            [InlineKeyboardButton("👁️ " + get_text(lang, 'help_seerules_button'), callback_data="help_viewrules")],
            [InlineKeyboardButton("👋 " + get_text(lang, 'help_setwelcome_button'), callback_data="help_setwelcome")],
            [InlineKeyboardButton("👁️ " + get_text(lang, 'help_seewelcome_button'), callback_data="help_viewwelcome")],
            [InlineKeyboardButton("➕ " + get_text(lang, 'help_setfilter_button'), callback_data="help_setfilter")],
            [InlineKeyboardButton("➖ " + get_text(lang, 'help_removefilter_button'), callback_data="help_removefilter")],
            [InlineKeyboardButton("👁️ " + get_text(lang, 'help_viewfilters_button'), callback_data="help_viewfilters")],
            [InlineKeyboardButton("📊 " + get_text(lang, 'help_stats'), callback_data="help_stats")],
            [InlineKeyboardButton(get_text(lang, 'help_back_menu'), callback_data=f"help_back_{lang}")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(help_text, reply_markup=reply_markup)
        return

    # Handle stats button
    if action == "help_stats":
        lang = get_user_language(query.from_user.id)
        user_id = query.from_user.id

        # Get all groups where user is admin
        managed_groups = []
        import sqlite3
        conn = sqlite3.connect('multi_tenant_moderation.db')
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id, chat_title FROM tenants WHERE chat_type IN ('group', 'supergroup')")
        all_groups = cursor.fetchall()
        conn.close()

        # Check which groups the user is admin in
        for group_chat_id, group_title in all_groups:
            try:
                chat_member = await context.bot.get_chat_member(
                    chat_id=group_chat_id,
                    user_id=user_id
                )
                if chat_member.status in ['creator', 'administrator']:
                    managed_groups.append((group_chat_id, group_title))
            except TelegramError:
                continue

        if not managed_groups:
            await query.edit_message_text(get_text(lang, 'no_admin_groups_add'))
            return

        # Show list of groups with buttons
        keyboard = []
        for group_chat_id, group_title in managed_groups:
            keyboard.append([
                InlineKeyboardButton(
                    f"📊 {group_title}",
                    callback_data=f"stats_{group_chat_id}"
                )
            ])

        # Add back button at the bottom
        keyboard.append([
            InlineKeyboardButton(
                get_text(lang, 'back_to_menu'),
                callback_data="back_to_help"
            )
        ])

        await query.edit_message_text(
            get_text(lang, 'select_group_stats'),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Handle setrules button
    if action == "help_setrules":
        lang = get_user_language(query.from_user.id)
        user_id = query.from_user.id

        # Get all groups where user is admin
        managed_groups = []
        import sqlite3
        conn = sqlite3.connect('multi_tenant_moderation.db')
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id, chat_title FROM tenants WHERE chat_type IN ('group', 'supergroup')")
        all_groups = cursor.fetchall()
        conn.close()

        # Check which groups the user is admin in
        for group_chat_id, group_title in all_groups:
            try:
                chat_member = await context.bot.get_chat_member(
                    chat_id=group_chat_id,
                    user_id=user_id
                )
                if chat_member.status in ['creator', 'administrator']:
                    managed_groups.append((group_chat_id, group_title))
            except TelegramError:
                continue

        if not managed_groups:
            await query.edit_message_text(get_text(lang, 'no_admin_groups_add'))
            return

        # Show list of groups with buttons
        keyboard = []
        for group_chat_id, group_title in managed_groups:
            keyboard.append([
                InlineKeyboardButton(
                    f"📋 {group_title}",
                    callback_data=f"start_setrules_{group_chat_id}"
                )
            ])

        # Add back button at the bottom
        keyboard.append([
            InlineKeyboardButton(
                get_text(lang, 'back_to_menu'),
                callback_data="back_to_help"
            )
        ])

        await query.edit_message_text(
            "📋 Qaysi guruh uchun qoidalarni o'rnatmoqchisiz?\n\nGuruhni tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Handle viewrules button
    if action == "help_viewrules":
        lang = get_user_language(query.from_user.id)
        user_id = query.from_user.id

        # Get all groups where user is admin
        managed_groups = []
        import sqlite3
        conn = sqlite3.connect('multi_tenant_moderation.db')
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id, chat_title FROM tenants WHERE chat_type IN ('group', 'supergroup')")
        all_groups = cursor.fetchall()
        conn.close()

        # Check which groups the user is admin in
        for group_chat_id, group_title in all_groups:
            try:
                chat_member = await context.bot.get_chat_member(
                    chat_id=group_chat_id,
                    user_id=user_id
                )
                if chat_member.status in ['creator', 'administrator']:
                    managed_groups.append((group_chat_id, group_title))
            except TelegramError:
                continue

        if not managed_groups:
            await query.edit_message_text(get_text(lang, 'no_admin_groups_add'))
            return

        # Show list of groups with buttons
        keyboard = []
        for group_chat_id, group_title in managed_groups:
            keyboard.append([
                InlineKeyboardButton(
                    f"👁️ {group_title}",
                    callback_data=f"viewrules_{group_chat_id}"
                )
            ])

        # Add back button at the bottom
        keyboard.append([
            InlineKeyboardButton(
                get_text(lang, 'back_to_menu'),
                callback_data="back_to_help"
            )
        ])

        await query.edit_message_text(
            "👁️ Qaysi guruhning qoidalarini ko'rmoqchisiz?\n\nGuruhni tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Handle setwelcome button
    if action == "help_setwelcome":
        lang = get_user_language(query.from_user.id)
        user_id = query.from_user.id

        # Get all groups where user is admin
        managed_groups = []
        import sqlite3
        conn = sqlite3.connect('multi_tenant_moderation.db')
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id, chat_title FROM tenants WHERE chat_type IN ('group', 'supergroup')")
        all_groups = cursor.fetchall()
        conn.close()

        # Check which groups the user is admin in
        for group_chat_id, group_title in all_groups:
            try:
                chat_member = await context.bot.get_chat_member(
                    chat_id=group_chat_id,
                    user_id=user_id
                )
                if chat_member.status in ['creator', 'administrator']:
                    managed_groups.append((group_chat_id, group_title))
            except TelegramError:
                continue

        if not managed_groups:
            await query.edit_message_text(get_text(lang, 'no_admin_groups_add'))
            return

        # Show list of groups with buttons
        keyboard = []
        for group_chat_id, group_title in managed_groups:
            keyboard.append([
                InlineKeyboardButton(
                    f"👋 {group_title}",
                    callback_data=f"start_setwelcome_{group_chat_id}"
                )
            ])

        # Add back button at the bottom
        keyboard.append([
            InlineKeyboardButton(
                get_text(lang, 'back_to_menu'),
                callback_data="back_to_help"
            )
        ])

        await query.edit_message_text(
            "👋 Qaysi guruh uchun xush kelibsiz xabarini o'rnatmoqchisiz?\n\nGuruhni tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Handle viewwelcome button
    if action == "help_viewwelcome":
        lang = get_user_language(query.from_user.id)
        user_id = query.from_user.id

        # Get all groups where user is admin
        managed_groups = []
        import sqlite3
        conn = sqlite3.connect('multi_tenant_moderation.db')
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id, chat_title FROM tenants WHERE chat_type IN ('group', 'supergroup')")
        all_groups = cursor.fetchall()
        conn.close()

        # Check which groups the user is admin in
        for group_chat_id, group_title in all_groups:
            try:
                chat_member = await context.bot.get_chat_member(
                    chat_id=group_chat_id,
                    user_id=user_id
                )
                if chat_member.status in ['creator', 'administrator']:
                    managed_groups.append((group_chat_id, group_title))
            except TelegramError:
                continue

        if not managed_groups:
            await query.edit_message_text(get_text(lang, 'no_admin_groups_add'))
            return

        # Show list of groups with buttons
        keyboard = []
        for group_chat_id, group_title in managed_groups:
            keyboard.append([
                InlineKeyboardButton(
                    f"👀 {group_title}",
                    callback_data=f"viewwelcome_{group_chat_id}"
                )
            ])

        # Add back button at the bottom
        keyboard.append([
            InlineKeyboardButton(
                get_text(lang, 'back_to_menu'),
                callback_data="back_to_help"
            )
        ])

        await query.edit_message_text(
            "👀 Qaysi guruhning xush kelibsiz xabarini ko'rmoqchisiz?\n\nGuruhni tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Handle set filter button
    if action == "help_setfilter":
        lang = get_user_language(query.from_user.id)
        user_id = query.from_user.id

        # Get all groups where user is admin
        managed_groups = []
        import sqlite3
        conn = sqlite3.connect('multi_tenant_moderation.db')
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id, chat_title FROM tenants WHERE chat_type IN ('group', 'supergroup')")
        all_groups = cursor.fetchall()
        conn.close()

        # Check which groups the user is admin in
        for group_chat_id, group_title in all_groups:
            try:
                chat_member = await context.bot.get_chat_member(
                    chat_id=group_chat_id,
                    user_id=user_id
                )
                if chat_member.status in ['creator', 'administrator']:
                    managed_groups.append((group_chat_id, group_title))
            except TelegramError:
                continue

        if not managed_groups:
            await query.edit_message_text(get_text(lang, 'no_admin_groups_add'))
            return

        # Show list of groups with buttons
        keyboard = []
        for group_chat_id, group_title in managed_groups:
            keyboard.append([
                InlineKeyboardButton(
                    f"🚫 {group_title}",
                    callback_data=f"start_setfilter_{group_chat_id}"
                )
            ])

        # Add back button at the bottom
        keyboard.append([
            InlineKeyboardButton(
                get_text(lang, 'back_to_menu'),
                callback_data="back_to_help"
            )
        ])

        await query.edit_message_text(
            "🚫 Qaysi guruhga filtr qo'shmoqchisiz?\n\nGuruhni tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Handle remove filter button
    if action == "help_removefilter":
        lang = get_user_language(query.from_user.id)
        user_id = query.from_user.id

        # Get all groups where user is admin
        managed_groups = []
        import sqlite3
        conn = sqlite3.connect('multi_tenant_moderation.db')
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id, chat_title FROM tenants WHERE chat_type IN ('group', 'supergroup')")
        all_groups = cursor.fetchall()
        conn.close()

        # Check which groups the user is admin in
        for group_chat_id, group_title in all_groups:
            try:
                chat_member = await context.bot.get_chat_member(
                    chat_id=group_chat_id,
                    user_id=user_id
                )
                if chat_member.status in ['creator', 'administrator']:
                    managed_groups.append((group_chat_id, group_title))
            except TelegramError:
                continue

        if not managed_groups:
            await query.edit_message_text(get_text(lang, 'no_admin_groups_add'))
            return

        # Show list of groups with buttons
        keyboard = []
        for group_chat_id, group_title in managed_groups:
            keyboard.append([
                InlineKeyboardButton(
                    f"✅ {group_title}",
                    callback_data=f"start_removefilter_{group_chat_id}"
                )
            ])

        # Add back button at the bottom
        keyboard.append([
            InlineKeyboardButton(
                get_text(lang, 'back_to_menu'),
                callback_data="back_to_help"
            )
        ])

        await query.edit_message_text(
            "✅ Qaysi guruhdan filtrni olib tashlamoqchisiz?\n\nGuruhni tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Handle view filters button
    if action == "help_viewfilters":
        lang = get_user_language(query.from_user.id)
        user_id = query.from_user.id

        # Get all groups where user is admin
        managed_groups = []
        import sqlite3
        conn = sqlite3.connect('multi_tenant_moderation.db')
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id, chat_title FROM tenants WHERE chat_type IN ('group', 'supergroup')")
        all_groups = cursor.fetchall()
        conn.close()

        # Check which groups the user is admin in
        for group_chat_id, group_title in all_groups:
            try:
                chat_member = await context.bot.get_chat_member(
                    chat_id=group_chat_id,
                    user_id=user_id
                )
                if chat_member.status in ['creator', 'administrator']:
                    managed_groups.append((group_chat_id, group_title))
            except TelegramError:
                continue

        if not managed_groups:
            await query.edit_message_text(get_text(lang, 'no_admin_groups_add'))
            return

        # Show list of groups with buttons
        keyboard = []
        for group_chat_id, group_title in managed_groups:
            keyboard.append([
                InlineKeyboardButton(
                    f"📝 {group_title}",
                    callback_data=f"viewfilters_{group_chat_id}"
                )
            ])

        # Add back button at the bottom
        keyboard.append([
            InlineKeyboardButton(
                get_text(lang, 'back_to_menu'),
                callback_data="back_to_help"
            )
        ])

        await query.edit_message_text(
            "📝 Qaysi guruhning filtrlarini ko'rmoqchisiz?\n\nGuruhni tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Handle settings button
    if action == "help_settings":
        lang = get_user_language(query.from_user.id)
        user_id = query.from_user.id

        # Get all groups where user is admin
        managed_groups = []
        import sqlite3
        conn = sqlite3.connect('multi_tenant_moderation.db')
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id, chat_title FROM tenants WHERE chat_type IN ('group', 'supergroup')")
        all_groups = cursor.fetchall()
        conn.close()

        # Check which groups the user is admin in
        for group_chat_id, group_title in all_groups:
            try:
                chat_member = await context.bot.get_chat_member(
                    chat_id=group_chat_id,
                    user_id=user_id
                )
                if chat_member.status in ['creator', 'administrator']:
                    managed_groups.append((group_chat_id, group_title))
            except TelegramError:
                continue

        if not managed_groups:
            await query.edit_message_text(get_text(lang, 'no_admin_groups'))
            return

        # Show list of groups with buttons
        keyboard = []
        for group_chat_id, group_title in managed_groups:
            keyboard.append([
                InlineKeyboardButton(
                    f"⚙️ {group_title}",
                    callback_data=f"show_settings_{group_chat_id}"
                )
            ])

        # Add back button at the bottom
        keyboard.append([
            InlineKeyboardButton(
                get_text(lang, 'back_to_menu'),
                callback_data="back_to_help"
            )
        ])

        await query.edit_message_text(
            get_text(lang, 'select_group_settings'),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return

    # Parse action: show_help_LANG or help_back_LANG
    parts = action.split('_')
    if len(parts) < 3:
        return

    if parts[0] == "show" and parts[1] == "help":
        # Show help menu
        lang = parts[2]

        # Build help text with commands organized by location
        help_text = (
            f"{get_text(lang, 'help_title')}\n\n"
            f"{get_text(lang, 'help_admin_group')}\n"
            f"{get_text(lang, 'help_ban')}\n"
            f"{get_text(lang, 'help_kick')}\n"
            f"{get_text(lang, 'help_mute')}\n"
            f"{get_text(lang, 'help_unmute')}\n"
            f"{get_text(lang, 'help_warn')}\n"
            f"{get_text(lang, 'help_unwarn')}\n"
            f"{get_text(lang, 'help_unban')}\n"
            f"{get_text(lang, 'help_info')}\n\n"
            f"{get_text(lang, 'help_users')}\n"
            f"{get_text(lang, 'help_rules')}"
        )

        # Create keyboard with settings, stats and back buttons
        keyboard = [
            [InlineKeyboardButton("⚙️ " + get_text(lang, 'help_settings'), callback_data="help_settings")],
            [InlineKeyboardButton("📋 " + get_text(lang, 'help_setrules_button'), callback_data="help_setrules")],
            [InlineKeyboardButton("👁️ " + get_text(lang, 'help_seerules_button'), callback_data="help_viewrules")],
            [InlineKeyboardButton("👋 " + get_text(lang, 'help_setwelcome_button'), callback_data="help_setwelcome")],
            [InlineKeyboardButton("👁️ " + get_text(lang, 'help_seewelcome_button'), callback_data="help_viewwelcome")],
            [InlineKeyboardButton("➕ " + get_text(lang, 'help_setfilter_button'), callback_data="help_setfilter")],
            [InlineKeyboardButton("➖ " + get_text(lang, 'help_removefilter_button'), callback_data="help_removefilter")],
            [InlineKeyboardButton("👁️ " + get_text(lang, 'help_viewfilters_button'), callback_data="help_viewfilters")],
            [InlineKeyboardButton("📊 " + get_text(lang, 'help_stats'), callback_data="help_stats")],
            [InlineKeyboardButton(get_text(lang, 'help_back_menu'), callback_data=f"help_back_{lang}")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(help_text, reply_markup=reply_markup)
        return

    category = parts[1]
    lang = parts[2]

    if category == "back":
        # Go back to start menu
        welcome_text = (
            f"{get_text(lang, 'start_greeting')}\n\n"
            f"{get_text(lang, 'start_description')}\n\n"
            f"{get_text(lang, 'start_instructions')}\n\n"
            f"{get_text(lang, 'start_list_1')}\n"
            f"{get_text(lang, 'start_list_2')}\n"
            f"{get_text(lang, 'start_list_3')}\n"
            f"{get_text(lang, 'start_list_4')}\n"
            f"{get_text(lang, 'start_list_5')}\n"
            f"{get_text(lang, 'start_list_6')}\n"
            f"{get_text(lang, 'start_list_7')}\n\n"
            f"{get_text(lang, 'start_footer')}\n"
            f"{get_text(lang, 'start_footer_text')}\n\n"
            f"{get_text(lang, 'start_commands_header')}\n\n"
            f"{get_text(lang, 'start_commands_text')}"
        )

        # Get bot username for the "Add to group" link
        bot_info = query.get_bot()
        bot_username = bot_info.username

        # Create keyboard without language buttons (only Uzbek supported)
        keyboard = [
            [InlineKeyboardButton(
                get_text(lang, 'add_to_group'),
                url=f"https://t.me/{bot_username}?startgroup=true"
            )],
            [InlineKeyboardButton(
                get_text(lang, 'show_help'),
                callback_data=f"show_help_{lang}"
            )]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(welcome_text, reply_markup=reply_markup)

@rate_limit(10)
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show group statistics - only works in private chat"""
    chat_type = update.effective_chat.type
    user_id = update.effective_user.id

    # Get user's language preference
    lang = get_user_language(user_id)

    # Only work in private chat
    if chat_type in ['group', 'supergroup']:
        await update.message.reply_text(
            get_text(lang, 'only_private')
        )
        return

    # Get all groups this bot is in and check if user is admin
    import sqlite3
    conn = sqlite3.connect('multi_tenant_moderation.db')
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id, chat_title FROM tenants WHERE chat_type IN ('group', 'supergroup')")
    all_groups = cursor.fetchall()
    conn.close()

    # Check which groups the user is admin in
    managed_groups = []
    for group_chat_id, group_title in all_groups:
        try:
            chat_member = await context.bot.get_chat_member(
                chat_id=group_chat_id,
                user_id=user_id
            )
            if chat_member.status in ['creator', 'administrator']:
                managed_groups.append((group_chat_id, group_title))
        except TelegramError:
            continue

    if not managed_groups:
        await update.message.reply_text(
            get_text(lang, 'no_admin_groups_add')
        )
        return

    # If only one group, show stats for that group
    if len(managed_groups) == 1:
        chat_id, chat_title = managed_groups[0]
        tenant = get_or_create_tenant(chat_id)
        lang = tenant.language
        stats = get_tenant_stats(chat_id)
        member_stats = get_member_activity_stats(chat_id)
        pending = len(tenant_pending_verifications.get(chat_id, {}))

        # Calculate growth indicators
        growth_7d_icon = "📈" if member_stats['net_growth_7d'] > 0 else "📉" if member_stats['net_growth_7d'] < 0 else "➡️"
        growth_30d_icon = "📈" if member_stats['net_growth_30d'] > 0 else "📉" if member_stats['net_growth_30d'] < 0 else "➡️"

        text = f"""
{get_text(lang, 'stats_title')}

**{get_text(lang, 'group')}:** {chat_title}

{get_text(lang, 'member_activity')}
• {get_text(lang, 'joined_7d')}: {member_stats['joined_7d']}
• {get_text(lang, 'left_7d')}: {member_stats['left_7d']}
• {get_text(lang, 'net_growth_7d')}: {member_stats['net_growth_7d']} {growth_7d_icon}

• {get_text(lang, 'joined_30d')}: {member_stats['joined_30d']}
• {get_text(lang, 'left_30d')}: {member_stats['left_30d']}
• {get_text(lang, 'net_growth_30d')}: {member_stats['net_growth_30d']} {growth_30d_icon}

{get_text(lang, 'database')}
• {get_text(lang, 'total_warnings')}: {stats['total_warnings']}
• {get_text(lang, 'total_filters')}: {stats['total_filters']}
• {get_text(lang, 'total_actions')}: {stats['total_actions']}

{get_text(lang, 'recent_actions')}
• {get_text(lang, 'bans')}: {stats['recent_bans']}
• {get_text(lang, 'kicks')}: {stats['recent_kicks']}
• {get_text(lang, 'mutes')}: {stats['recent_mutes']}
• {get_text(lang, 'warnings')}: {stats['recent_warns']}

{get_text(lang, 'current_session')}
• {get_text(lang, 'active_verifications')}: {pending}
• {get_text(lang, 'tracked_users')}: {len(tenant_flood_tracking.get(chat_id, {}))}
        """
        await update.message.reply_text(text, parse_mode='Markdown')
    else:
        # Multiple groups - show buttons to select which group
        keyboard = []
        for group_chat_id, group_title in managed_groups:
            keyboard.append([
                InlineKeyboardButton(
                    f"📊 {group_title}",
                    callback_data=f"stats_{group_chat_id}"
                )
            ])

        await update.message.reply_text(
            get_text(lang, 'select_group_stats'),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle stats group selection"""
    query = update.callback_query
    await query.answer()

    # Extract chat_id from callback data
    chat_id = int(query.data.replace('stats_', ''))

    # Verify user is admin in that group
    try:
        chat_member = await context.bot.get_chat_member(
            chat_id=chat_id,
            user_id=query.from_user.id
        )
        if chat_member.status not in ['creator', 'administrator']:
            tenant = get_or_create_tenant(chat_id)
            await query.answer(get_text(tenant.language, 'no_permission'), show_alert=True)
            return
    except TelegramError:
        lang = get_user_language(query.from_user.id)
        await query.answer(get_text(lang, 'permission_error'), show_alert=True)
        return

    # Get group title
    try:
        chat = await context.bot.get_chat(chat_id)
        chat_title = chat.title
    except TelegramError:
        chat_title = "Unknown Group"

    # Get stats
    tenant = get_or_create_tenant(chat_id)
    lang = tenant.language
    stats = get_tenant_stats(chat_id)
    member_stats = get_member_activity_stats(chat_id)
    pending = len(tenant_pending_verifications.get(chat_id, {}))

    # Calculate growth indicators
    growth_7d_icon = "📈" if member_stats['net_growth_7d'] > 0 else "📉" if member_stats['net_growth_7d'] < 0 else "➡️"
    growth_30d_icon = "📈" if member_stats['net_growth_30d'] > 0 else "📉" if member_stats['net_growth_30d'] < 0 else "➡️"

    text = f"""
{get_text(lang, 'stats_title')}

**{get_text(lang, 'group')}:** {chat_title}

{get_text(lang, 'member_activity')}
• {get_text(lang, 'joined_7d')}: {member_stats['joined_7d']}
• {get_text(lang, 'left_7d')}: {member_stats['left_7d']}
• {get_text(lang, 'net_growth_7d')}: {member_stats['net_growth_7d']} {growth_7d_icon}

• {get_text(lang, 'joined_30d')}: {member_stats['joined_30d']}
• {get_text(lang, 'left_30d')}: {member_stats['left_30d']}
• {get_text(lang, 'net_growth_30d')}: {member_stats['net_growth_30d']} {growth_30d_icon}

{get_text(lang, 'database')}
• {get_text(lang, 'total_warnings')}: {stats['total_warnings']}
• {get_text(lang, 'total_filters')}: {stats['total_filters']}
• {get_text(lang, 'total_actions')}: {stats['total_actions']}

{get_text(lang, 'recent_actions')}
• {get_text(lang, 'bans')}: {stats['recent_bans']}
• {get_text(lang, 'kicks')}: {stats['recent_kicks']}
• {get_text(lang, 'mutes')}: {stats['recent_mutes']}
• {get_text(lang, 'warnings')}: {stats['recent_warns']}

{get_text(lang, 'current_session')}
• {get_text(lang, 'active_verifications')}: {pending}
• {get_text(lang, 'tracked_users')}: {len(tenant_flood_tracking.get(chat_id, {}))}
    """

    # Add back button
    keyboard = [
        [InlineKeyboardButton(
            get_text(lang, 'back_to_menu'),
            callback_data="help_stats"
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

@rate_limit(5)
@group_only
@admin_only
async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get information about a user"""
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
    else:
        user = update.effective_user

    chat_id = update.effective_chat.id

    # Get user status
    try:
        member = await context.bot.get_chat_member(chat_id, user.id)
        status = member.status.upper()
    except TelegramError:
        status = "UNKNOWN"

    # Get warnings
    warnings = get_warnings(chat_id, user.id)
    tenant = get_or_create_tenant(chat_id)
    lang = tenant.language

    text = (
        f"👤 <b>{get_text(lang, 'info_title')}</b>\n\n"
        f"<b>{get_text(lang, 'info_name')}:</b> {user.mention_html()}\n"
        f"<b>{get_text(lang, 'info_user_id')}:</b> <code>{user.id}</code>\n"
        f"<b>{get_text(lang, 'info_username')}:</b> @{user.username if user.username else get_text(lang, 'info_none')}\n"
        f"<b>{get_text(lang, 'info_status')}:</b> {status}\n"
        f"<b>{get_text(lang, 'info_warnings')}:</b> {warnings}/{tenant.max_warnings}\n"
        f"<b>{get_text(lang, 'info_is_bot')}:</b> {get_text(lang, 'info_yes') if user.is_bot else get_text(lang, 'info_no')}\n"
        f"<b>{get_text(lang, 'info_tenant_id')}:</b> <code>{chat_id}</code>"
    )

    await update.message.reply_text(text, parse_mode='HTML')

@rate_limit(10)
@group_only
async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show group rules"""
    chat_id = update.effective_chat.id
    tenant = get_or_create_tenant(chat_id)
    lang = tenant.language

    if tenant.rules_text:
        rules = tenant.rules_text
    else:
        rules = f"{get_text(lang, 'default_rules_title')}\n\n{get_text(lang, 'default_rules')}"

    await update.message.reply_text(rules, parse_mode='Markdown')

@rate_limit(5)
async def set_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set custom group rules - works in both group and private chat"""
    chat_type = update.effective_chat.type
    user_id = update.effective_user.id

    # If in group, set rules directly (admin check)
    if chat_type in ['group', 'supergroup']:
        # Check if user is admin
        if not await is_admin(update, context):
            tenant = get_or_create_tenant(update.effective_chat.id)
            await update.message.reply_text(get_text(tenant.language, 'admin_only'))
            return

        chat_id = update.effective_chat.id
        tenant = get_or_create_tenant(chat_id)
        lang = tenant.language

        if update.message.reply_to_message and update.message.reply_to_message.text:
            rules_text = update.message.reply_to_message.text
        elif context.args:
            rules_text = ' '.join(context.args)
        else:
            await update.message.reply_text(
                get_text(lang, 'setrules_usage'),
                parse_mode='Markdown'
            )
            return

        update_tenant_config(chat_id, rules_text=rules_text)
        await update.message.reply_text(get_text(lang, 'rules_updated'))
        return

    # In private chat - show list of groups to configure
    lang = get_user_language(user_id)
    import sqlite3
    conn = sqlite3.connect('multi_tenant_moderation.db')
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id, chat_title FROM tenants WHERE chat_type IN ('group', 'supergroup')")
    all_groups = cursor.fetchall()
    conn.close()

    # Check which groups the user is admin in
    managed_groups = []
    for group_chat_id, group_title in all_groups:
        try:
            chat_member = await context.bot.get_chat_member(
                chat_id=group_chat_id,
                user_id=user_id
            )
            if chat_member.status in ['creator', 'administrator']:
                managed_groups.append((group_chat_id, group_title))
        except TelegramError:
            continue

    if not managed_groups:
        await update.message.reply_text(
            get_text(lang, 'setwelcome_no_groups')
        )
        return

    # Check if user provided rules text
    if update.message.reply_to_message and update.message.reply_to_message.text:
        rules_text = update.message.reply_to_message.text
    elif context.args:
        rules_text = ' '.join(context.args)
    else:
        # Show simple instructions
        groups_list = "\n".join([f"• {title}" for _, title in managed_groups])
        help_text = get_text(lang, 'setrules_usage')
        help_text += f"\n\n**Siz admin bo'lgan guruhlar:**\n{groups_list}"
        await update.message.reply_text(help_text, parse_mode='Markdown')
        return

    # If only one group, set it for that group
    if len(managed_groups) == 1:
        chat_id = managed_groups[0][0]
        group_title = managed_groups[0][1]
        update_tenant_config(chat_id, rules_text=rules_text)
        await update.message.reply_text(
            f"✅ {group_title} uchun qoidalar yangilandi.",
            parse_mode='Markdown'
        )
    else:
        # Multiple groups - show buttons to select which group
        keyboard = []
        for group_chat_id, group_title in managed_groups:
            keyboard.append([
                InlineKeyboardButton(
                    f"{group_title}",
                    callback_data=f"setrules_{group_chat_id}"
                )
            ])

        # Store the rules text in context for later use
        context.user_data['pending_rules_text'] = rules_text

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "📋 Qaysi guruh uchun qoidalarni o'rnatmoqchisiz?",
            reply_markup=reply_markup
        )

@rate_limit(5)
async def see_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View the current custom rules for the group"""
    chat_type = update.effective_chat.type
    user_id = update.effective_user.id

    # If in group, show rules directly (admin check)
    if chat_type in ['group', 'supergroup']:
        # Check if user is admin
        if not await is_admin(update, context):
            tenant = get_or_create_tenant(update.effective_chat.id)
            await update.message.reply_text(get_text(tenant.language, 'admin_only'))
            return

        chat_id = update.effective_chat.id
        tenant = get_or_create_tenant(chat_id)
        lang = tenant.language
        chat_title = update.effective_chat.title

        # Check if custom rules are set
        if not tenant.rules_text:
            await update.message.reply_text(
                get_text(lang, 'seerules_not_set'),
                parse_mode='Markdown'
            )
            return

        # Show current custom rules
        text = f"{get_text(lang, 'seerules_title')}\n\n{get_text(lang, 'seerules_current', group_title=chat_title, rules_text=tenant.rules_text)}"
        await update.message.reply_text(text, parse_mode='Markdown')
        return

    # In private chat - show list of groups to select
    lang = get_user_language(user_id)
    import sqlite3
    conn = sqlite3.connect('multi_tenant_moderation.db')
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id, chat_title FROM tenants WHERE chat_type IN ('group', 'supergroup')")
    all_groups = cursor.fetchall()
    conn.close()

    # Check which groups the user is admin in
    managed_groups = []
    for group_chat_id, group_title in all_groups:
        try:
            chat_member = await context.bot.get_chat_member(
                chat_id=group_chat_id,
                user_id=user_id
            )
            if chat_member.status in ['creator', 'administrator']:
                managed_groups.append((group_chat_id, group_title))
        except TelegramError:
            continue

    if not managed_groups:
        await update.message.reply_text(
            get_text(lang, 'setwelcome_no_groups')
        )
        return

    # Show buttons to select which group (show all groups, not just ones with custom rules)
    keyboard = []
    for group_chat_id, group_title in managed_groups:
        keyboard.append([
            InlineKeyboardButton(
                f"{group_title}",
                callback_data=f"seerules_{group_chat_id}"
            )
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📋 Qaysi guruh qoidalarini ko'rmoqchisiz?",
        reply_markup=reply_markup
    )

@rate_limit(10)
async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simple welcome message setup - must be used in private chat"""
    chat_type = update.effective_chat.type
    user_id = update.effective_user.id
    lang = get_user_language(user_id)

    # Only work in private chat
    if chat_type in ['group', 'supergroup']:
        await update.message.reply_text(
            get_text(lang, 'setwelcome_private_only')
        )
        return

    # In private chat - show list of groups to configure
    import sqlite3
    conn = sqlite3.connect('multi_tenant_moderation.db')
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id, chat_title FROM tenants WHERE chat_type IN ('group', 'supergroup')")
    all_groups = cursor.fetchall()
    conn.close()

    # Check which groups the user is admin in
    managed_groups = []
    for group_chat_id, group_title in all_groups:
        try:
            chat_member = await context.bot.get_chat_member(
                chat_id=group_chat_id,
                user_id=user_id
            )
            if chat_member.status in ['creator', 'administrator']:
                managed_groups.append((group_chat_id, group_title))
        except TelegramError:
            continue

    if not managed_groups:
        await update.message.reply_text(
            get_text(lang, 'setwelcome_no_groups')
        )
        return

    # Check if user provided welcome message
    if update.message.reply_to_message and update.message.reply_to_message.text:
        welcome_text = update.message.reply_to_message.text
    elif context.args:
        welcome_text = ' '.join(context.args)
    else:
        # Show simple instructions
        groups_list = "\n".join([f"• {title}" for _, title in managed_groups])
        help_text = get_text(lang, 'setwelcome_help', groups_list=groups_list)
        await update.message.reply_text(help_text, parse_mode='Markdown')
        return

    # If only one group, set it for that group and show preview
    if len(managed_groups) == 1:
        chat_id = managed_groups[0][0]
        group_title = managed_groups[0][1]
        update_tenant_config(chat_id, welcome_message=welcome_text)

        # Generate preview
        from datetime import datetime
        preview = welcome_text.replace('[user]', update.effective_user.first_name)
        preview = preview.replace('[group]', group_title)
        preview = preview.replace('[time]', datetime.now().strftime('%H:%M'))

        await update.message.reply_text(
            get_text(lang, 'setwelcome_preview', preview=preview, group_title=group_title),
            parse_mode='Markdown'
        )
    else:
        # Multiple groups - show buttons to select which group
        keyboard = []
        for group_chat_id, group_title in managed_groups:
            keyboard.append([
                InlineKeyboardButton(
                    f"Set for: {group_title}",
                    callback_data=f"setwelcome_{group_chat_id}"
                )
            ])

        # Store the welcome message in context for later use
        context.user_data['pending_welcome_message'] = welcome_text

        await update.message.reply_text(
            get_text(lang, 'setwelcome_select_group'),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def setwelcome_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle welcome message group selection"""
    query = update.callback_query
    await query.answer()

    # Extract chat_id from callback data
    chat_id = int(query.data.replace('setwelcome_', ''))

    # Verify user is admin in that group
    try:
        chat_member = await context.bot.get_chat_member(
            chat_id=chat_id,
            user_id=query.from_user.id
        )
        if chat_member.status not in ['creator', 'administrator']:
            tenant = get_or_create_tenant(chat_id)
            await query.answer(get_text(tenant.language, 'no_permission'), show_alert=True)
            return
    except TelegramError:
        lang = get_user_language(query.from_user.id)
        await query.answer(get_text(lang, 'permission_error'), show_alert=True)
        return

    # Get the welcome message from user_data
    welcome_text = context.user_data.get('pending_welcome_message')
    lang = get_user_language(query.from_user.id)
    if not welcome_text:
        await query.edit_message_text("❌ Error: Welcome message not found. Please try again.")
        return

    # Get group title
    try:
        chat = await context.bot.get_chat(chat_id)
        group_title = chat.title
    except TelegramError:
        group_title = "Unknown Group"

    # Update the welcome message
    update_tenant_config(chat_id, welcome_message=welcome_text)

    # Clear the pending message
    context.user_data.pop('pending_welcome_message', None)

    # Generate preview
    from datetime import datetime
    preview = welcome_text.replace('[user]', query.from_user.first_name)
    preview = preview.replace('[group]', group_title)
    preview = preview.replace('[time]', datetime.now().strftime('%H:%M'))

    await query.edit_message_text(
        get_text(lang, 'setwelcome_success', preview=preview, group_title=group_title),
        parse_mode='Markdown'
    )

async def handle_private_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages in private chat (for conversation states like setting rules/welcome)"""
    # Only process private chat messages
    if update.effective_chat.type != 'private':
        return

    # Check if user is waiting to input welcome message
    if 'waiting_for_welcome' in context.user_data:
        chat_id = context.user_data['waiting_for_welcome']
        group_title = context.user_data.get('waiting_for_welcome_group_title', 'the group')
        welcome_text = update.message.text

        # Update the welcome message for the selected group
        update_tenant_config(chat_id, welcome_message=welcome_text)

        # Clear the waiting state
        del context.user_data['waiting_for_welcome']
        if 'waiting_for_welcome_group_title' in context.user_data:
            del context.user_data['waiting_for_welcome_group_title']

        # Get user language
        lang = get_user_language(update.effective_user.id)

        # Create back to menu button
        keyboard = [
            [InlineKeyboardButton(
                get_text(lang, 'back_to_menu'),
                callback_data="back_to_help"
            )]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send confirmation with back button
        await update.message.reply_text(
            f"✅ **{group_title}** uchun xush kelibsiz xabari muvaffaqiyatli yangilandi!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return

    # Check if user is waiting to input rules
    if 'waiting_for_rules' in context.user_data:
        chat_id = context.user_data['waiting_for_rules']
        group_title = context.user_data.get('waiting_for_rules_group_title', 'the group')
        rules_text = update.message.text

        # Update the rules for the selected group
        update_tenant_config(chat_id, rules_text=rules_text)

        # Clear the waiting state
        del context.user_data['waiting_for_rules']
        if 'waiting_for_rules_group_title' in context.user_data:
            del context.user_data['waiting_for_rules_group_title']

        # Get user language
        lang = get_user_language(update.effective_user.id)

        # Create back to menu button
        keyboard = [
            [InlineKeyboardButton(
                get_text(lang, 'back_to_menu'),
                callback_data="back_to_help"
            )]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send confirmation with back button
        await update.message.reply_text(
            f"✅ **{group_title}** uchun qoidalar muvaffaqiyatli yangilandi!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return

    # Check if user is waiting to input filter word
    if 'waiting_for_filter' in context.user_data:
        chat_id = context.user_data['waiting_for_filter']
        group_title = context.user_data.get('waiting_for_filter_group_title', 'the group')
        filter_text = update.message.text.strip().lower()

        # Split by comma and clean up each word
        filter_words = [word.strip() for word in filter_text.split(',') if word.strip()]

        # Add all filter words
        added_count = 0
        for word in filter_words:
            add_filtered_word(chat_id, word)
            added_count += 1

        # Clear the waiting state
        del context.user_data['waiting_for_filter']
        if 'waiting_for_filter_group_title' in context.user_data:
            del context.user_data['waiting_for_filter_group_title']

        # Get user language
        lang = get_user_language(update.effective_user.id)

        # Create back to menu button
        keyboard = [
            [InlineKeyboardButton(
                get_text(lang, 'back_to_menu'),
                callback_data="back_to_help"
            )]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send confirmation with back button
        if added_count == 1:
            await update.message.reply_text(
                f"✅ **{group_title}** uchun `{filter_words[0]}` so'zi filtrga qo'shildi!",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            words_list = ', '.join([f"`{w}`" for w in filter_words])
            await update.message.reply_text(
                f"✅ **{group_title}** uchun {added_count} ta so'z filtrga qo'shildi:\n{words_list}",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        return

    # Check if user is waiting to input unfilter word
    if 'waiting_for_unfilter' in context.user_data:
        chat_id = context.user_data['waiting_for_unfilter']
        group_title = context.user_data.get('waiting_for_unfilter_group_title', 'the group')
        filter_text = update.message.text.strip().lower()

        # Split by comma and clean up each word
        filter_words = [word.strip() for word in filter_text.split(',') if word.strip()]

        # Remove all filter words
        removed_count = 0
        for word in filter_words:
            remove_filtered_word(chat_id, word)
            removed_count += 1

        # Clear the waiting state
        del context.user_data['waiting_for_unfilter']
        if 'waiting_for_unfilter_group_title' in context.user_data:
            del context.user_data['waiting_for_unfilter_group_title']

        # Get user language
        lang = get_user_language(update.effective_user.id)

        # Create back to menu button
        keyboard = [
            [InlineKeyboardButton(
                get_text(lang, 'back_to_menu'),
                callback_data="back_to_help"
            )]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send confirmation with back button
        if removed_count == 1:
            await update.message.reply_text(
                f"✅ **{group_title}** uchun `{filter_words[0]}` so'zi filtrdan olib tashlandi!",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            words_list = ', '.join([f"`{w}`" for w in filter_words])
            await update.message.reply_text(
                f"✅ **{group_title}** uchun {removed_count} ta so'z filtrdan olib tashlandi:\n{words_list}",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        return

async def start_setrules_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle initial group selection for setting rules (from button menu)"""
    query = update.callback_query
    await query.answer()

    # Extract chat_id from callback data
    chat_id = int(query.data.replace('start_setrules_', ''))

    # Verify user is admin in that group
    try:
        chat_member = await context.bot.get_chat_member(
            chat_id=chat_id,
            user_id=query.from_user.id
        )
        if chat_member.status not in ['creator', 'administrator']:
            tenant = get_or_create_tenant(chat_id)
            await query.answer(get_text(tenant.language, 'no_permission'), show_alert=True)
            return
    except TelegramError:
        lang = get_user_language(query.from_user.id)
        await query.answer(get_text(lang, 'permission_error'), show_alert=True)
        return

    # Get group title
    try:
        chat = await context.bot.get_chat(chat_id)
        group_title = chat.title
    except TelegramError:
        group_title = "Unknown Group"

    # Store the target chat_id in user data and set waiting state
    context.user_data['waiting_for_rules'] = chat_id
    context.user_data['waiting_for_rules_group_title'] = group_title

    await query.edit_message_text(
        f"📋 **{group_title}** uchun qoidalarni kiriting.\n\n"
        f"Iltimos, guruh qoidalarini matn sifatida yuboring:",
        parse_mode='Markdown'
    )

async def setrules_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle rules group selection (from /setrules command)"""
    query = update.callback_query
    await query.answer()

    # Extract chat_id from callback data
    chat_id = int(query.data.replace('setrules_', ''))

    # Verify user is admin in that group
    try:
        chat_member = await context.bot.get_chat_member(
            chat_id=chat_id,
            user_id=query.from_user.id
        )
        if chat_member.status not in ['creator', 'administrator']:
            tenant = get_or_create_tenant(chat_id)
            await query.answer(get_text(tenant.language, 'no_permission'), show_alert=True)
            return
    except TelegramError:
        lang = get_user_language(query.from_user.id)
        await query.answer(get_text(lang, 'permission_error'), show_alert=True)
        return

    # Get the rules text from user_data
    rules_text = context.user_data.get('pending_rules_text')
    lang = get_user_language(query.from_user.id)
    if not rules_text:
        await query.edit_message_text("❌ Error: Rules text not found. Please try again.")
        return

    # Get group title
    try:
        chat = await context.bot.get_chat(chat_id)
        group_title = chat.title
    except TelegramError:
        group_title = "Unknown Group"

    # Update the rules
    update_tenant_config(chat_id, rules_text=rules_text)

    # Clear the pending rules
    context.user_data.pop('pending_rules_text', None)

    await query.edit_message_text(
        f"✅ **{group_title}** uchun qoidalar yangilandi.",
        parse_mode='Markdown'
    )

async def seewelcome_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle viewing welcome message from group selection"""
    query = update.callback_query
    await query.answer()

    # Extract chat_id from callback data
    chat_id = int(query.data.replace('seewelcome_', ''))

    # Verify user is admin in that group
    try:
        chat_member = await context.bot.get_chat_member(
            chat_id=chat_id,
            user_id=query.from_user.id
        )
        if chat_member.status not in ['creator', 'administrator']:
            tenant = get_or_create_tenant(chat_id)
            await query.answer(get_text(tenant.language, 'no_permission'), show_alert=True)
            return
    except TelegramError:
        lang = get_user_language(query.from_user.id)
        await query.answer(get_text(lang, 'permission_error'), show_alert=True)
        return

    # Get tenant and display welcome message
    tenant = get_or_create_tenant(chat_id)
    lang = tenant.language

    # Get group title
    try:
        chat = await context.bot.get_chat(chat_id)
        group_title = chat.title
    except TelegramError:
        group_title = "Unknown Group"

    # Show current welcome message
    text = f"{get_text(lang, 'viewwelcome_title')}\n\n{get_text(lang, 'viewwelcome_current', group_title=group_title, welcome_message=tenant.welcome_message)}"

    # Add status if disabled
    if not tenant.welcome_enabled:
        text = f"{text}\n\n{get_text(lang, 'viewwelcome_disabled')}"

    await query.edit_message_text(text, parse_mode='Markdown')

async def start_setwelcome_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle initial group selection for setting welcome message (from button menu)"""
    query = update.callback_query
    await query.answer()

    # Extract chat_id from callback data
    chat_id = int(query.data.replace('start_setwelcome_', ''))

    # Verify user is admin in that group
    try:
        chat_member = await context.bot.get_chat_member(
            chat_id=chat_id,
            user_id=query.from_user.id
        )
        if chat_member.status not in ['creator', 'administrator']:
            tenant = get_or_create_tenant(chat_id)
            await query.answer(get_text(tenant.language, 'no_permission'), show_alert=True)
            return
    except TelegramError:
        lang = get_user_language(query.from_user.id)
        await query.answer(get_text(lang, 'permission_error'), show_alert=True)
        return

    # Get group title
    try:
        chat = await context.bot.get_chat(chat_id)
        group_title = chat.title
    except TelegramError:
        group_title = "Unknown Group"

    # Store the target chat_id in user data and set waiting state
    context.user_data['waiting_for_welcome'] = chat_id
    context.user_data['waiting_for_welcome_group_title'] = group_title

    await query.edit_message_text(
        f"👋 **{group_title}** uchun xush kelibsiz xabarini kiriting.\n\n"
        f"Iltimos, xush kelibsiz xabarini matn sifatida yuboring:\n\n"
        f"**Maxsus teglar:**\n"
        f"`[user]` - Foydalanuvchi ismi\n"
        f"`[group]` - Guruh nomi\n"
        f"`[time]` - Joriy vaqt",
        parse_mode='Markdown'
    )

async def viewwelcome_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle viewing welcome message from button menu"""
    query = update.callback_query
    await query.answer()

    # Extract chat_id from callback data
    chat_id = int(query.data.replace('viewwelcome_', ''))

    # Verify user is admin in that group
    try:
        chat_member = await context.bot.get_chat_member(
            chat_id=chat_id,
            user_id=query.from_user.id
        )
        if chat_member.status not in ['creator', 'administrator']:
            tenant = get_or_create_tenant(chat_id)
            await query.answer(get_text(tenant.language, 'no_permission'), show_alert=True)
            return
    except TelegramError:
        lang = get_user_language(query.from_user.id)
        await query.answer(get_text(lang, 'permission_error'), show_alert=True)
        return

    # Get tenant and display welcome message
    tenant = get_or_create_tenant(chat_id)
    lang = tenant.language

    # Get group title
    try:
        chat = await context.bot.get_chat(chat_id)
        group_title = chat.title
    except TelegramError:
        group_title = "Unknown Group"

    # Check if welcome message is set
    if not tenant.welcome_message:
        text = f"👋 **{group_title}**\n\n{get_text(lang, 'viewwelcome_not_set')}"
    else:
        # Show current welcome message
        text = f"{get_text(lang, 'viewwelcome_title')}\n\n{get_text(lang, 'viewwelcome_current', group_title=group_title, welcome_message=tenant.welcome_message)}"

        # Add status if disabled
        if not tenant.welcome_enabled:
            text = f"{text}\n\n{get_text(lang, 'viewwelcome_disabled')}"

    # Add back button
    keyboard = [
        [InlineKeyboardButton(
            get_text(lang, 'back_to_menu'),
            callback_data="back_to_help"
        )]
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def viewrules_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle viewing rules from button menu"""
    query = update.callback_query
    await query.answer()

    # Extract chat_id from callback data
    chat_id = int(query.data.replace('viewrules_', ''))

    # Verify user is admin in that group
    try:
        chat_member = await context.bot.get_chat_member(
            chat_id=chat_id,
            user_id=query.from_user.id
        )
        if chat_member.status not in ['creator', 'administrator']:
            tenant = get_or_create_tenant(chat_id)
            await query.answer(get_text(tenant.language, 'no_permission'), show_alert=True)
            return
    except TelegramError:
        lang = get_user_language(query.from_user.id)
        await query.answer(get_text(lang, 'permission_error'), show_alert=True)
        return

    # Get tenant and display rules
    tenant = get_or_create_tenant(chat_id)
    lang = tenant.language

    # Get group title
    try:
        chat = await context.bot.get_chat(chat_id)
        group_title = chat.title
    except TelegramError:
        group_title = "Unknown Group"

    # Show custom rules or default rules
    if tenant.rules_text:
        text = f"{get_text(lang, 'seerules_title')}\n\n{get_text(lang, 'seerules_current', group_title=group_title, rules_text=tenant.rules_text)}"
    else:
        # Show default rules
        rules = f"{get_text(lang, 'default_rules_title')}\n\n{get_text(lang, 'default_rules')}"
        text = f"📋 **{group_title}**\n\n{rules}"

    # Add back button
    keyboard = [
        [InlineKeyboardButton(
            get_text(lang, 'back_to_menu'),
            callback_data="back_to_help"
        )]
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def seerules_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle viewing rules from group selection"""
    query = update.callback_query
    await query.answer()

    # Extract chat_id from callback data
    chat_id = int(query.data.replace('seerules_', ''))

    # Verify user is admin in that group
    try:
        chat_member = await context.bot.get_chat_member(
            chat_id=chat_id,
            user_id=query.from_user.id
        )
        if chat_member.status not in ['creator', 'administrator']:
            tenant = get_or_create_tenant(chat_id)
            await query.answer(get_text(tenant.language, 'no_permission'), show_alert=True)
            return
    except TelegramError:
        lang = get_user_language(query.from_user.id)
        await query.answer(get_text(lang, 'permission_error'), show_alert=True)
        return

    # Get tenant and display rules
    tenant = get_or_create_tenant(chat_id)
    lang = tenant.language

    # Get group title
    try:
        chat = await context.bot.get_chat(chat_id)
        group_title = chat.title
    except TelegramError:
        group_title = "Unknown Group"

    # Show custom rules or default rules
    if tenant.rules_text:
        text = f"{get_text(lang, 'seerules_title')}\n\n{get_text(lang, 'seerules_current', group_title=group_title, rules_text=tenant.rules_text)}"
    else:
        # Show default rules
        rules = f"{get_text(lang, 'default_rules_title')}\n\n{get_text(lang, 'default_rules')}"
        text = f"📋 **{group_title}**\n\n{rules}"

    await query.edit_message_text(text, parse_mode='Markdown')

async def start_setfilter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle adding filter word (from button menu)"""
    query = update.callback_query
    await query.answer()

    # Extract chat_id from callback data
    chat_id = int(query.data.replace('start_setfilter_', ''))

    # Verify user is admin in that group
    try:
        chat_member = await context.bot.get_chat_member(
            chat_id=chat_id,
            user_id=query.from_user.id
        )
        if chat_member.status not in ['creator', 'administrator']:
            tenant = get_or_create_tenant(chat_id)
            await query.answer(get_text(tenant.language, 'no_permission'), show_alert=True)
            return
    except TelegramError:
        lang = get_user_language(query.from_user.id)
        await query.answer(get_text(lang, 'permission_error'), show_alert=True)
        return

    # Get group title
    try:
        chat = await context.bot.get_chat(chat_id)
        group_title = chat.title
    except TelegramError:
        group_title = "Unknown Group"

    # Store the target chat_id in user data and set waiting state
    context.user_data['waiting_for_filter'] = chat_id
    context.user_data['waiting_for_filter_group_title'] = group_title

    await query.edit_message_text(
        f"🚫 **{group_title}** uchun filtrlash kerak bo'lgan so'z(lar)ni kiriting.\n\n"
        f"Iltimos, so'z(lar)ni matn sifatida yuboring.\n"
        f"Bir nechta so'zni vergul bilan ajrating: `so'z1, so'z2, so'z3`",
        parse_mode='Markdown'
    )

async def start_removefilter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle removing filter word (from button menu)"""
    query = update.callback_query
    await query.answer()

    # Extract chat_id from callback data
    chat_id = int(query.data.replace('start_removefilter_', ''))

    # Verify user is admin in that group
    try:
        chat_member = await context.bot.get_chat_member(
            chat_id=chat_id,
            user_id=query.from_user.id
        )
        if chat_member.status not in ['creator', 'administrator']:
            tenant = get_or_create_tenant(chat_id)
            await query.answer(get_text(tenant.language, 'no_permission'), show_alert=True)
            return
    except TelegramError:
        lang = get_user_language(query.from_user.id)
        await query.answer(get_text(lang, 'permission_error'), show_alert=True)
        return

    # Get group title
    try:
        chat = await context.bot.get_chat(chat_id)
        group_title = chat.title
    except TelegramError:
        group_title = "Unknown Group"

    # Store the target chat_id in user data and set waiting state
    context.user_data['waiting_for_unfilter'] = chat_id
    context.user_data['waiting_for_unfilter_group_title'] = group_title

    await query.edit_message_text(
        f"✅ **{group_title}** uchun olib tashlash kerak bo'lgan filtr so'z(lar)ini kiriting.\n\n"
        f"Iltimos, so'z(lar)ni matn sifatida yuboring.\n"
        f"Bir nechta so'zni vergul bilan ajrating: `so'z1, so'z2, so'z3`",
        parse_mode='Markdown'
    )

async def viewfilters_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle viewing filters from button menu"""
    query = update.callback_query
    await query.answer()

    # Extract chat_id from callback data
    chat_id = int(query.data.replace('viewfilters_', ''))

    # Verify user is admin in that group
    try:
        chat_member = await context.bot.get_chat_member(
            chat_id=chat_id,
            user_id=query.from_user.id
        )
        if chat_member.status not in ['creator', 'administrator']:
            tenant = get_or_create_tenant(chat_id)
            await query.answer(get_text(tenant.language, 'no_permission'), show_alert=True)
            return
    except TelegramError:
        lang = get_user_language(query.from_user.id)
        await query.answer(get_text(lang, 'permission_error'), show_alert=True)
        return

    # Get tenant and display filters
    tenant = get_or_create_tenant(chat_id)
    lang = tenant.language

    # Get group title
    try:
        chat = await context.bot.get_chat(chat_id)
        group_title = chat.title
    except TelegramError:
        group_title = "Unknown Group"

    # Get filtered words
    filtered_words = get_filtered_words(chat_id)

    if not filtered_words:
        text = f"📝 **{group_title}**\n\nHozircha filtrlangan so'zlar yo'q."
    else:
        words_list = '\n'.join([f"• `{word}`" for word in filtered_words])
        text = f"📝 **{group_title}**\n\nFiltrlangan so'zlar:\n\n{words_list}"

    # Add back button
    keyboard = [
        [InlineKeyboardButton(
            get_text(lang, 'back_to_menu'),
            callback_data="back_to_help"
        )]
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

@rate_limit(5)
async def view_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View the current welcome message for the group"""
    chat_type = update.effective_chat.type
    user_id = update.effective_user.id

    # If in group, show welcome message directly (admin check)
    if chat_type in ['group', 'supergroup']:
        # Check if user is admin
        if not await is_admin(update, context):
            tenant = get_or_create_tenant(update.effective_chat.id)
            await update.message.reply_text(get_text(tenant.language, 'admin_only'))
            return

        chat_id = update.effective_chat.id
        tenant = get_or_create_tenant(chat_id)
        lang = tenant.language
        chat_title = update.effective_chat.title

        # Check if welcome message is set
        if not tenant.welcome_message:
            await update.message.reply_text(
                get_text(lang, 'viewwelcome_not_set'),
                parse_mode='Markdown'
            )
            return

        # Show current welcome message
        text = f"{get_text(lang, 'viewwelcome_title')}\n\n{get_text(lang, 'viewwelcome_current', group_title=chat_title, welcome_message=tenant.welcome_message)}"

        # Add status if disabled
        if not tenant.welcome_enabled:
            text = f"{text}\n\n{get_text(lang, 'viewwelcome_disabled')}"

        await update.message.reply_text(text, parse_mode='Markdown')
        return

    # In private chat - show list of groups to select
    lang = get_user_language(user_id)
    import sqlite3
    conn = sqlite3.connect('multi_tenant_moderation.db')
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id, chat_title FROM tenants WHERE chat_type IN ('group', 'supergroup')")
    all_groups = cursor.fetchall()
    conn.close()

    # Check which groups the user is admin in
    managed_groups = []
    for group_chat_id, group_title in all_groups:
        try:
            chat_member = await context.bot.get_chat_member(
                chat_id=group_chat_id,
                user_id=user_id
            )
            if chat_member.status in ['creator', 'administrator']:
                managed_groups.append((group_chat_id, group_title))
        except TelegramError:
            continue

    if not managed_groups:
        await update.message.reply_text(
            get_text(lang, 'setwelcome_no_groups')
        )
        return

    # Show buttons to select which group
    keyboard = []
    for group_chat_id, group_title in managed_groups:
        tenant = get_or_create_tenant(group_chat_id)
        if tenant.welcome_message:
            keyboard.append([
                InlineKeyboardButton(
                    f"{group_title}",
                    callback_data=f"seewelcome_{group_chat_id}"
                )
            ])

    if not keyboard:
        await update.message.reply_text(
            get_text(lang, 'viewwelcome_not_set'),
            parse_mode='Markdown'
        )
        return

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Qaysi guruhning xush kelibsiz xabarini ko'rmoqchisiz?",
        reply_markup=reply_markup
    )

# ==================== MESSAGE FILTERS ====================

async def filter_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Filter messages for banned words, spam, links, and files"""
    if not update.message:
        return

    # Only work in groups
    if update.effective_chat.type not in ['group', 'supergroup']:
        return

    # Don't filter admins
    if await is_admin(update, context):
        return

    chat_id = update.effective_chat.id
    tenant = get_or_create_tenant(chat_id, update.effective_chat.title, update.effective_chat.type)

    # Check antiflood
    if tenant.antiflood_enabled:
        if is_flooding(chat_id, update.effective_user.id, Config.FLOOD_LIMIT, Config.FLOOD_TIME):
            try:
                await update.message.delete()
                await context.bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=update.effective_user.id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=datetime.now(timezone.utc) + timedelta(minutes=5)
                )

                log_action(chat_id, update.effective_user.id, context.bot.id, "AUTO-MUTE", "Flooding detected", 5)

                msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=get_text(tenant.language, 'flood_muted', user=update.effective_user.mention_html()),
                    parse_mode='HTML'
                )
                await asyncio.sleep(5)
                await msg.delete()
                return
            except TelegramError as e:
                logger.error(f"Error handling flood: {e}")

    # Check link filtering (before word filters)
    if tenant.antilink_enabled and update.message.text:
        # Check if message contains URLs/links
        has_link = False

        # Check for URL entities (links, mentions, hashtags, etc.)
        if update.message.entities:
            for entity in update.message.entities:
                if entity.type in ['url', 'text_link']:
                    has_link = True
                    break

        # Also check for common URL patterns in text
        if not has_link:
            import re
            url_pattern = r'(?:http[s]?://|www\.|t\.me/)[^\s]+'
            if re.search(url_pattern, update.message.text, re.IGNORECASE):
                has_link = True

        if has_link:
            try:
                # Delete the message with link
                await update.message.delete()

                # Add warning to user
                warnings = add_warning(chat_id, update.effective_user.id, "Havolalar taqiqlangan")

                # Check if user reached max warnings
                if warnings >= tenant.max_warnings:
                    # Auto-kick user (ban then unban - allows rejoin)
                    await context.bot.ban_chat_member(chat_id=chat_id, user_id=update.effective_user.id)
                    await context.bot.unban_chat_member(chat_id=chat_id, user_id=update.effective_user.id)
                    log_action(chat_id, update.effective_user.id, context.bot.id, "AUTO-KICK", f"Reached {tenant.max_warnings} warnings (antilink)")

                    msg = await context.bot.send_message(
                        chat_id=chat_id,
                        text=get_text(tenant.language, 'user_warned_banned', user=update.effective_user.mention_html(), max_warnings=tenant.max_warnings),
                        parse_mode='HTML'
                    )
                    reset_warnings(chat_id, update.effective_user.id)
                else:
                    # Just warn the user
                    log_action(chat_id, update.effective_user.id, context.bot.id, "WARN", "Link detected (antilink)")

                    msg = await context.bot.send_message(
                        chat_id=chat_id,
                        text=get_text(tenant.language, 'link_warning', user=update.effective_user.mention_html(), warnings=warnings, max_warnings=tenant.max_warnings),
                        parse_mode='HTML'
                    )

                await asyncio.sleep(5)
                await msg.delete()
                return
            except TelegramError as e:
                logger.error(f"Error handling link message: {e}")

    # Check file filtering (only documents, not media)
    if tenant.antifile_enabled and update.message.document:
        # Get file extension
        file_name = update.message.document.file_name or ""
        file_ext = file_name.lower().split('.')[-1] if '.' in file_name else ""

        # Dangerous file extensions to block
        dangerous_extensions = [
            'exe', 'msi', 'bat', 'cmd', 'com', 'scr', 'vbs', 'js', 'jar',  # Windows executables
            'apk', 'xapk', 'apks',  # Android
            'ipa',  # iOS
            'deb', 'rpm',  # Linux packages
            'dmg', 'pkg', 'app',  # macOS
            'sh', 'run',  # Shell scripts
            'dll', 'sys', 'drv',  # System files
            'zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz',  # Archives (can contain malware)
        ]

        if file_ext in dangerous_extensions:
            try:
                # Delete the message with file
                await update.message.delete()

                # Add warning to user
                warnings = add_warning(chat_id, update.effective_user.id, "Fayllar taqiqlangan")

                # Check if user reached max warnings
                if warnings >= tenant.max_warnings:
                    # Auto-kick user (ban then unban - allows rejoin)
                    await context.bot.ban_chat_member(chat_id=chat_id, user_id=update.effective_user.id)
                    await context.bot.unban_chat_member(chat_id=chat_id, user_id=update.effective_user.id)
                    log_action(chat_id, update.effective_user.id, context.bot.id, "AUTO-KICK", f"Reached {tenant.max_warnings} warnings (antifile)")

                    msg = await context.bot.send_message(
                        chat_id=chat_id,
                        text=get_text(tenant.language, 'user_warned_banned', user=update.effective_user.mention_html(), max_warnings=tenant.max_warnings),
                        parse_mode='HTML'
                    )
                    reset_warnings(chat_id, update.effective_user.id)
                else:
                    # Just warn the user
                    log_action(chat_id, update.effective_user.id, context.bot.id, "WARN", "File detected (antifile)")

                    msg = await context.bot.send_message(
                        chat_id=chat_id,
                        text=get_text(tenant.language, 'file_warning', user=update.effective_user.mention_html(), warnings=warnings, max_warnings=tenant.max_warnings),
                        parse_mode='HTML'
                    )

                await asyncio.sleep(5)
                await msg.delete()
                return
            except TelegramError as e:
                logger.error(f"Error handling file message: {e}")

    # Check media filtering (photos, videos, audio, voice, stickers, animations, video notes)
    media_checks = [
        (update.message.photo, tenant.antimedia_photo, 'media_photo'),
        (update.message.video, tenant.antimedia_video, 'media_video'),
        (update.message.audio, tenant.antimedia_audio, 'media_audio'),
        (update.message.voice, tenant.antimedia_voice, 'media_voice'),
        (update.message.sticker, tenant.antimedia_sticker, 'media_sticker'),
        (update.message.animation, tenant.antimedia_animation, 'media_animation'),
        (update.message.video_note, tenant.antimedia_videonote, 'media_videonote'),
    ]

    for media_present, filter_enabled, media_type_key in media_checks:
        if media_present and filter_enabled:
            try:
                # Delete the message with media
                await update.message.delete()

                # Get the media type name for display
                media_type_name = get_text(tenant.language, media_type_key)

                # Add warning to user
                warnings = add_warning(chat_id, update.effective_user.id, f"{media_type_name} taqiqlangan")

                # Check if user reached max warnings
                if warnings >= tenant.max_warnings:
                    # Auto-kick user (ban then unban - allows rejoin)
                    await context.bot.ban_chat_member(chat_id=chat_id, user_id=update.effective_user.id)
                    await context.bot.unban_chat_member(chat_id=chat_id, user_id=update.effective_user.id)
                    log_action(chat_id, update.effective_user.id, context.bot.id, "AUTO-KICK", f"Reached {tenant.max_warnings} warnings (media: {media_type_key})")

                    msg = await context.bot.send_message(
                        chat_id=chat_id,
                        text=get_text(tenant.language, 'user_warned_banned', user=update.effective_user.mention_html(), max_warnings=tenant.max_warnings),
                        parse_mode='HTML'
                    )
                    reset_warnings(chat_id, update.effective_user.id)
                else:
                    # Just warn the user
                    log_action(chat_id, update.effective_user.id, context.bot.id, "WARN", f"Media detected: {media_type_key}")

                    msg = await context.bot.send_message(
                        chat_id=chat_id,
                        text=get_text(tenant.language, 'media_warning', user=update.effective_user.mention_html(), warnings=warnings, max_warnings=tenant.max_warnings, media_type=media_type_name),
                        parse_mode='HTML'
                    )

                await asyncio.sleep(5)
                await msg.delete()
                return
            except TelegramError as e:
                logger.error(f"Error handling media message ({media_type_key}): {e}")

    # Check word filters (only for text messages)
    if tenant.filter_enabled and update.message.text:
        message_text = update.message.text.lower()
        filters = get_filter_words(chat_id)

        for word in filters:
            if word in message_text:
                try:
                    await update.message.delete()

                    log_action(chat_id, update.effective_user.id, context.bot.id, "FILTER", f"Filtered word: {word}")

                    msg = await context.bot.send_message(
                        chat_id=chat_id,
                        text=get_text(tenant.language, 'word_filtered', user=update.effective_user.mention_html()),
                        parse_mode='HTML'
                    )
                    await asyncio.sleep(3)
                    await msg.delete()
                    return
                except TelegramError as e:
                    logger.error(f"Error deleting message: {e}")

# ==================== SERVICE MESSAGE HANDLING ====================

async def handle_service_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all service messages (join/leave/etc)"""
    if not update.message:
        return

    # Only work in groups
    if update.effective_chat.type not in ['group', 'supergroup']:
        return

    chat_id = update.effective_chat.id
    tenant = get_or_create_tenant(chat_id, update.effective_chat.title, update.effective_chat.type)

    try:
        # Handle user joined messages
        if update.message.new_chat_members and tenant.delete_join_messages:
            # Delete the join message immediately
            await update.message.delete()
            return

        # Handle user left messages
        if update.message.left_chat_member:
            # Log member leave activity
            if not update.message.left_chat_member.is_bot:
                log_member_activity(chat_id, update.message.left_chat_member.id, 'left')

            # Delete the leave message if configured
            if tenant.delete_leave_messages:
                await update.message.delete()
            return

        # Handle other service messages (photo changed, title changed, etc)
        if tenant.delete_service_messages:
            if (update.message.new_chat_photo or
                update.message.delete_chat_photo or
                update.message.new_chat_title or
                update.message.pinned_message or
                update.message.group_chat_created or
                update.message.supergroup_chat_created or
                update.message.channel_chat_created):
                await update.message.delete()
                return

    except TelegramError as e:
        logger.error(f"Error deleting service message: {e}")

# ==================== NEW MEMBER HANDLING ====================

async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new members joining"""
    chat_id = update.effective_chat.id
    tenant = get_or_create_tenant(chat_id, update.effective_chat.title, update.effective_chat.type)

    # Log member activity for all new members
    for member in update.message.new_chat_members:
        if not member.is_bot:
            log_member_activity(chat_id, member.id, 'joined')

    # Store the join message ID for potential deletion
    join_message_id = update.message.message_id

    # Check if verification is enabled
    if not tenant.verification_enabled:
        # Just send welcome message if enabled
        if tenant.welcome_enabled:
            for member in update.message.new_chat_members:
                if not member.is_bot:
                    # Use custom welcome message or default
                    if tenant.welcome_message:
                        from datetime import datetime
                        welcome_text = tenant.welcome_message
                        # Replace [user] with mention, [group] with group name, [time] with current time
                        welcome_text = welcome_text.replace('[user]', member.first_name)
                        welcome_text = welcome_text.replace('[group]', update.effective_chat.title or "the group")
                        welcome_text = welcome_text.replace('[time]', datetime.now().strftime('%H:%M'))
                    else:
                        # Default welcome message
                        welcome_text = f"👋 Welcome {member.first_name} to {update.effective_chat.title}!"

                    welcome_msg = await update.message.reply_text(welcome_text)

                    # Schedule welcome message deletion if duration is set
                    if tenant.welcome_message_duration > 0:
                        import asyncio
                        async def delete_welcome():
                            await asyncio.sleep(tenant.welcome_message_duration)
                            try:
                                await welcome_msg.delete()
                            except TelegramError:
                                pass
                        asyncio.create_task(delete_welcome())

        # Delete join message immediately if configured (separate from welcome message)
        if tenant.delete_join_messages:
            try:
                await update.message.delete()
            except TelegramError:
                pass

        return

    for member in update.message.new_chat_members:
        # Skip if bot itself
        if member.is_bot:
            continue

        # Initialize tenant verification dict
        if chat_id not in tenant_pending_verifications:
            tenant_pending_verifications[chat_id] = {}

        # Create verification button
        keyboard = [
            [InlineKeyboardButton(get_text(tenant.language, 'verify_button'), callback_data=f"verify_{member.id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            # Mute new user
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=member.id,
                permissions=ChatPermissions(can_send_messages=False)
            )

            # Send verification message
            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=get_text(tenant.language, 'verify_welcome', user=member.mention_html()),
                reply_markup=reply_markup,
                parse_mode='HTML'
            )

            # Store both verification message ID and join message ID
            # Format: (verification_msg_id, join_msg_id)
            tenant_pending_verifications[chat_id][member.id] = (msg.message_id, join_message_id)

            # Schedule auto-kick after 2 minutes
            context.job_queue.run_once(
                auto_kick_unverified,
                when=Config.VERIFICATION_TIMEOUT,
                data={'chat_id': chat_id, 'user_id': member.id}
            )

        except TelegramError as e:
            logger.error(f"Error handling new member: {e}")

    # Delete the original join service message immediately if configured
    if tenant.delete_join_messages:
        try:
            await update.message.delete()
        except TelegramError as e:
            logger.error(f"Error deleting join message: {e}")

async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle verification button press"""
    query = update.callback_query
    user_id = int(query.data.split('_')[1])

    if query.from_user.id != user_id:
        await query.answer("❌ This button is not for you!", show_alert=True)
        return

    chat_id = query.message.chat_id
    tenant = get_or_create_tenant(chat_id)

    try:
        # Unmute user
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=ChatPermissions.all_permissions()
        )

        await query.answer(get_text(tenant.language, 'verify_success', user=query.from_user.first_name))

        # Prepare welcome message (custom or default)
        success_msg = get_text(tenant.language, 'verify_success', user=query.from_user.first_name)

        if tenant.welcome_enabled and tenant.welcome_message:
            from datetime import datetime
            welcome_text = tenant.welcome_message
            welcome_text = welcome_text.replace('[user]', query.from_user.first_name)
            welcome_text = welcome_text.replace('[group]', query.message.chat.title or "the group")
            welcome_text = welcome_text.replace('[time]', datetime.now().strftime('%H:%M'))
            success_msg = f"{success_msg}\n\n{welcome_text}"

        # Edit the verification message to show success + welcome
        await query.message.edit_text(success_msg)

        # Delete the verification success message after a delay if configured
        if tenant.welcome_message_duration > 0:
            # Schedule deletion of verification success message based on welcome_message_duration
            async def delete_verification_message():
                try:
                    await asyncio.sleep(tenant.welcome_message_duration)
                    await context.bot.delete_message(
                        chat_id=chat_id,
                        message_id=query.message.message_id
                    )
                except TelegramError as e:
                    logger.error(f"Error deleting verification message: {e}")

            # Run deletion in background
            asyncio.create_task(delete_verification_message())
        elif tenant.delete_join_messages:
            # If no welcome duration set, use the old 3 second delay
            async def delete_verification_message():
                try:
                    await asyncio.sleep(3)
                    await context.bot.delete_message(
                        chat_id=chat_id,
                        message_id=query.message.message_id
                    )
                except TelegramError as e:
                    logger.error(f"Error deleting verification message: {e}")

            # Run deletion in background
            asyncio.create_task(delete_verification_message())

        if chat_id in tenant_pending_verifications and user_id in tenant_pending_verifications[chat_id]:
            del tenant_pending_verifications[chat_id][user_id]

    except TelegramError as e:
        logger.error(f"Error verifying user: {e}")

async def auto_kick_unverified(context: ContextTypes.DEFAULT_TYPE):
    """Auto-kick users who didn't verify"""
    job_data = context.job.data
    chat_id = job_data['chat_id']
    user_id = job_data['user_id']

    if chat_id in tenant_pending_verifications and user_id in tenant_pending_verifications[chat_id]:
        try:
            await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_id)

            msg_data = tenant_pending_verifications[chat_id][user_id]

            # Handle both old format (int) and new format (tuple)
            if isinstance(msg_data, tuple):
                verification_msg_id, _ = msg_data  # We only need verification msg, join msg already deleted
                # Delete verification message
                await context.bot.delete_message(chat_id=chat_id, message_id=verification_msg_id)
            else:
                # Old format - just delete the verification message
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_data)

            del tenant_pending_verifications[chat_id][user_id]

            log_action(chat_id, user_id, context.bot.id, "AUTO-KICK", "Failed to verify within timeout")
            logger.info(f"Auto-kicked unverified user {user_id} from tenant {chat_id}")
        except TelegramError as e:
            logger.error(f"Error auto-kicking user: {e}")

# ==================== ERROR HANDLER ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors gracefully"""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

    if isinstance(context.error, TelegramError):
        error_message = str(context.error)

        if "Forbidden" in error_message or "bot was blocked" in error_message:
            logger.warning(f"Bot doesn't have permissions or was blocked")
            return
        elif "message to delete not found" in error_message:
            logger.info("Message already deleted")
            return
        elif "user not found" in error_message:
            logger.warning("User not found in chat")
            if update and update.effective_message:
                # Get language
                if update.effective_chat.type in ['group', 'supergroup']:
                    tenant = get_or_create_tenant(update.effective_chat.id)
                    lang = tenant.language
                else:
                    lang = get_user_language(update.effective_user.id)
                await update.effective_message.reply_text(
                    get_text(lang, 'user_not_found')
                )
            return
        elif "not enough rights" in error_message or "CHAT_ADMIN_REQUIRED" in error_message:
            logger.warning("Bot lacks necessary permissions")
            if update and update.effective_message:
                # Get language
                if update.effective_chat.type in ['group', 'supergroup']:
                    tenant = get_or_create_tenant(update.effective_chat.id)
                    lang = tenant.language
                else:
                    lang = get_user_language(update.effective_user.id)
                await update.effective_message.reply_text(
                    get_text(lang, 'insufficient_permissions')
                )
            return
        elif "Too Many Requests" in error_message or "retry after" in error_message:
            logger.warning("Rate limited by Telegram")
            if update and update.effective_message:
                # Get language
                if update.effective_chat.type in ['group', 'supergroup']:
                    tenant = get_or_create_tenant(update.effective_chat.id)
                    lang = tenant.language
                else:
                    lang = get_user_language(update.effective_user.id)
                await update.effective_message.reply_text(
                    get_text(lang, 'rate_limit_telegram')
                )
            return
        elif "Timed out" in error_message or "TimedOut" in str(type(context.error).__name__):
            logger.warning(f"Request timed out - network issue")
            # Don't send error message for timeout - it's usually temporary network issue
            return
        elif "Query is too old" in error_message:
            logger.info("Callback query expired")
            # Don't send error message for old queries
            return
        elif "Bad Request" in error_message:
            logger.warning(f"Bad request: {error_message}")
            if update and update.effective_message:
                # Get language
                if update.effective_chat.type in ['group', 'supergroup']:
                    tenant = get_or_create_tenant(update.effective_chat.id)
                    lang = tenant.language
                else:
                    lang = get_user_language(update.effective_user.id)
                await update.effective_message.reply_text(
                    get_text(lang, 'invalid_request')
                )
            return

    logger.error(f"Unhandled error: {context.error}")

    if update and update.effective_message:
        try:
            # Get language
            if update.effective_chat.type in ['group', 'supergroup']:
                tenant = get_or_create_tenant(update.effective_chat.id)
                lang = tenant.language
            else:
                lang = get_user_language(update.effective_user.id)
            await update.effective_message.reply_text(
                get_text(lang, 'unexpected_error')
            )
        except Exception:
            pass

# ==================== MAIN ====================

def main():
    """Start the bot"""
    # Initialize database
    init_db()

    # Create application
    application = Application.builder().token(Config.BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ban", ban_user))
    application.add_handler(CommandHandler("unban", unban_user))
    application.add_handler(CommandHandler("kick", kick_user))
    application.add_handler(CommandHandler("mute", mute_user))
    application.add_handler(CommandHandler("unmute", unmute_user))
    application.add_handler(CommandHandler("warn", warn_user))
    application.add_handler(CommandHandler("unwarn", unwarn_user))
    application.add_handler(CommandHandler("warnings", check_warnings))
    application.add_handler(CommandHandler("filter", add_filter))
    application.add_handler(CommandHandler("unfilter", remove_filter))
    application.add_handler(CommandHandler("seefilters", list_filters))
    application.add_handler(CommandHandler("purge", purge_messages))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("info", user_info))
    application.add_handler(CommandHandler("rules", rules_command))
    application.add_handler(CommandHandler("setrules", set_rules))
    application.add_handler(CommandHandler("setwelcome", set_welcome))
    application.add_handler(CommandHandler("seewelcome", view_welcome))
    application.add_handler(CommandHandler("seerules", see_rules))

    # Private text message handler (for conversation states) - MUST be before filter_messages
    application.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND,
        handle_private_text
    ))

    # Message filters
    application.add_handler(MessageHandler(
        (filters.TEXT | filters.Document.ALL) & ~filters.COMMAND,
        filter_messages
    ))

    # Media message handler (photos, videos, audio, voice, stickers, animations, video notes)
    application.add_handler(MessageHandler(
        (filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE | filters.Sticker.ALL | filters.ANIMATION | filters.VIDEO_NOTE) & ~filters.COMMAND,
        filter_messages
    ))

    # New member handler
    application.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        new_member
    ))

    # Service message handlers (LEFT_CHAT_MEMBER and other status updates)
    application.add_handler(MessageHandler(
        filters.StatusUpdate.LEFT_CHAT_MEMBER |
        filters.StatusUpdate.NEW_CHAT_PHOTO |
        filters.StatusUpdate.DELETE_CHAT_PHOTO |
        filters.StatusUpdate.NEW_CHAT_TITLE |
        filters.StatusUpdate.PINNED_MESSAGE,
        handle_service_messages
    ))

    # Callback handlers
    application.add_handler(CallbackQueryHandler(verify_callback, pattern=r'^verify_'))
    application.add_handler(CallbackQueryHandler(settings_callback, pattern=r'^(show_settings_|toggle_|set_warnings_|change_warnings|set_welcome_duration_|change_welcome_duration|settings_info|back_to_settings|back_to_start)'))
    application.add_handler(CallbackQueryHandler(setwelcome_callback, pattern=r'^setwelcome_'))
    application.add_handler(CallbackQueryHandler(setrules_callback, pattern=r'^setrules_'))
    application.add_handler(CallbackQueryHandler(start_setrules_callback, pattern=r'^start_setrules_'))
    application.add_handler(CallbackQueryHandler(start_setwelcome_callback, pattern=r'^start_setwelcome_'))
    application.add_handler(CallbackQueryHandler(start_setfilter_callback, pattern=r'^start_setfilter_'))
    application.add_handler(CallbackQueryHandler(start_removefilter_callback, pattern=r'^start_removefilter_'))
    application.add_handler(CallbackQueryHandler(seewelcome_callback, pattern=r'^seewelcome_'))
    application.add_handler(CallbackQueryHandler(seerules_callback, pattern=r'^seerules_'))
    application.add_handler(CallbackQueryHandler(viewrules_callback, pattern=r'^viewrules_'))
    application.add_handler(CallbackQueryHandler(viewwelcome_callback, pattern=r'^viewwelcome_'))
    application.add_handler(CallbackQueryHandler(viewfilters_callback, pattern=r'^viewfilters_'))
    application.add_handler(CallbackQueryHandler(stats_callback, pattern=r'^stats_'))
    application.add_handler(CallbackQueryHandler(help_callback, pattern=r'^(help_|show_help_|back_to_help)'))
    application.add_handler(CallbackQueryHandler(filter_callback, pattern=r'^(addfilter_|removefilter_|listfilters_)'))

    # Error handler
    application.add_error_handler(error_handler)

    # Start the bot
    logger.info("🤖 Multi-Tenant Moderation Bot started successfully!")
    logger.info(f"📊 Database: {Config.DATABASE_NAME}")
    logger.info(f"🚫 Flood Limit: {Config.FLOOD_LIMIT} messages in {Config.FLOOD_TIME}s")
    logger.info(f"✅ Verification Timeout: {Config.VERIFICATION_TIMEOUT}s")
    logger.info("Press Ctrl+C to stop the bot")

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n👋 Bot stopped by user")
        logger.info("Cleaning up...")
        logger.info("✅ Shutdown complete")
    except Exception as e:
        logger.error(f"💥 Bot crashed: {e}", exc_info=True)
        logger.error("Please check the error above and restart the bot")
        exit(1)
