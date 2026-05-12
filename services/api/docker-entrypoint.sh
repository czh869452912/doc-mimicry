#!/bin/sh
set -eu

python services/api/scripts/bootstrap_db.py
alembic -c services/api/alembic.ini upgrade head
exec "$@"
