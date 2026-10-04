"""
DAG quotidien : ingestion Ticketmaster -> BigQuery, puis transformations dbt.

ingest_events  ->  dbt_deps  ->  dbt_build (run + test)
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

DBT_BIN = "/home/airflow/dbt-venv/bin/dbt"
DBT_PROJECT_DIR = "/opt/airflow/dbt/ticketmaster"
DBT_PROFILES_DIR = "/opt/airflow/dbt_profiles"
DBT_FLAGS = f"--project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROFILES_DIR}"

COUNTRY_CODE = "GB"
# L'API Discovery plafonne à 1000 résultats par requête (size x page < 1000).
# Avec size=200, la page 5 déclenche une erreur : on s'arrête donc à 5 pages (0 à 4).
MAX_PAGES = 5


def ingest_events() -> None:
    # Import tardif : le module d'ingestion (monté en volume) n'est chargé
    # qu'à l'exécution de la tâche, pas à chaque parsing du DAG par le scheduler.
    from main import run

    run(city=None, country_code=COUNTRY_CODE, max_pages=MAX_PAGES)


default_args = {
    "owner": "illmmin",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="ticketmaster_daily",
    description="Ingestion Ticketmaster vers BigQuery puis dbt build",
    default_args=default_args,
    start_date=datetime(2026, 10, 1),
    schedule="0 6 * * *",     # tous les jours à 06:00 UTC
    catchup=False,            # pas de rattrapage : l'API renvoie l'état courant
    max_active_runs=1,
    tags=["ticketmaster", "bigquery", "dbt"],
) as dag:

    ingest = PythonOperator(
        task_id="ingest_events",
        python_callable=ingest_events,
    )

    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=f"{DBT_BIN} deps {DBT_FLAGS}",
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=f"{DBT_BIN} build {DBT_FLAGS}",
    )

    ingest >> dbt_deps >> dbt_build
