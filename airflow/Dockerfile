FROM apache/airflow:2.10.3-python3.12

ENV AIRFLOW_HOME=/opt/airflow
ENV AIRFLOW_VERSION=2.10.3
ENV PYTHON_VERSION=3.12
ENV CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        poppler-utils \
        tesseract-ocr \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/.docling-models && chown -R airflow:root /app

USER airflow

COPY requirements-airflow.txt /tmp/requirements-airflow.txt
RUN pip install --no-cache-dir -r /tmp/requirements-airflow.txt \
    --constraint "${CONSTRAINT_URL}"

RUN docling-tools models download layout tableformer --output-dir /app/.docling-models

COPY --chown=airflow:airflow entrypoint.sh /entrypoint.sh
USER root
RUN chmod +x /entrypoint.sh
USER airflow

WORKDIR ${AIRFLOW_HOME}

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
CMD ["webserver"]