#!/bin/bash
set -e
airflow db migrate
airflow sync-perm
airflow users create \
    --username ${AIRFLOW_ADMIN_USERNAME} \
    --password ${AIRFLOW_ADMIN_PASSWORD} \
    --firstname Admin --lastname User \
    --role Admin --email admin@example.com 2>/dev/null || true
exec airflow webserver &
exec airflow scheduler