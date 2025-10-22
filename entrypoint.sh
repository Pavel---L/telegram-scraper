#!/usr/bin/env sh
set -e

echo "[entrypoint] CMD_ARGS: ${CMD_ARGS}" >&2
echo "[entrypoint] Extra args: $*" >&2
exec python /app/tg_chat_scrape.py ${CMD_ARGS} "$@"