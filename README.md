#!/bin/sh
# entrypoint.sh
# Handles PUID/PGID privilege dropping for Unraid and other hosts.
# If running as root, uses gosu to drop to PUID/PGID.
# If already running as non-root, executes directly.

PUID=${PUID:-99}
PGID=${PGID:-100}

echo ""
echo "-------------------------------------"
echo "      emptyarr"
echo "-------------------------------------"
echo "  PUID: ${PUID}"
echo "  PGID: ${PGID}"
echo "-------------------------------------"
echo ""

# Only do privilege setup if running as root
if [ "$(id -u)" = "0" ]; then
    # Create group if GID doesn't exist
    if ! getent group "${PGID}" > /dev/null 2>&1; then
        addgroup --gid "${PGID}" appgroup 2>/dev/null || true
    fi

    # Create user if UID doesn't exist
    if ! getent passwd "${PUID}" > /dev/null 2>&1; then
        useradd --no-log-init -u "${PUID}" \
            -g "$(getent group ${PGID} | cut -d: -f1)" \
            --no-create-home --shell /bin/sh appuser 2>/dev/null || true
    fi

    # Chown app files (not mounted volumes)
    chown -R "${PUID}:${PGID}" /app/src /app/templates /app/app.py 2>/dev/null || true

    # Drop privileges and run
    exec gosu "${PUID}:${PGID}" "$@"
else
    # Already non-root, just run directly
    exec "$@"
fi