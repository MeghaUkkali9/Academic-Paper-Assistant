#!/bin/bash
set -e

airflow db migrate
airflow sync-perm

airflow users create \
    --username ${AIRFLOW_ADMIN_USERNAME} \
    --password ${AIRFLOW_ADMIN_PASSWORD} \
    --firstname Megha \
    --lastname U \
    --role Admin \
    --email megha@gmail.com 2>/dev/null || true

# Start scheduler in background
airflow scheduler &

# Keep webserver as PID 1
exec airflow webserver