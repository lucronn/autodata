#!/bin/sh
set +x
set -eu
cd /
exec /usr/bin/env -i /usr/bin/python3 -I /opt/autodata/bin/backup_restore.py backup "$@"
