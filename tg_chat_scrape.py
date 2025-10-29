#!/usr/bin/env python3

from typing import Any, Callable
import os
import sys
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from telethon import TelegramClient, events
from telethon.events import NewMessage
from telethon.tl.custom.message import Message
from telethon.utils import get_peer_id
from telethon.sessions import StringSession


import psycopg2
from psycopg2.extras import Json


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Error: {name} environment variable is required", file=sys.stderr)
        sys.exit(1)
    return value


# Read config from environment
API_ID = int(get_required_env("TELEGRAM_API_ID"))
API_HASH = get_required_env("TELEGRAM_API_HASH")

raw = get_required_env("TELEGRAM_CHAT_ID")
CHAT_ID: int | str = int(raw) if raw.lstrip("-").isdigit() else raw

LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "24"))

# Mode selection: --db flag or USE_DATABASE env var
USE_DATABASE = ("--db" in sys.argv) or bool(os.getenv("DATABASE_URL"))
DATABASE_URL = os.getenv("DATABASE_URL")

if USE_DATABASE:
    if not DATABASE_URL:
        print("[db] ERROR: --db set but DATABASE_URL is missing", file=sys.stderr)
        sys.exit(2)
    print("[db] DATABASE_URL detected, database mode enabled", file=sys.stderr)


DATA_DIR = Path(os.getenv("DATA_DIR", "./.telegram-scraper-data"))
STATE_DIR = DATA_DIR / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)


def get_state_file(chat_id: int | str) -> Path:
    return STATE_DIR / str(chat_id)


def get_db_connection(database_url: str | None) -> psycopg2.extensions.connection:
    return psycopg2.connect(database_url)


SESSION_BASENAME = DATA_DIR / "session"
SESSION_FILE = Path(str(SESSION_BASENAME) + ".session")
STRING_SESSION = os.getenv("TELEGRAM_STRING_SESSION")
if STRING_SESSION:
    TELEGRAM_CLIENT = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
else:
    TELEGRAM_CLIENT = TelegramClient(str(SESSION_BASENAME), API_ID, API_HASH)


def read_last_id_from_file(state_file: Path) -> int:
    try:
        return int(state_file.read_text().strip())
    except FileNotFoundError:
        print(
            f"[state] No state file found at {state_file}, starting from 0",
            file=sys.stderr,
        )
        return 0
    except (ValueError, OSError) as e:
        print(
            f"[state] Error reading {state_file}: {e}. Starting from 0", file=sys.stderr
        )
        return 0


def read_last_id_from_db(db_conn: Any, peer_id: int) -> int:
    try:
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT last_message_id FROM scraper_state WHERE chat_peer_id = %s",
                (peer_id,),
            )
            result = cur.fetchone()
            return int(result[0]) if result else 0
    except Exception as e:
        print(f"Error reading last_id from DB: {e}", file=sys.stderr)
        return 0


def read_last_id(db_conn: Any, peer_id: int, reset: bool = False) -> int:
    if reset:
        return 0
    if db_conn is not None:
        return read_last_id_from_db(db_conn, peer_id)
    else:
        return read_last_id_from_file(get_state_file(peer_id))


def save_last_id_to_file(state_file: Path, msg_id: int) -> None:
    try:
        state_file.write_text(str(msg_id))
    except OSError as e:
        print(f"Error saving state file: {e}", file=sys.stderr)


def save_last_id_to_db(db_conn: Any, peer_id: int, msg_id: int) -> None:
    try:
        with db_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scraper_state (chat_peer_id, last_message_id, last_run_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (chat_peer_id)
                DO UPDATE SET last_message_id = %s, last_run_at = NOW()
            """,
                (peer_id, msg_id, msg_id),
            )
            db_conn.commit()
    except Exception as e:
        print(f"Error saving last_id to DB: {e}", file=sys.stderr)


def save_last_id_conn(db_conn: Any | None, peer_id: int, msg_id: int) -> None:
    if db_conn is not None:
        save_last_id_to_db(db_conn, peer_id, msg_id)
    else:
        save_last_id_to_file(get_state_file(peer_id), msg_id)


def message_to_dict(peer_id: int, msg: Message) -> dict[str, Any]:
    """Convert Telegram message to dict/JSON"""
    return {
        "id": msg.id,
        "chat_id": msg.chat_id,
        "peer_id": peer_id,
        "date": msg.date.isoformat() if msg.date else None,
        "text": msg.text,
        "sender_id": msg.sender_id,
        # Sender info
        "sender": {
            "id": msg.sender.id if msg.sender else None,
            "username": msg.sender.username if msg.sender else None,
            "first_name": msg.sender.first_name if msg.sender else None,
            "last_name": msg.sender.last_name if msg.sender else None,
            "is_bot": getattr(msg.sender, "bot", False) if msg.sender else False,
        }
        if msg.sender
        else None,
        # Message metadata
        "edit_date": msg.edit_date.isoformat() if msg.edit_date else None,
        "out": msg.out,
        "mentioned": msg.mentioned,
        "silent": msg.silent,
        "post": msg.post,
        "views": msg.views,
        "forwards": msg.forwards,
        "pinned": msg.pinned,
        # Reply and forward
        "reply_to_msg_id": msg.reply_to_msg_id,
        "forward": (
            {
                "from_id": get_peer_id(msg.forward.from_id)
                if msg.forward.from_id
                else None,
                "from_name": msg.forward.from_name,
                "date": msg.forward.date.isoformat() if msg.forward.date else None,
            }
            if msg.forward
            else None
        ),
        # Media
        "has_media": msg.media is not None,
        "media_type": msg.media.__class__.__name__ if msg.media else None,
        # Reactions
        "reactions": [
            {
                "emoji": getattr(r.reaction, "emoticon", None),
                "custom_emoji_id": getattr(r.reaction, "document_id", None),
                "count": r.count,
                "i_reacted": hasattr(r, "chosen_order"),
                "my_reaction_order": getattr(r, "chosen_order", None),
            }
            for r in (getattr(msg.reactions, "results", []) if msg.reactions else [])
        ]
        if msg.reactions
        else [],
        # Entities (links, mentions, etc)
        "entities": [
            {
                "type": e.__class__.__name__,
                "offset": e.offset,
                "length": e.length,
                "url": getattr(e, "url", None),
            }
            for e in (msg.entities or [])
        ],
    }


def output_msg_to_stdout(msg_dict: dict[str, Any]) -> None:
    print(json.dumps(msg_dict, ensure_ascii=False), flush=True)


def output_msg_to_db_reuse(
    db_conn: Any, peer_id: int, msg_dict: dict[str, Any], msg: Any
) -> None:
    try:
        with db_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO messages (chat_peer_id, message_id, date, data)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (chat_peer_id, message_id)
                DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()
            """,
                (peer_id, msg.id, msg.date, Json(msg_dict)),
            )
            db_conn.commit()

        print(
            f"[DB] Saved message {msg.id} for chat {peer_id}",
            file=sys.stderr,
            flush=True,
        )
    except Exception as e:
        print(f"Error saving message {msg.id}: {e}", file=sys.stderr)


def output_msg(db_conn: Any | None, peer_id: int, message: Message) -> None:
    msg_dict = message_to_dict(peer_id, message)

    if db_conn is None:
        output_msg_to_stdout(msg_dict)
    else:
        output_msg_to_db_reuse(db_conn, peer_id, msg_dict, message)


async def dump_messages(
    client: TelegramClient,
    chat_id: int | str,
    last_id: int,
    since: Any,
    callback: Callable[[Message], None] | None = None,
) -> tuple[int, int]:
    """Fetch messages since last_id or lookback period"""

    max_id: int = last_id
    count: int = 0
    messages = client.iter_messages(
        chat_id, min_id=last_id, offset_date=since, reverse=True
    )

    async for msg in messages:
        if callback is not None:
            callback(msg)

        if msg.id is not None:
            max_id = max(max_id, msg.id)
            count += 1

    return max_id, count


async def main(client: TelegramClient, db_conn: Any, chat_id: int | str) -> None:
    await client.start()

    # Get chat info
    chat_entity = await client.get_entity(chat_id)
    peer_id = get_peer_id(chat_entity)
    title = getattr(chat_entity, "title", chat_id)
    mode = "DATABASE" if db_conn else "STDOUT"

    print(f"Scraping: {title} [{peer_id} | {chat_id}]", file=sys.stderr)

    # Fetch history
    last_id = read_last_id(db_conn, peer_id, "--reset" in sys.argv)
    since = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)

    print(f"[{mode}] Fetching since ID {last_id} or {since}", file=sys.stderr)

    max_id, count = await dump_messages(
        client, chat_id, last_id, since, lambda msg: output_msg(db_conn, peer_id, msg)
    )

    if max_id > last_id:
        save_last_id_conn(db_conn, peer_id, max_id)

    print(f"[{mode}] Processed {count} messages. Last ID: {max_id}", file=sys.stderr)

    # Tail mode
    if "-f" not in sys.argv:
        return

    print(
        "--- Listening for new messages (Ctrl+C to stop) ---",
        file=sys.stderr,
        flush=True,
    )

    last_printed_id = [max_id]

    @client.on(events.NewMessage(chats=chat_id))
    async def handler(event: NewMessage.Event) -> None:
        msg = event.message
        if msg.id > last_printed_id[0]:
            output_msg(db_conn, peer_id, msg)
            save_last_id_conn(db_conn, peer_id, msg.id)
            last_printed_id[0] = msg.id

    try:
        await client.run_until_disconnected()
    except KeyboardInterrupt:
        if last_printed_id[0] > max_id:
            print(f"\nSaving final state: {last_printed_id[0]}", file=sys.stderr)
            save_last_id_conn(db_conn, peer_id, last_printed_id[0])
        raise


# Main execution
start_time = time.monotonic()
db_conn = None

try:
    if USE_DATABASE:
        db_conn = get_db_connection(DATABASE_URL)

    TELEGRAM_CLIENT.loop.run_until_complete(main(TELEGRAM_CLIENT, db_conn, CHAT_ID))

except KeyboardInterrupt:
    print("\n[signal] Shutdown gracefully by user", file=sys.stderr)

except Exception as e:
    print(f"[fatal] Unhandled exception: {e}", file=sys.stderr)
    import traceback

    traceback.print_exc(file=sys.stderr)
    sys.exit(1)

finally:
    # Cleanup database connection
    if db_conn:
        try:
            db_conn.close()
            print("[db] Connection closed", file=sys.stderr)
        except Exception as e:
            print(f"[db] Error closing connection: {e}", file=sys.stderr)

    # Print execution time
    elapsed = time.monotonic() - start_time
    print(f"[exit] Script finished in {elapsed:.1f}s", file=sys.stderr)
