# telegram-scraper

Minimalist Telegram chat scraper in Unix style.  
Fetches new messages incrementally and supports tail mode for real-time monitoring.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue)

---

## ✨ Features

- Incremental scraping with state persistence
- Configurable lookback window (`LOOKBACK_HOURS`, default: 24)
- Optional PostgreSQL storage with upsert and JSONB
- Tail mode (`-f`) for continuous listening
- Reset mode (`--reset`) to re-fetch recent history
- Per-chat state via stable `peer_id`
- Designed to run from cron, Docker, or Railway

---

## ⚙️ Requirements

- Python 3.12+
- [Telethon](https://github.com/LonamiWebs/Telethon)
- Optional: PostgreSQL (if `USE_DATABASE=true`)

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## 🧩 Setup

### 1. Create Telegram API credentials

- Go to [https://my.telegram.org](https://my.telegram.org)
- Log in → API Development Tools → create app → copy `api_id` and `api_hash`

### 2. Get your chat ID

Forward a message from the chat to [@userinfobot](https://t.me/userinfobot)  
→ use the numeric `chat_id` (starts with `-100...` for groups/channels).

### 3. Configure environment

You can export variables manually or create a `.env` file (recommended).

**`.env.example`:**
```dotenv
TELEGRAM_API_ID=1234567
TELEGRAM_API_HASH=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
TELEGRAM_CHAT_ID=-1001234567890
LOOKBACK_HOURS=24

# Optional database mode
USE_DATABASE=false
DATABASE_URL=postgresql://telegram_user:telegram_pass@postgres:5432/telegram

# Data storage for session and state
DATA_DIR=/app/data
```

---

## 🚀 Usage

### STDOUT mode (default)

```bash
python tg_chat_scrape.py | tee -a messages_${TELEGRAM_CHAT_ID}.json
```

### Reset + Tail

Start from lookback period, then listen for new messages:
```bash
python tg_chat_scrape.py --reset -f
```

### With database (requires PostgreSQL)

```bash
python tg_chat_scrape.py --db
```

Or via Docker:
```bash
docker run --rm   --link telegram-postgres:postgres   --env-file .env   -v $(pwd)/.telegram-scraper-data:/app/data   telegram-scraper python /app/tg_chat_scrape.py --db
```

If you use Docker networks instead of legacy `--link`:
```bash
docker network create tgnet
docker run -d --name telegram-postgres --network tgnet   -e POSTGRES_USER=telegram_user -e POSTGRES_PASSWORD=telegram_pass -e POSTGRES_DB=telegram postgres:16

docker run --rm --network tgnet   --env-file .env   -v $(pwd)/.telegram-scraper-data:/app/data   telegram-scraper python /app/tg_chat_scrape.py --db
```

---

## 🗃️ Output

In STDOUT mode each message is emitted as JSON:

```json
{
  "id": 81783,
  "peer_id": 2337723540,
  "date": "2025-10-06T19:45:26+00:00",
  "text": "Hello world",
  "sender_id": 114379332,
  "sender": {
    "username": "john_doe"
  }
}
```

In DB mode, messages are stored in:
- `messages(chat_peer_id, message_id, date, data JSONB)`
- State in `scraper_state(chat_peer_id, last_message_id, last_run_at)`

---

## 🧱 Files Created

| File | Purpose |
|------|----------|
| `$DATA_DIR/session.session` | Telethon session |
| `$DATA_DIR/state/<peer_id>` | Last processed message ID |
| `messages_<chat_id>.json` | STDOUT log (if piped via `tee`) |

---

## ⏰ Cron Example

Fetch every hour:
```cron
0 * * * * cd /path/to/repo && . .env && python tg_chat_scrape.py | tee -a messages_${TELEGRAM_CHAT_ID}.json
```

---

## 🐳 Docker Quickstart

Build:
```bash
docker build -t telegram-scraper .
```

Run (stdout mode):
```bash
docker run --rm -v $(pwd)/.telegram-scraper-data:/app/data --env-file .env telegram-scraper
```

---

## ☁️ Deploy on Railway

1. Push repo to GitHub
2. Connect in [Railway.app](https://railway.app/)
3. Set environment variables from `.env.example`
4. Command:  
   ```
   python tg_chat_scrape.py --db
   ```
5. Add PostgreSQL plugin if you use DB mode

> ⚠️ Note: Railway ephemeral disks mean file-based state/session will reset between deploys —  
> to keep continuity, prefer DB storage.

---

## 🧠 How state works

- Each chat is tracked via numeric `peer_id`
- Messages are fetched starting from last saved ID, but not older than `LOOKBACK_HOURS`
- This ensures:
  - no duplicate processing on restart
  - no deep history crawl if script was idle for long
  - safe incremental operation suitable for cron jobs

---

## 🧰 Troubleshooting

| Issue | Solution |
|-------|-----------|
| `psycopg2.OperationalError: could not translate host name "postgres"` | Use `--link` or `--network` to connect Docker containers |
| `Session expired` | Delete session file in `$DATA_DIR` and rerun |
| No messages appear | Check that `TELEGRAM_CHAT_ID` is numeric and bot/user has access |

---

## 🧑‍💻 Development

Install tools and enable pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
pre-commit run -a
```

Run linter:
```bash
ruff check .
```

---

## 🪶 License

MIT — see [LICENSE](LICENSE)

---

## ❤️ Credits

Built with [Telethon](https://github.com/LonamiWebs/Telethon)  
by Pavlos Labada
