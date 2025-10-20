"""
Multi-Tenant Database Management
Handles all database operations with tenant isolation using SQLite
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from config import Config

@dataclass
class TenantConfig:
    """Configuration for each tenant/group"""
    chat_id: int
    chat_title: str = ""
    chat_type: str = "group"
    welcome_enabled: bool = False  # OFF by default
    antiflood_enabled: bool = True
    filter_enabled: bool = True
    verification_enabled: bool = False  # OFF by default
    antilink_enabled: bool = True  # ON by default
    antifile_enabled: bool = True  # ON by default
    # Media filtering (individual toggles)
    antimedia_photo: bool = True  # ON by default
    antimedia_video: bool = True  # ON by default
    antimedia_audio: bool = True  # ON by default
    antimedia_voice: bool = True  # ON by default
    antimedia_sticker: bool = True  # ON by default
    antimedia_animation: bool = True  # ON by default
    antimedia_videonote: bool = True  # ON by default
    max_warnings: int = 3
    rules_text: str = ""
    welcome_message: str = ""
    welcome_message_duration: int = 0  # Duration in seconds to keep welcome message (0 = don't delete)
    language: str = "eng"  # Default to English (uz, ru, eng)
    timezone: str = "UTC"
    is_active: bool = True
    # Service message deletion settings
    delete_join_messages: bool = True  # ON by default
    delete_leave_messages: bool = True  # ON by default
    delete_service_messages: bool = True  # ON by default

# ==================== DATABASE INITIALIZATION ====================

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(Config.DATABASE_NAME)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn

def init_db():
    """Initialize multi-tenant database"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Tenants table (one row per group)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tenants (
            chat_id INTEGER PRIMARY KEY,
            chat_title TEXT,
            chat_type TEXT DEFAULT 'group',
            welcome_enabled BOOLEAN DEFAULT 0,
            antiflood_enabled BOOLEAN DEFAULT 1,
            filter_enabled BOOLEAN DEFAULT 1,
            verification_enabled BOOLEAN DEFAULT 0,
            antilink_enabled BOOLEAN DEFAULT 1,
            antifile_enabled BOOLEAN DEFAULT 1,
            antimedia_photo BOOLEAN DEFAULT 1,
            antimedia_video BOOLEAN DEFAULT 1,
            antimedia_audio BOOLEAN DEFAULT 1,
            antimedia_voice BOOLEAN DEFAULT 1,
            antimedia_sticker BOOLEAN DEFAULT 1,
            antimedia_animation BOOLEAN DEFAULT 1,
            antimedia_videonote BOOLEAN DEFAULT 1,
            max_warnings INTEGER DEFAULT 3,
            rules_text TEXT,
            welcome_message TEXT,
            welcome_message_duration INTEGER DEFAULT 0,
            language TEXT DEFAULT 'uz',
            timezone TEXT DEFAULT 'UTC',
            is_active BOOLEAN DEFAULT 1,
            delete_join_messages BOOLEAN DEFAULT 1,
            delete_leave_messages BOOLEAN DEFAULT 1,
            delete_service_messages BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Tenant warnings (scoped by tenant_id)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tenant_warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER,
            user_id INTEGER,
            warnings INTEGER DEFAULT 0,
            last_warning TIMESTAMP,
            warning_reasons TEXT,
            FOREIGN KEY (tenant_id) REFERENCES tenants (chat_id),
            UNIQUE(tenant_id, user_id)
        )
    ''')

    # Tenant filters (scoped by tenant_id)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tenant_filters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER,
            word TEXT,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES tenants (chat_id),
            UNIQUE(tenant_id, word)
        )
    ''')

    # User preferences for private chat
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY,
            language TEXT DEFAULT 'uz',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Tenant moderation logs (scoped by tenant_id)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tenant_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER,
            user_id INTEGER,
            admin_id INTEGER,
            action TEXT,
            reason TEXT,
            duration_minutes INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES tenants (chat_id)
        )
    ''')

    # Member activity tracking (join/leave)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS member_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER,
            user_id INTEGER,
            action TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES tenants (chat_id)
        )
    ''')

    # Global admins (bot super-admins across all tenants)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_admins (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Chat admins cache (for performance optimization)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_admins (
            chat_id INTEGER,
            user_id INTEGER,
            status TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (chat_id, user_id),
            FOREIGN KEY (chat_id) REFERENCES tenants (chat_id)
        )
    ''')

    # Add initial global admins from config
    for admin_id in Config.GLOBAL_ADMIN_IDS:
        cursor.execute('''
            INSERT OR IGNORE INTO global_admins (user_id) VALUES (?)
        ''', (admin_id,))

    # Migration: Add antilink_enabled column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE tenants ADD COLUMN antilink_enabled BOOLEAN DEFAULT 0")
        print("✅ Added antilink_enabled column to tenants table")
    except sqlite3.OperationalError:
        # Column already exists
        pass

    # Migration: Add antifile_enabled column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE tenants ADD COLUMN antifile_enabled BOOLEAN DEFAULT 0")
        print("✅ Added antifile_enabled column to tenants table")
    except sqlite3.OperationalError:
        # Column already exists
        pass

    # Migration: Add media filter columns if they don't exist
    media_columns = [
        'antimedia_photo', 'antimedia_video', 'antimedia_audio',
        'antimedia_voice', 'antimedia_sticker', 'antimedia_animation', 'antimedia_videonote'
    ]
    for column in media_columns:
        try:
            cursor.execute(f"ALTER TABLE tenants ADD COLUMN {column} BOOLEAN DEFAULT 0")
            print(f"✅ Added {column} column to tenants table")
        except sqlite3.OperationalError:
            # Column already exists
            pass

    conn.commit()
    conn.close()
    print("✅ Multi-tenant database initialized successfully!")

# ==================== TENANT MANAGEMENT ====================

def get_or_create_tenant(chat_id: int, chat_title: str = "", chat_type: str = "group") -> TenantConfig:
    """Get or create tenant configuration"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tenants WHERE chat_id = ?", (chat_id,))
    result = cursor.fetchone()

    if not result:
        # Create new tenant
        cursor.execute('''
            INSERT INTO tenants
            (chat_id, chat_title, chat_type, max_warnings)
            VALUES (?, ?, ?, ?)
        ''', (chat_id, chat_title, chat_type, Config.DEFAULT_MAX_WARNINGS))
        conn.commit()

        cursor.execute("SELECT * FROM tenants WHERE chat_id = ?", (chat_id,))
        result = cursor.fetchone()

    # Handle new columns that might not exist in old databases
    try:
        delete_join = bool(result['delete_join_messages'])
    except (KeyError, IndexError):
        delete_join = False

    try:
        delete_leave = bool(result['delete_leave_messages'])
    except (KeyError, IndexError):
        delete_leave = False

    try:
        delete_service = bool(result['delete_service_messages'])
    except (KeyError, IndexError):
        delete_service = False

    try:
        welcome_msg = result['welcome_message'] or ""
    except (KeyError, IndexError):
        welcome_msg = ""

    try:
        welcome_duration = int(result['welcome_message_duration'] or 0)
    except (KeyError, IndexError):
        welcome_duration = 0

    # Handle antilink_enabled (new column that might not exist)
    try:
        antilink = bool(result['antilink_enabled'])
    except (KeyError, IndexError):
        antilink = False

    # Handle antifile_enabled (new column that might not exist)
    try:
        antifile = bool(result['antifile_enabled'])
    except (KeyError, IndexError):
        antifile = False

    # Handle media filter columns (new columns that might not exist)
    media_filters = {}
    for media_type in ['photo', 'video', 'audio', 'voice', 'sticker', 'animation', 'videonote']:
        try:
            media_filters[f'antimedia_{media_type}'] = bool(result[f'antimedia_{media_type}'])
        except (KeyError, IndexError):
            media_filters[f'antimedia_{media_type}'] = False

    config = TenantConfig(
        chat_id=result['chat_id'],
        chat_title=result['chat_title'] or "",
        chat_type=result['chat_type'] or "group",
        welcome_enabled=bool(result['welcome_enabled']),
        antiflood_enabled=bool(result['antiflood_enabled']),
        filter_enabled=bool(result['filter_enabled']),
        verification_enabled=bool(result['verification_enabled']),
        antilink_enabled=antilink,
        antifile_enabled=antifile,
        antimedia_photo=media_filters['antimedia_photo'],
        antimedia_video=media_filters['antimedia_video'],
        antimedia_audio=media_filters['antimedia_audio'],
        antimedia_voice=media_filters['antimedia_voice'],
        antimedia_sticker=media_filters['antimedia_sticker'],
        antimedia_animation=media_filters['antimedia_animation'],
        antimedia_videonote=media_filters['antimedia_videonote'],
        max_warnings=result['max_warnings'],
        rules_text=result['rules_text'] or "",
        welcome_message=welcome_msg,
        welcome_message_duration=welcome_duration,
        language=result['language'] or "en",
        timezone=result['timezone'] or "UTC",
        is_active=bool(result['is_active']),
        delete_join_messages=delete_join,
        delete_leave_messages=delete_leave,
        delete_service_messages=delete_service
    )

    conn.close()
    return config

def update_tenant_config(chat_id: int, **kwargs):
    """Update tenant configuration"""
    conn = get_db_connection()
    cursor = conn.cursor()

    valid_fields = [
        'welcome_enabled', 'antiflood_enabled', 'filter_enabled',
        'verification_enabled', 'antilink_enabled', 'antifile_enabled',
        'antimedia_photo', 'antimedia_video', 'antimedia_audio',
        'antimedia_voice', 'antimedia_sticker', 'antimedia_animation', 'antimedia_videonote',
        'max_warnings', 'rules_text',
        'welcome_message', 'welcome_message_duration', 'language', 'timezone', 'is_active', 'chat_title',
        'delete_join_messages', 'delete_leave_messages', 'delete_service_messages'
    ]

    for key, value in kwargs.items():
        if key in valid_fields:
            cursor.execute(
                f"UPDATE tenants SET {key} = ?, updated_at = CURRENT_TIMESTAMP WHERE chat_id = ?",
                (value, chat_id)
            )

    conn.commit()
    conn.close()

def get_all_tenants(active_only: bool = True) -> List[TenantConfig]:
    """Get all tenant configurations"""
    conn = get_db_connection()
    cursor = conn.cursor()

    if active_only:
        cursor.execute("SELECT * FROM tenants WHERE is_active = 1")
    else:
        cursor.execute("SELECT * FROM tenants")

    results = cursor.fetchall()
    tenants = []

    for row in results:
        # Handle new columns that might not exist in old databases
        try:
            delete_join = bool(row['delete_join_messages'])
        except (KeyError, IndexError):
            delete_join = False

        try:
            delete_leave = bool(row['delete_leave_messages'])
        except (KeyError, IndexError):
            delete_leave = False

        try:
            delete_service = bool(row['delete_service_messages'])
        except (KeyError, IndexError):
            delete_service = False

        # Handle antilink_enabled (new column that might not exist)
        try:
            antilink = bool(row['antilink_enabled'])
        except (KeyError, IndexError):
            antilink = False

        # Handle antifile_enabled (new column that might not exist)
        try:
            antifile = bool(row['antifile_enabled'])
        except (KeyError, IndexError):
            antifile = False

        # Handle media filter columns (new columns that might not exist)
        media_filters = {}
        for media_type in ['photo', 'video', 'audio', 'voice', 'sticker', 'animation', 'videonote']:
            try:
                media_filters[f'antimedia_{media_type}'] = bool(row[f'antimedia_{media_type}'])
            except (KeyError, IndexError):
                media_filters[f'antimedia_{media_type}'] = False

        tenants.append(TenantConfig(
            chat_id=row['chat_id'],
            chat_title=row['chat_title'] or "",
            chat_type=row['chat_type'] or "group",
            welcome_enabled=bool(row['welcome_enabled']),
            antiflood_enabled=bool(row['antiflood_enabled']),
            filter_enabled=bool(row['filter_enabled']),
            verification_enabled=bool(row['verification_enabled']),
            antilink_enabled=antilink,
            antifile_enabled=antifile,
            antimedia_photo=media_filters['antimedia_photo'],
            antimedia_video=media_filters['antimedia_video'],
            antimedia_audio=media_filters['antimedia_audio'],
            antimedia_voice=media_filters['antimedia_voice'],
            antimedia_sticker=media_filters['antimedia_sticker'],
            antimedia_animation=media_filters['antimedia_animation'],
            antimedia_videonote=media_filters['antimedia_videonote'],
            max_warnings=row['max_warnings'],
            rules_text=row['rules_text'] or "",
            language=row['language'] or "en",
            timezone=row['timezone'] or "UTC",
            is_active=bool(row['is_active']),
            delete_join_messages=delete_join,
            delete_leave_messages=delete_leave,
            delete_service_messages=delete_service
        ))

    conn.close()
    return tenants

# ==================== WARNING MANAGEMENT ====================

def get_warnings(tenant_id: int, user_id: int) -> int:
    """Get warning count for user in a tenant"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT warnings FROM tenant_warnings WHERE tenant_id = ? AND user_id = ?",
        (tenant_id, user_id)
    )
    result = cursor.fetchone()
    conn.close()

    return result['warnings'] if result else 0

def add_warning(tenant_id: int, user_id: int, reason: str = "") -> int:
    """Add warning to user and return total warnings"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT warnings, warning_reasons FROM tenant_warnings WHERE tenant_id = ? AND user_id = ?",
        (tenant_id, user_id)
    )
    result = cursor.fetchone()

    if not result:
        # Create new warning record
        cursor.execute('''
            INSERT INTO tenant_warnings (tenant_id, user_id, warnings, last_warning, warning_reasons)
            VALUES (?, ?, 1, CURRENT_TIMESTAMP, ?)
        ''', (tenant_id, user_id, reason))
        new_count = 1
    else:
        # Update existing warnings
        reasons = result['warning_reasons'] or ""
        if reason:
            reasons = f"{reasons}\n{datetime.now().isoformat()}: {reason}" if reasons else f"{datetime.now().isoformat()}: {reason}"

        new_count = result['warnings'] + 1
        cursor.execute('''
            UPDATE tenant_warnings
            SET warnings = ?, last_warning = CURRENT_TIMESTAMP, warning_reasons = ?
            WHERE tenant_id = ? AND user_id = ?
        ''', (new_count, reasons, tenant_id, user_id))

    conn.commit()
    conn.close()
    return new_count

def remove_warning(tenant_id: int, user_id: int) -> int:
    """Remove one warning from user and return new count"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT warnings FROM tenant_warnings WHERE tenant_id = ? AND user_id = ?",
        (tenant_id, user_id)
    )
    result = cursor.fetchone()

    if result and result['warnings'] > 0:
        new_count = result['warnings'] - 1
        cursor.execute('''
            UPDATE tenant_warnings
            SET warnings = ?, last_warning = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND user_id = ?
        ''', (new_count, tenant_id, user_id))
        conn.commit()
    else:
        new_count = 0

    conn.close()
    return new_count

def reset_warnings(tenant_id: int, user_id: int):
    """Reset warnings for user"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE tenant_warnings
        SET warnings = 0, last_warning = NULL, warning_reasons = NULL
        WHERE tenant_id = ? AND user_id = ?
    ''', (tenant_id, user_id))

    conn.commit()
    conn.close()

# ==================== FILTER MANAGEMENT ====================

def get_filter_words(tenant_id: int) -> List[str]:
    """Get all filtered words for a tenant"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT word FROM tenant_filters WHERE tenant_id = ?", (tenant_id,))
    results = cursor.fetchall()
    conn.close()

    return [row['word'] for row in results]

def add_filter_word(tenant_id: int, word: str, added_by: int = None) -> bool:
    """Add word to filter list"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO tenant_filters (tenant_id, word, added_by)
            VALUES (?, ?, ?)
        ''', (tenant_id, word, added_by))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        # Word already exists
        conn.close()
        return False

def remove_filter_word(tenant_id: int, word: str) -> bool:
    """Remove word from filter list"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM tenant_filters WHERE tenant_id = ? AND word = ?",
        (tenant_id, word)
    )
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return deleted

# ==================== LOGGING ====================

def log_action(tenant_id: int, user_id: int, admin_id: int, action: str, reason: str = "", duration_minutes: int = None):
    """Log moderation action"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO tenant_logs (tenant_id, user_id, admin_id, action, reason, duration_minutes)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (tenant_id, user_id, admin_id, action, reason, duration_minutes))

    conn.commit()
    conn.close()

def get_tenant_stats(tenant_id: int) -> Dict:
    """Get statistics for a tenant"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Total warnings
    cursor.execute("SELECT COUNT(*) as count FROM tenant_warnings WHERE tenant_id = ?", (tenant_id,))
    total_warnings = cursor.fetchone()['count']

    # Total filters
    cursor.execute("SELECT COUNT(*) as count FROM tenant_filters WHERE tenant_id = ?", (tenant_id,))
    total_filters = cursor.fetchone()['count']

    # Total actions
    cursor.execute("SELECT COUNT(*) as count FROM tenant_logs WHERE tenant_id = ?", (tenant_id,))
    total_actions = cursor.fetchone()['count']

    # Recent actions (last 24h)
    yesterday = (datetime.now() - timedelta(days=1)).isoformat()

    cursor.execute(
        "SELECT COUNT(*) as count FROM tenant_logs WHERE tenant_id = ? AND action = 'BAN' AND timestamp > ?",
        (tenant_id, yesterday)
    )
    recent_bans = cursor.fetchone()['count']

    cursor.execute(
        "SELECT COUNT(*) as count FROM tenant_logs WHERE tenant_id = ? AND action = 'KICK' AND timestamp > ?",
        (tenant_id, yesterday)
    )
    recent_kicks = cursor.fetchone()['count']

    cursor.execute(
        "SELECT COUNT(*) as count FROM tenant_logs WHERE tenant_id = ? AND action = 'MUTE' AND timestamp > ?",
        (tenant_id, yesterday)
    )
    recent_mutes = cursor.fetchone()['count']

    cursor.execute(
        "SELECT COUNT(*) as count FROM tenant_logs WHERE tenant_id = ? AND action = 'WARN' AND timestamp > ?",
        (tenant_id, yesterday)
    )
    recent_warns = cursor.fetchone()['count']

    conn.close()

    return {
        'total_warnings': total_warnings,
        'total_filters': total_filters,
        'total_actions': total_actions,
        'recent_bans': recent_bans,
        'recent_kicks': recent_kicks,
        'recent_mutes': recent_mutes,
        'recent_warns': recent_warns
    }

# ==================== GLOBAL ADMINS ====================

def is_global_admin(user_id: int) -> bool:
    """Check if user is a global admin"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM global_admins WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()

    return result is not None

def log_member_activity(tenant_id: int, user_id: int, action: str):
    """Log member join/leave activity"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO member_activity (tenant_id, user_id, action) VALUES (?, ?, ?)",
        (tenant_id, user_id, action)
    )

    conn.commit()
    conn.close()

def get_member_activity_stats(tenant_id: int) -> dict:
    """Get member join/leave statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Joined in last 7 days
    cursor.execute(
        "SELECT COUNT(*) FROM member_activity WHERE tenant_id = ? AND action = 'joined' AND timestamp > datetime('now', '-7 days')",
        (tenant_id,)
    )
    joined_7d = cursor.fetchone()[0]

    # Left in last 7 days
    cursor.execute(
        "SELECT COUNT(*) FROM member_activity WHERE tenant_id = ? AND action = 'left' AND timestamp > datetime('now', '-7 days')",
        (tenant_id,)
    )
    left_7d = cursor.fetchone()[0]

    # Joined in last 30 days
    cursor.execute(
        "SELECT COUNT(*) FROM member_activity WHERE tenant_id = ? AND action = 'joined' AND timestamp > datetime('now', '-30 days')",
        (tenant_id,)
    )
    joined_30d = cursor.fetchone()[0]

    # Left in last 30 days
    cursor.execute(
        "SELECT COUNT(*) FROM member_activity WHERE tenant_id = ? AND action = 'left' AND timestamp > datetime('now', '-30 days')",
        (tenant_id,)
    )
    left_30d = cursor.fetchone()[0]

    conn.close()

    return {
        'joined_7d': joined_7d,
        'left_7d': left_7d,
        'joined_30d': joined_30d,
        'left_30d': left_30d,
        'net_growth_7d': joined_7d - left_7d,
        'net_growth_30d': joined_30d - left_30d
    }

def get_user_language(user_id: int) -> str:
    """Get user's preferred language for private chat"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT language FROM user_preferences WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()

    if result:
        return result[0]
    return 'uz'  # Default to Uzbek

def set_user_language(user_id: int, language: str):
    """Set user's preferred language for private chat"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO user_preferences (user_id, language, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            language = excluded.language,
            updated_at = CURRENT_TIMESTAMP
    ''', (user_id, language))

    conn.commit()
    conn.close()

def add_global_admin(user_id: int, username: str = ""):
    """Add global admin"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("INSERT INTO global_admins (user_id, username) VALUES (?, ?)", (user_id, username))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False

    conn.close()
    return success

def remove_global_admin(user_id: int):
    """Remove global admin"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM global_admins WHERE user_id = ?", (user_id,))
    removed = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return removed

# ==================== CLEANUP ====================

def cleanup_old_logs(days: int = 30) -> int:
    """Delete logs older than specified days"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cursor.execute("DELETE FROM tenant_logs WHERE timestamp < ?", (cutoff,))

    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    return deleted

def deactivate_tenant(chat_id: int):
    """Deactivate a tenant (mark as inactive)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE tenants SET is_active = 0 WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()

def delete_tenant_data(chat_id: int):
    """Delete all data for a tenant (WARNING: Cannot be undone!)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM tenant_warnings WHERE tenant_id = ?", (chat_id,))
    cursor.execute("DELETE FROM tenant_filters WHERE tenant_id = ?", (chat_id,))
    cursor.execute("DELETE FROM tenant_logs WHERE tenant_id = ?", (chat_id,))
    cursor.execute("DELETE FROM chat_admins WHERE chat_id = ?", (chat_id,))
    cursor.execute("DELETE FROM tenants WHERE chat_id = ?", (chat_id,))

    conn.commit()
    conn.close()

# ==================== CHAT ADMINS CACHE ====================

def update_chat_admin(chat_id: int, user_id: int, status: str):
    """Update or add a chat admin to the database cache"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO chat_admins (chat_id, user_id, status, updated_at)
        VALUES (?, ?, ?, datetime('now'))
    ''', (chat_id, user_id, status))

    conn.commit()
    conn.close()

def remove_chat_admin(chat_id: int, user_id: int):
    """Remove a user from chat admins cache"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM chat_admins WHERE chat_id = ? AND user_id = ?', (chat_id, user_id))

    conn.commit()
    conn.close()

def get_user_admin_chats(user_id: int) -> List[tuple]:
    """Get all chats where user is an admin (from cache)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT ca.chat_id, t.chat_title
        FROM chat_admins ca
        JOIN tenants t ON ca.chat_id = t.chat_id
        WHERE ca.user_id = ? AND ca.status IN ('creator', 'administrator')
        ORDER BY t.chat_title
    ''', (user_id,))

    results = cursor.fetchall()
    conn.close()

    return [(row['chat_id'], row['chat_title']) for row in results]

def refresh_chat_admins(chat_id: int):
    """Clear all admins for a chat (to force refresh from Telegram API)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM chat_admins WHERE chat_id = ?', (chat_id,))

    conn.commit()
    conn.close()
