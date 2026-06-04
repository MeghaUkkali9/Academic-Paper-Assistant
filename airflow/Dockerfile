FROM python:3.12-slim

# Set environment variables
ENV AIRFLOW_HOME=/opt/airflow
ENV AIRFLOW_VERSION=2.10.3
ENV PYTHON_VERSION=3.12
ENV CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        libpq-dev \
        poppler-utils \
        tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Create airflow user
RUN groupadd -r -g 50000 airflow && \
    useradd -r -u 50000 -g airflow -d ${AIRFLOW_HOME} -s /bin/bash airflow

# Create directories
RUN mkdir -p ${AIRFLOW_HOME}/dags \
             ${AIRFLOW_HOME}/logs \
             ${AIRFLOW_HOME}/plugins \
             ${AIRFLOW_HOME}/scripts && \
    chown -R 50000:50000 ${AIRFLOW_HOME} && \
    chmod -R 755 ${AIRFLOW_HOME}

# Install Airflow
RUN pip install --no-cache-dir \
    "apache-airflow[postgres,celery,redis]==${AIRFLOW_VERSION}" \
    --constraint "${CONSTRAINT_URL}" \
    && pip install --no-cache-dir psycopg2-binary

# Copy and install project dependencies
COPY requirements-airflow.txt /tmp/requirements-airflow.txt
RUN pip install --no-cache-dir -r /tmp/requirements-airflow.txt

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl --fail http://localhost:8080/health || exit 1

USER airflow
WORKDIR ${AIRFLOW_HOME}

EXPOSE 8080

CMD ["/entrypoint.sh"]