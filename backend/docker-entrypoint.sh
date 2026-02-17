#!/bin/bash
set -e

echo "→ Running migrations..."
python manage.py migrate --run-syncdb

echo "→ Creating admin user (if needed)..."
python manage.py shell -c "
from django.contrib.auth.models import User
u, created = User.objects.get_or_create(username='admin', defaults={'is_superuser': True, 'is_staff': True})
if created:
    u.set_password('admin')
    u.save()
    print('Created admin user')
else:
    print('Admin user exists')
" 2>/dev/null || true

echo "→ Starting Daphne..."
exec "$@"
