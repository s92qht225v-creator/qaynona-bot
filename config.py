"""
Configuration Management for Multi-Tenant Moderation Bot
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration class for the bot"""

    # Bot Token (REQUIRED)
    BOT_TOKEN = os.getenv("BOT_TOKEN")

    if not BOT_TOKEN:
        raise ValueError(
            "BOT_TOKEN is not set! Please create a .env file with your bot token.\n"
            "Get your token from @BotFather on Telegram."
        )

    # Database Configuration
    DATABASE_NAME = os.getenv("DATABASE_NAME", "multi_tenant_moderation.db")

    # Default Settings
    DEFAULT_MAX_WARNINGS = int(os.getenv("DEFAULT_MAX_WARNINGS", "3"))
    FLOOD_LIMIT = int(os.getenv("FLOOD_LIMIT", "5"))  # messages
    FLOOD_TIME = int(os.getenv("FLOOD_TIME", "10"))  # seconds
    VERIFICATION_TIMEOUT = int(os.getenv("VERIFICATION_TIMEOUT", "120"))  # seconds

    # Feature Flags (default enabled)
    ENABLE_ANTIFLOOD = os.getenv("ENABLE_ANTIFLOOD", "true").lower() == "true"
    ENABLE_WORD_FILTER = os.getenv("ENABLE_WORD_FILTER", "true").lower() == "true"
    ENABLE_VERIFICATION = os.getenv("ENABLE_VERIFICATION", "true").lower() == "true"
    ENABLE_WELCOME_MESSAGE = os.getenv("ENABLE_WELCOME_MESSAGE", "true").lower() == "true"

    # Admin Configuration
    GLOBAL_ADMIN_IDS = []
    admin_ids_str = os.getenv("GLOBAL_ADMIN_IDS", "")
    if admin_ids_str:
        try:
            GLOBAL_ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]
        except ValueError:
            print("Warning: Invalid GLOBAL_ADMIN_IDS format. Should be comma-separated numbers.")

    # Logging Configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "")

    # Rate Limiting
    RATE_LIMIT_COMMANDS = int(os.getenv("RATE_LIMIT_COMMANDS", "3"))  # seconds

    # Multi-tenant Settings
    MAX_TENANTS = int(os.getenv("MAX_TENANTS", "1000"))  # Maximum number of groups
    AUTO_CREATE_TENANT = os.getenv("AUTO_CREATE_TENANT", "true").lower() == "true"

    # Language Support
    DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "en")
    SUPPORTED_LANGUAGES = ["en", "es", "fr", "de", "ru", "ar"]

    # Security Settings
    REQUIRE_GROUP_ADMIN = os.getenv("REQUIRE_GROUP_ADMIN", "true").lower() == "true"
    ALLOW_PRIVATE_COMMANDS = os.getenv("ALLOW_PRIVATE_COMMANDS", "false").lower() == "true"

    @classmethod
    def validate(cls):
        """Validate configuration"""
        errors = []

        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN is required")

        if cls.DEFAULT_MAX_WARNINGS < 1:
            errors.append("DEFAULT_MAX_WARNINGS must be at least 1")

        if cls.FLOOD_LIMIT < 1:
            errors.append("FLOOD_LIMIT must be at least 1")

        if cls.FLOOD_TIME < 1:
            errors.append("FLOOD_TIME must be at least 1")

        if errors:
            raise ValueError(f"Configuration errors:\n" + "\n".join(errors))

        return True

    @classmethod
    def print_config(cls):
        """Print current configuration (for debugging)"""
        print("=" * 50)
        print("Multi-Tenant Moderation Bot Configuration")
        print("=" * 50)
        print(f"Database: {cls.DATABASE_NAME}")
        print(f"Max Warnings: {cls.DEFAULT_MAX_WARNINGS}")
        print(f"Flood Limit: {cls.FLOOD_LIMIT} messages in {cls.FLOOD_TIME}s")
        print(f"Verification Timeout: {cls.VERIFICATION_TIMEOUT}s")
        print(f"Anti-flood: {'Enabled' if cls.ENABLE_ANTIFLOOD else 'Disabled'}")
        print(f"Word Filter: {'Enabled' if cls.ENABLE_WORD_FILTER else 'Disabled'}")
        print(f"Verification: {'Enabled' if cls.ENABLE_VERIFICATION else 'Disabled'}")
        print(f"Welcome Message: {'Enabled' if cls.ENABLE_WELCOME_MESSAGE else 'Disabled'}")
        print(f"Global Admins: {len(cls.GLOBAL_ADMIN_IDS)}")
        print(f"Max Tenants: {cls.MAX_TENANTS}")
        print(f"Default Language: {cls.DEFAULT_LANGUAGE}")
        print("=" * 50)

# Validate configuration on import
try:
    Config.validate()
except ValueError as e:
    print(f"Configuration Error: {e}")
    raise
