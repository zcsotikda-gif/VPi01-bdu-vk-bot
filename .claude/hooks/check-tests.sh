#!/bin/sh
# Stop: перед завершением ответа pytest и ruff должны быть зелёными (CLAUDE.md проекта).
# exit 2 — Claude получает stderr и продолжает работу. Повторно не блокирует:
# при stop_hook_active=true выходит 0, чтобы не зациклиться.
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
input=$(cat)
case "$input" in
  *'"stop_hook_active":true'* | *'"stop_hook_active": true'*) exit 0 ;;
esac
[ -x .venv/bin/pytest ] || exit 0

if ! out=$(.venv/bin/pytest -q -p no:cacheprovider 2>&1); then
  printf 'pytest не зелёный — исправь до завершения:\n%s\n' "$(printf '%s\n' "$out" | tail -n 15)" >&2
  exit 2
fi
if ! out=$(.venv/bin/ruff check src tests --output-format concise 2>&1); then
  printf 'ruff check не чистый:\n%s\n' "$out" >&2
  exit 2
fi
exit 0
