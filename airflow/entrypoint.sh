#!/bin/bash
set -euo pipefail

ROLE="${1:-webserver}"

# --- Neon IPv4 fix -----------------------------------------------------
if [ -n "${AIRFLOW__DATABASE__SQL_ALCHEMY_CONN:-}" ]; then
    if [[ "$AIRFLOW__DATABASE__SQL_ALCHEMY_CONN" != *"hostaddr="* ]]; then
        NEON_IPV4=$(python3 - "$AIRFLOW__DATABASE__SQL_ALCHEMY_CONN" <<'PYEOF'
import socket, sys
from urllib.parse import urlparse
host = urlparse(sys.argv[1]).hostname
try:
    print(socket.getaddrinfo(host, None, socket.AF_INET)[0][4][0])
except Exception:
    print("")
PYEOF
)
        if [ -n "$NEON_IPV4" ]; then
            SEP="&"; [[ "$AIRFLOW__DATABASE__SQL_ALCHEMY_CONN" != *"?"* ]] && SEP="?"
            echo "Airflow DB: forcing IPv4 -> $NEON_IPV4"
            export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="${AIRFLOW__DATABASE__SQL_ALCHEMY_CONN}${SEP}hostaddr=${NEON_IPV4}"
        fi
    fi
fi
# -------------------------------------------------------------------------

if [ "$ROLE" = "init" ]; then
    # Clean up stale PID files from a previous, uncleanly-stopped run
    rm -f "${AIRFLOW_HOME}/airflow-webserver.pid"
    rm -f "${AIRFLOW_HOME}/airflow-scheduler.pid"

    echo "Initializing Airflow database..."
    airflow db migrate

    echo "Syncing FAB permissions..."
    airflow sync-perm

    echo "Creating admin user..."
    airflow users create \
        --username "${AIRFLOW_ADMIN_USERNAME}" \
        --password "${AIRFLOW_ADMIN_PASSWORD}" \
        --firstname Megha --lastname U --role Admin --email megha@gmail.com \
        || echo "Admin user already exists, skipping."
    exit 0
fi

if [ "$ROLE" = "webserver" ]; then
    echo "Starting Airflow scheduler..."
    airflow scheduler &

    echo "Starting Airflow webserver..."
    exec airflow webserver
fi

echo "Unknown role: $ROLE" >&2
exit 1