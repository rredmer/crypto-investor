#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$ROOT_DIR/.env"

echo "Generating secrets..."

DJANGO_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
DJANGO_ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
FT_JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
FT_API_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
BACKUP_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

if [ -f "$ENV_FILE" ]; then
    echo "Updating existing .env file..."
    # Remove old keys if present
    sed -i '/^DJANGO_SECRET_KEY=/d' "$ENV_FILE"
    sed -i '/^DJANGO_ENCRYPTION_KEY=/d' "$ENV_FILE"
    sed -i '/^FT_JWT_SECRET=/d' "$ENV_FILE"
    sed -i '/^FT_API_PASS=/d' "$ENV_FILE"
    sed -i '/^FREQTRADE__API_SERVER__JWT_SECRET_KEY=/d' "$ENV_FILE"
    sed -i '/^FREQTRADE__API_SERVER__PASSWORD=/d' "$ENV_FILE"
    sed -i '/^BACKUP_ENCRYPTION_KEY=/d' "$ENV_FILE"
else
    echo "Creating new .env file..."
fi

cat >> "$ENV_FILE" << EOF
DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY
DJANGO_ENCRYPTION_KEY=$DJANGO_ENCRYPTION_KEY
FREQTRADE__API_SERVER__JWT_SECRET_KEY=$FT_JWT_SECRET
FREQTRADE__API_SERVER__PASSWORD=$FT_API_PASS
BACKUP_ENCRYPTION_KEY=$BACKUP_KEY
EOF

chmod 600 "$ENV_FILE"

echo "Secrets written to $ENV_FILE (permissions set to 600)"
echo "  - DJANGO_SECRET_KEY"
echo "  - DJANGO_ENCRYPTION_KEY (Fernet)"
echo "  - FREQTRADE__API_SERVER__JWT_SECRET_KEY"
echo "  - FREQTRADE__API_SERVER__PASSWORD"
echo "  - BACKUP_ENCRYPTION_KEY"
