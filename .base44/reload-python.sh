#!/bin/sh
# Base44 sandbox live-reload wrapper for the Python services.
#
# The Go API reloads with `air` from its bind mount. The Python workers are
# plain long-running modules with no reloader of their own: an edit reaches the
# container through the bind mount, but the running interpreter keeps the code
# it imported at startup, so the change silently had no effect until the
# service was restarted. This wrapper runs the service command as a child and
# re-execs it whenever a watched source file changes, so saving a file is
# enough.
#
# Usage (from docker-compose.base44.yml):
#   sh /app/reload-python.sh python -m autodata_ingestion.http_service
set -eu

watch_dirs="${BASE44_RELOAD_WATCH_DIRS:-/app/src}"
poll_seconds="${BASE44_RELOAD_POLL_SECONDS:-1}"

# One comparable value for the mtime+size of every watched file.
snapshot() {
  find $watch_dirs -type f \( -name '*.py' -o -name '*.json' \) \
    -exec stat -c '%n %Y %s' {} + 2>/dev/null | sort | cksum
}

child=""
stop_child() {
  [ -n "$child" ] || return 0
  kill "$child" 2>/dev/null || true
  attempts=0
  while kill -0 "$child" 2>/dev/null && [ "$attempts" -lt 10 ]; do
    sleep 0.2
    attempts=$((attempts + 1))
  done
  kill -9 "$child" 2>/dev/null || true
  wait "$child" 2>/dev/null || true
  child=""
}
trap 'stop_child; exit 0' INT TERM

state="$(snapshot)"
"$@" &
child=$!
echo "base44: reloader watching $watch_dirs for: $*" >&2

while :; do
  sleep "$poll_seconds"
  if ! kill -0 "$child" 2>/dev/null; then
    # The service exited on its own: propagate its status so Compose's
    # restart policy and the recorded exit code stay meaningful.
    set +e
    wait "$child"
    status=$?
    exit "$status"
  fi
  next="$(snapshot)"
  if [ "$next" != "$state" ]; then
    state="$next"
    echo "base44: source changed, restarting: $*" >&2
    stop_child
    "$@" &
    child=$!
  fi
done
