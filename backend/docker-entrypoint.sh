#!/bin/bash
set -e

echo "→ Checking database directory permissions..."
touch /project/backend/data/.write-test && rm /project/backend/data/.write-test || {
    echo "FATAL: Cannot write to /project/backend/data/" >&2; exit 1
}

echo "→ Running migrations..."
python manage.py migrate --run-syncdb

if [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "→ Creating superuser from env (if needed)..."
    python manage.py createsuperuser --noinput \
        --username "${DJANGO_SUPERUSER_USERNAME:-admin}" \
        --email "${DJANGO_SUPERUSER_EMAIL:-admin@localhost}" 2>/dev/null || true
else
    echo "→ Skipping superuser creation (set DJANGO_SUPERUSER_PASSWORD to enable)"
fi

echo "→ Validating environment..."
python manage.py validate_env || true

echo "→ Collecting static files..."
python manage.py collectstatic --noinput --clear 2>/dev/null

echo "→ Running pre-flight checks..."
python manage.py pilot_preflight || echo "WARNING: Pre-flight returned NO-GO (check logs)"

echo "→ Closing startup DB connections..."
python -c "
# Close Django connections from startup commands (migrate, collectstatic, etc.)
# so Daphne starts with a clean connection slate.
# NOTE: Do NOT run PRAGMA wal_checkpoint(TRUNCATE) here or anywhere.
# TRUNCATE changes the WAL file inode under Docker virtiofs bind mounts,
# which causes 'disk I/O error' on all connections that opened the old inode.
try:
    from django.db import connections
    for conn in connections.all():
        conn.close()
    print('  Startup connections closed')
except Exception:
    pass
" || true

echo "→ Starting Daphne..."
exec "$@"
