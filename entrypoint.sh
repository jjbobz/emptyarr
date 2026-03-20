#!/bin/sh
# entrypoint.sh
# Handles PUID/PGID so the app runs as the right user on Unraid and elsewhere.
# Defaults to nobody:users (99:100) which is the Unraid standard.

PUID=${PUID:-99}
PGID=${PGID:-100}

echo "
-------------------------------------
      emptyarr
-------------------------------------
  PUID: ${PUID}
  PGID: ${PGID}
-------------------------------------
"

# Create group if it doesn't exist with this GID
if ! getent group "${PGID}" > /dev/null 2>&1; then
    addgroup --gid "${PGID}" appgroup
fi

# Create user if it doesn't exist with this UID
if ! getent passwd "${PUID}" > /dev/null 2>&1; then
    adduser --disabled-password --gecos "" --uid "${PUID}" \
        --ingroup "$(getent group ${PGID} | cut -d: -f1)" appuser
fi

# Give ownership of the app directory to the runtime user
chown -R "${PUID}:${PGID}" /app

# Drop privileges and run the app
exec su-exec "${PUID}:${PGID}" "$@"