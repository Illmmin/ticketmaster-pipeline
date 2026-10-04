FROM apache/airflow:2.10.5-python3.11

USER airflow

# Dépendances de l'ingestion, installées dans l'environnement d'Airflow
COPY ingestion/requirements.txt /tmp/ingestion-requirements.txt
RUN pip install --no-cache-dir -r /tmp/ingestion-requirements.txt

# dbt dans un venv séparé : évite les conflits de dépendances avec Airflow
RUN python -m venv /home/airflow/dbt-venv \
    && /home/airflow/dbt-venv/bin/pip install --no-cache-dir "dbt-bigquery>=1.10"

# Permet au DAG de faire `from main import run` (module d'ingestion monté en volume)
ENV PYTHONPATH="/opt/airflow/ingestion:${PYTHONPATH}"
