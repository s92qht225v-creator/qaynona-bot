#!/usr/bin/env python3
"""Test if filter_messages handler is registered"""

import sys
sys.path.insert(0, '/root/qaynona-bot')

from bot import application

print("Checking registered handlers...\n")

# Check if MessageHandler for filter_messages exists
for group_number, handlers in application.handlers.items():
    print(f"Group {group_number}:")
    for handler in handlers:
        handler_type = type(handler).__name__
        if handler_type == "MessageHandler":
            print(f"  - MessageHandler (filters: {handler.filters})")
        elif handler_type == "CommandHandler":
            print(f"  - CommandHandler: /{handler.command}")
    print()

print("\nLooking for filter_messages handler...")
found = False
for group_number, handlers in application.handlers.items():
    for handler in handlers:
        if hasattr(handler, 'callback') and handler.callback.__name__ == 'filter_messages':
            print(f"✅ Found filter_messages in group {group_number}")
            print(f"   Filters: {handler.filters}")
            found = True

if not found:
    print("❌ filter_messages handler NOT found!")
