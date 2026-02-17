#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
DB_FILE="$ROOT_DIR/backend/data/crypto_investor.db"
BACKUP_DIR="$ROOT_DIR/backend/data/backups"

if [ ! -f "$DB_FILE" ]; then
    echo "Database not found at $DB_FILE"
    exit 1
fi

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_BASE="$BACKUP_DIR/crypto_investor_$TIMESTAMP"

echo "Backing up database..."
sqlite3 "$DB_FILE" ".backup '${BACKUP_BASE}.db'"

# Compress with gzip
gzip "${BACKUP_BASE}.db"

# Encrypt with GPG symmetric AES256 if BACKUP_ENCRYPTION_KEY is set
if [ -n "$BACKUP_ENCRYPTION_KEY" ]; then
    echo "$BACKUP_ENCRYPTION_KEY" | gpg --batch --yes --passphrase-fd 0 \
        --symmetric --cipher-algo AES256 \
        -o "${BACKUP_BASE}.db.gz.gpg" "${BACKUP_BASE}.db.gz"
    rm -f "${BACKUP_BASE}.db.gz"

    # SHA256 checksum
    sha256sum "${BACKUP_BASE}.db.gz.gpg" > "${BACKUP_BASE}.db.gz.gpg.sha256"
    echo "Encrypted backup: ${BACKUP_BASE}.db.gz.gpg"
    echo "Checksum: ${BACKUP_BASE}.db.gz.gpg.sha256"

    # Keep only the 7 most recent encrypted backups
    cd "$BACKUP_DIR"
    ls -t crypto_investor_*.db.gz.gpg 2>/dev/null | tail -n +8 | xargs -r rm -f
    ls -t crypto_investor_*.db.gz.gpg.sha256 2>/dev/null | tail -n +8 | xargs -r rm -f
    REMAINING=$(ls -1 crypto_investor_*.db.gz.gpg 2>/dev/null | wc -l)
else
    echo "WARNING: BACKUP_ENCRYPTION_KEY not set — backup is compressed but NOT encrypted."
    echo "Compressed backup: ${BACKUP_BASE}.db.gz"

    # Keep only the 7 most recent compressed backups
    cd "$BACKUP_DIR"
    ls -t crypto_investor_*.db.gz 2>/dev/null | tail -n +8 | xargs -r rm -f
    REMAINING=$(ls -1 crypto_investor_*.db.gz 2>/dev/null | wc -l)
fi

echo "Backups retained: $REMAINING"
