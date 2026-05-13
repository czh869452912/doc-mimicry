#!/bin/sh
set -eu

if [ "${DOCAGENT_RUN_MIGRATIONS:-1}" = "1" ]; then
    python services/api/scripts/bootstrap_db.py
    alembic -c services/api/alembic.ini upgrade head
fi

exec "$@"
