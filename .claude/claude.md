# Claude Memory File - Qaynona Bot

## CRITICAL RULES - NEVER BREAK THESE:

### 1. WARNING MESSAGES - NEVER DELETE ANY WARNING
- **ALL WARNING MESSAGES MUST NEVER BE DELETED**
- This applies to:
  - Media warnings (photos, videos, audio, etc.) - line ~3549
  - Link warnings (antilink) - line ~3442
  - File warnings (antifile) - line ~3494
- Remove these lines after sending ANY warning:
  ```python
  await asyncio.sleep(10)
  await msg.delete()
  ```
- Warning messages should be sent and stay permanently
- FIXED: Commit c93e7e2 "Fix: Remove auto-deletion of all warning messages"

### 2. FILE SYNCHRONIZATION
- **ALWAYS commit changes to git after fixes**
- **NEVER upload local file without checking what's on server first**
- Workflow:
  1. Make fix on server OR local
  2. Commit to git: `git add . && git commit -m "description" && git push`
  3. Pull on other side: `git pull`

### 3. WARNING MESSAGE TEXT (from commit f8af77a)
```
'media_warning': '⚠️ {user} guruhga {media_type} yuborgani uchun {warnings} chi martta ogohlantirildi\n\n💡 Agar {max_warnings} ta ogohlantirish olsangiz, guruhdan chiqarilasiz.'
```

### 4. FILTER WORDS
- Function: `add_filter_word(chat_id, word, admin_id)`
- Need `admin_id = update.effective_user.id` before calling
- NOTE: Filter words are stored in database (`tenant_filters` table)
- You can add/remove unlimited filter words - no restrictions

### 5. GLOBAL ADMINS
- User ID: 6461799783 (ali)
- Anonymous Bot ID: 1087968824 (GroupAnonymousBot)

### 6. DATABASE STATE
- 18 groups
- 29 warnings
- 3 filter words (общежитие, manzil, локация)
- Database: multi_tenant_moderation.db (SQLite)

### 7. IMPORTANT SETTINGS
- Privacy Mode: OFF (must stay OFF)
- Bot: @qaynonajonbot
- Token: 8229904786:AAEXTzRHvW7XR1gfAls6KYACYL4-IUh1MpA
- Server: 152.42.233.255

### 8. ANTILINK FILTER - BLOCKS USERNAME SPAM
- **Line 3406**: Antilink filter checks for entity types: `'url'`, `'text_link'`, `'mention'`, `'text_mention'`
- This blocks spam messages like "@testuser" which create clickable username links
- When antilink is enabled, messages with @username mentions are deleted and user gets warned
- FIXED: Commit f3797c8 "Add mention and text_mention to antilink filter to block username spam"

### 9. CHANNEL FORWARDED MESSAGES - SKIP MODERATION
- **Line 3380-3384**: Messages forwarded from channels to discussion groups must NOT be moderated
- Check: `update.message.forward_origin.type == MessageOriginType.CHANNEL`
- This allows channel posts to appear in linked discussion groups without being deleted
- FIXED: Commit 1bd588b "Fix channel forward check for new Telegram API"

### 10. BOT DEPLOYMENT
- **Bot runs on DigitalOcean droplet (152.42.233.255) via systemd service**
- Service name: `qaynonabot.service`
- **NEVER run bot from local machine or background bash shells**
- Commands:
  - Restart: `ssh root@152.42.233.255 "systemctl restart qaynonabot"`
  - Status: `ssh root@152.42.233.255 "systemctl status qaynonabot"`
  - Logs: `ssh root@152.42.233.255 "journalctl -u qaynonabot -f"`
- After code changes:
  ```bash
  scp bot.py root@152.42.233.255:/root/qaynona-bot/
  ssh root@152.42.233.255 "rm -rf /root/qaynona-bot/__pycache__ && systemctl restart qaynonabot"
  ```

### 11. CODE STATE
- Current commit: 1bd588b (Fix channel forward for new Telegram API)
- Using SQLite (database.py), NOT PostgreSQL (database_pg.py)
- Vercel migration was FAILED and REVERTED

## BEFORE MAKING ANY CHANGE:
1. Read this file
2. Check current state on server
3. Make changes
4. Commit to git
5. Test

## COMMON MISTAKES TO AVOID:
- ❌ Don't delete warning messages after sending
- ❌ Don't use Markdown for globalstats (use HTML with html.escape())
- ❌ Don't forget admin_id when calling add_filter_word()
- ❌ Don't upload local without checking server first
