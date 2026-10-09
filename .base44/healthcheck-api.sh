#!/bin/bash
# Liveness probe for the Go API container.
#
# The golang image ships neither curl nor wget, so this uses bash's built-in
# /dev/tcp client against the API's existing read-only /healthz endpoint.
set -eu

exec 3<>/dev/tcp/127.0.0.1/8080
printf 'GET /healthz HTTP/1.0\r\n\r\n' >&3
response=$(cat <&3)

case "$response" in
  *'"status":"ok"'*)
    exit 0
    ;;
esac

echo "unexpected /healthz response: $response" >&2
exit 1
