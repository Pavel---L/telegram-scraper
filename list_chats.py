#!/usr/bin/env python3
"""
list_chats.py — print accessible Telegram dialogs with useful metadata.

Features:
- Reads API credentials from env:
    TELEGRAM_API_ID, TELEGRAM_API_HASH (required)
    TELEGRAM_STRING_SESSION (optional),
    DATA_DIR (optional, default: ./.telegram-scraper-data)
- Session source: StringSession (if TELEGRAM_STRING_SESSION set)
    or file session in DATA_DIR.
- For each dialog prints:
    title, id, username, type, peer_id, is_self, is_bot, deleted,
    participants_count, megagroup, broadcast, and InputPeer (with access_hash).
- --json flag emits one JSON object per dialog (JSON lines).
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.utils import get_peer_id


# ---------- helpers ----------


def get_required_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        print(f"[env] ERROR: {name} environment variable is required", file=sys.stderr)
        sys.exit(2)
    return v


def get_data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", "./.telegram-scraper-data"))


def build_client() -> TelegramClient:
    api_id = int(get_required_env("TELEGRAM_API_ID"))
    api_hash = get_required_env("TELEGRAM_API_HASH")
    string_session = os.getenv("TELEGRAM_STRING_SESSION")
    session_base = get_data_dir() / "session"
    if string_session:
        return TelegramClient(StringSession(string_session), api_id, api_hash)
    return TelegramClient(str(session_base), api_id, api_hash)


def input_peer_to_dict(ip: Any) -> Dict[str, Any]:
    """Serialize InputPeer* structure into dict."""
    if ip is None:
        return {}
    data: Dict[str, Any] = {"type": ip.__class__.__name__}
    for f in ("user_id", "chat_id", "channel_id"):
        if hasattr(ip, f):
            data[f] = getattr(ip, f)
    if hasattr(ip, "access_hash"):
        data["access_hash"] = getattr(ip, "access_hash")
    return data


# ---------- main ----------


async def list_chats(client: TelegramClient, as_json: bool) -> None:
    dialogs = await client.get_dialogs()

    for d in dialogs:
        ent = d.entity
        title = (
            getattr(ent, "title", None) or getattr(ent, "first_name", None) or "NoTitle"
        )
        username = getattr(ent, "username", None)
        ent_type = ent.__class__.__name__
        peer = get_peer_id(ent)

        # Resolve InputPeer (may fail for special/system entities)
        try:
            ip = await client.get_input_entity(ent)
        except Exception:
            ip = None

        record = {
            "title": title,
            "id": getattr(ent, "id", None),
            "username": username,
            "type": ent_type,
            "peer_id": peer,
            "is_self": getattr(ent, "is_self", False),
            "is_bot": getattr(ent, "bot", False),
            "deleted": getattr(ent, "deleted", False),
            "participants_count": getattr(ent, "participants_count", None),
            "megagroup": getattr(ent, "megagroup", None),
            "broadcast": getattr(ent, "broadcast", None),
            "input_peer": input_peer_to_dict(ip),
        }

        if as_json:
            print(json.dumps(record, ensure_ascii=False))
            continue

        print(f"{title}")
        print(f"  ID: {record['id']}")
        print(f"  Username: {record['username']}")
        print(f"  Type: {record['type']}")
        print(f"  PeerID: {record['peer_id']}")
        if record["is_self"]:
            print("  👤 This is your own account")
        if record["is_bot"]:
            print("  ⚙️  Bot account")
        if record["deleted"]:
            print("  ❌ Deleted account")
        if record["participants_count"] is not None:
            print(f"  Participants: {record['participants_count']}")
        if record["megagroup"]:
            print("  🗨️  Supergroup")
        if record["broadcast"]:
            print("  📢 Channel")
        ipd = record["input_peer"]
        if ipd:
            ids = ", ".join(f"{k}={v}" for k, v in ipd.items() if k != "type")
            print(f"  InputPeer: {ipd['type']} ({ids})")
        print("-" * 40)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="List accessible Telegram dialogs with PeerID and InputPeer."
    )
    p.add_argument(
        "--json", action="store_true", help="Emit JSON lines (one object per dialog)."
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    client = build_client()
    with client:
        client.loop.run_until_complete(list_chats(client, as_json=args.json))


if __name__ == "__main__":
    main()
