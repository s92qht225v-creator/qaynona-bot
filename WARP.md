# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

**qaynona-bot** is a multi-tenant Telegram moderation bot written in Python using python-telegram-bot v21.0. The bot manages multiple groups simultaneously with isolated configurations, warnings, filters, and logs per group (tenant).

## Essential Commands

### Development Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment (copy .env.example to .env and add BOT_TOKEN)
cp .env.example .env
```

### Running the Bot
```bash
# Run locally (development/testing only)
python3 bot.py

# CRITICAL: Production bot runs on remote server via systemd
# The bot MUST NOT be run from local machine in production
```

### Deployment (Production)
```bash
# Deploy code changes to server
scp bot.py root@152.42.233.255:/root/qaynona-bot/

# Restart the bot service on server
ssh root@152.42.233.255 "rm -rf /root/qaynona-bot/__pycache__ && systemctl restart qaynonabot"

# Check bot status
ssh root@152.42.233.255 "systemctl status qaynonabot"

# View live logs
ssh root@152.42.233.255 "journalctl -u qaynonabot -f"
```

### Database Operations
```bash
# Connect to database on server
ssh root@152.42.233.255 "sqlite3 /root/qaynona-bot/multi_tenant_moderation.db"

# Check database locally
sqlite3 multi_tenant_moderation.db
```

### Git Workflow
```bash
# ALWAYS commit after making changes
git add .
git commit -m "description of changes"
git push

# Pull changes on other environment
git pull
```

## Architecture Overview

### Multi-Tenant Design
The bot uses a **tenant isolation model** where each Telegram group is a separate "tenant" with:
- Independent configuration (stored in `tenants` table)
- Isolated warnings (stored in `tenant_warnings` table)
- Isolated filter words (stored in `tenant_filters` table)
- Isolated moderation logs (stored in `tenant_logs` table)
- Isolated member activity tracking (stored in `member_activity` table)

All data is scoped by `chat_id` (the Telegram group ID), ensuring complete data isolation between groups.

### Core Components

**bot.py** (3600+ lines)
- Main bot logic and command handlers
- Decorators: `@admin_only`, `@group_only`, `@rate_limit`
- Command handlers for moderation (`/ban`, `/kick`, `/mute`, `/warn`, etc.)
- Settings management via inline keyboards
- Message filtering pipeline (antiflood, antilink, antifile, antimedia, word filters)
- Admin cache with 60s TTL to reduce Telegram API calls
- Global admin support (user ID: 6461799783)

**database.py** (800+ lines)
- All database operations using SQLite
- Schema management with migrations
- Functions for tenant CRUD, warnings, filters, logs
- Database connection pooling via `get_db_connection()`
- TenantConfig dataclass for type-safe configuration

**translations.py** (900+ lines)
- Uzbek language translations (primary language)
- Translation keys for all bot messages
- `get_text(lang, key, **kwargs)` function for formatted strings

**config.py** (112 lines)
- Configuration from environment variables via python-dotenv
- Required: `BOT_TOKEN`
- Optional: Database name, flood limits, verification timeout, global admin IDs

### Database Schema

```
tenants (main configuration per group)
  ├─ chat_id (PK)
  ├─ settings (welcome_enabled, antiflood_enabled, filter_enabled, etc.)
  ├─ media filters (antimedia_photo, antimedia_video, etc.)
  └─ service message deletion (delete_join_messages, etc.)

tenant_warnings (per-group user warnings)
  ├─ tenant_id (FK to tenants)
  ├─ user_id
  └─ warnings count

tenant_filters (per-group filtered words)
  ├─ tenant_id (FK to tenants)
  └─ word (unique per tenant)

tenant_logs (moderation action logs)
  ├─ tenant_id (FK to tenants)
  ├─ user_id (target)
  ├─ admin_id (moderator)
  └─ action (BAN, KICK, MUTE, WARN)

member_activity (join/leave tracking)
  ├─ tenant_id (FK to tenants)
  ├─ user_id
  └─ action (joined, left)

global_admins (bot super-admins)
  └─ user_id (PK)

chat_admins (cached admin status)
  ├─ chat_id
  ├─ user_id
  └─ status
```

### Message Filtering Pipeline

Messages from non-admins are checked in this order:

1. **Channel Forward Check** (line ~3421): Skip messages forwarded from channels to discussion groups
2. **Antiflood** (line ~3436): Delete + 5min mute if user sends >5 messages in 10 seconds
3. **Antilink** (line ~3461): Delete + warn for URLs/mentions (checks entities: 'url', 'text_link', 'mention', 'text_mention')
4. **Antifile** (line ~3526): Delete + warn for dangerous file extensions (exe, apk, zip, etc.)
5. **Antimedia** (line ~3577): Delete + warn for each media type (photo, video, audio, voice, sticker, animation, video_note)
6. **Word Filters** (line ~3627): Delete + warn for messages containing filtered words

Each filter can trigger warnings. When warnings reach `max_warnings` (default 3), user is auto-kicked.

## Critical Rules from .claude/claude.md

### NEVER DELETE WARNING MESSAGES
- All warning messages (media, link, file) must **stay permanently**
- The bot used to auto-delete warnings after 10 seconds - this was **fixed** in commit c93e7e2
- If you see `await asyncio.sleep(10)` followed by `await msg.delete()` after sending a warning, **DO NOT ADD IT**

### Antilink Blocks @Username Mentions
- Antilink checks for entity types: `'url'`, `'text_link'`, `'mention'`, `'text_mention'` (line 3468)
- This blocks spam like "@testuser" which creates clickable username links
- Fixed in commit f3797c8

### Channel-Forwarded Messages Must Skip Moderation
- Messages forwarded from channels to discussion groups must NOT be moderated (line 3421)
- Check: `update.message.forward_origin.type == MessageOriginType.CHANNEL`
- This allows channel posts in linked discussion groups without deletion
- Fixed in commit 1bd588b for new Telegram API

### File Synchronization Workflow
1. Make fix on server OR local
2. Commit to git: `git add . && git commit -m "description" && git push`
3. Pull on other side: `git pull`

**NEVER** upload local file without checking server state first via `git status` or `git diff`.

### Filter Words
- No limit on number of filter words
- Stored in `tenant_filters` table with `(tenant_id, word)` unique constraint
- Function: `add_filter_word(chat_id, word, admin_id)` - requires `admin_id`

## Bot Configuration

### Privacy Mode
**MUST be OFF** for bot to read group messages. Check via @BotFather.

### Required Permissions
When adding bot to groups, grant these admin permissions:
- Delete messages (required for moderation)
- Ban users (required for ban/kick)
- Restrict members (required for mute)
- Invite users (optional)

### Service Configuration
- **Service name**: `qaynonabot.service`
- **Server**: 152.42.233.255
- **Directory**: /root/qaynona-bot/
- **Database**: multi_tenant_moderation.db (SQLite)
- **Environment**: Production uses systemd, NOT background bash processes

## Code Patterns

### Admin Check Pattern
```python
if not await is_admin(update, context):
    await update.message.reply_text(get_text(lang, 'admin_only'))
    return
```

### Language-Aware Messages
```python
lang = tenant.language  # In group context
lang = get_user_language(user_id)  # In private chat context
await update.message.reply_text(get_text(lang, 'message_key', param=value))
```

### Tenant Creation Pattern
```python
tenant = get_or_create_tenant(chat_id, chat_title, chat_type)
```

### Database Transaction Pattern
```python
conn = get_db_connection()
cursor = conn.cursor()
try:
    cursor.execute("SQL", (params,))
    conn.commit()
finally:
    conn.close()
```

### Warning with Auto-Kick Pattern
```python
warnings = add_warning(chat_id, user_id, reason)
if warnings >= tenant.max_warnings:
    # Auto-kick (ban then unban - allows rejoin)
    await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
    await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
    reset_warnings(chat_id, user_id)
```

## Testing

No automated tests exist yet. Manual testing workflow:
1. Add bot to test group
2. Make bot admin with required permissions
3. Test commands and filters
4. Check logs: `ssh root@152.42.233.255 "journalctl -u qaynonabot -n 100"`

## Important Notes

- **Bot Token**: Stored in `.env`, never commit
- **Database**: SQLite (database.py), NOT PostgreSQL (database_pg.py exists but is unused)
- **Language**: Primary language is Uzbek (uz), bot messages are in translations.py
- **Anonymous Admins**: Bot recognizes GroupAnonymousBot (ID: 1087968824) as admin
- **Global Admin**: User 6461799783 (ali) has super-admin access across all groups
- **Current State**: 18 groups, 29 warnings, 3 filter words in production database
