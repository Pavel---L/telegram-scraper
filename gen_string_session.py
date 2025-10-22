#!/usr/bin/env python3
"""
gen_string_session.py

Utility script to generate a Telethon StringSession for
use in Telegram bots or scrapers.

Usage:
    1. Set environment variables TELEGRAM_API_ID and TELEGRAM_API_HASH, or
       enter them interactively when prompted.
    2. Run the script:
           python gen_string_session.py
    3. Follow the login instructions in the console.
    4. Copy the printed STRING_SESSION value and store it securely
       (for example, as TELEGRAM_STRING_SESSION in your environment variables).

This session can be reused in code like:
    client = TelegramClient(StringSession(STRING_SESSION), api_id, api_hash)
"""

from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import os


def main() -> None:
    api_id = int(os.getenv("TELEGRAM_API_ID") or input("Enter your TELEGRAM_API_ID: "))
    api_hash = os.getenv("TELEGRAM_API_HASH") or input("Enter your TELEGRAM_API_HASH: ")

    print("\nLogging in to Telegram...")
    with TelegramClient(StringSession(), api_id, api_hash) as client:
        session_str = client.session.save()
        print("\nSuccessfully logged in!")
        print("Here is your StringSession:\n")
        print(f"STRING_SESSION={session_str}")
        print("\nKeep this string private! Anyone with it can access your account.")


if __name__ == "__main__":
    main()
