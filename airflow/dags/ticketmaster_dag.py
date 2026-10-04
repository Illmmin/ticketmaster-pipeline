from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator, ShortCircuitOperator
from airflow.utils.trigger_rule import TriggerRule

PROJECT_DIR = "/opt/airflow/ticketmaster-pipeline"

default_args = {
    "owner": "data-team",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "email_on_failure": True,
    "email": ["alerts@ton-projet.com"],
}

with DAG(
    dag_id="ticketmaster_daily_ingestion",
    description="Ingestion quotidienne Ticketmaster : events, prix, artistes",
    schedule_interval="0 6 * * *",
    start_date=datetime(2024, 1, 1),
    default_args=default_args,
    catchup=False,
    tags=["ticketmaster", "ingestion", "music"],
) as dag:

    check_quota = BashOperator(
        task_id="check_quota",
        bash_command=f"""
            cd {PROJECT_DIR}
            python -c "
import psycopg2, os
conn = psycopg2.connect(host=os.environ['DB_HOST'], dbname=os.environ['DB_NAME'],
                        user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'])
cur = conn.cursor()
cur.execute(\"SELECT COUNT(*) FROM api_calls_log WHERE called_at::date = CURRENT_DATE\")
calls = cur.fetchone()[0]
print(f'Appels déjà effectués aujourd hui: {calls}/5000')
if calls >= 4900:
    raise Exception(f'Quota quasi-épuisé ({calls}/5000) — DAG annulé.')
conn.close()
"
        """,
    )

   fetch_events = BashOperator(
        task_id="fetch_events",
        bash_command=f"cd {PROJECT_DIR} && python -m src.pipeline --genres Rock Pop Hip-Hop Electronic Jazz",
        execution_timeout=timedelta(hours=2),
    )

    refresh_prices = BashOperator(
        task_id="refresh_prices",
        bash_command=f"cd {PROJECT_DIR} && python -m src.pipeline --refresh-prices",
        execution_timeout=timedelta(hours=1),
    )

   enrich_artists = BashOperator(
        task_id="enrich_artists",
        bash_command=f"cd {PROJECT_DIR} && python -m src.pipeline --enrich-artists",
        execution_timeout=timedelta(minutes=30),
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {PROJECT_DIR}/dbt && dbt run --profiles-dir . --target prod",
        trigger_rule=TriggerRule.ALL_DONE,  # lance même si refresh échoue
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {PROJECT_DIR}/dbt && dbt test --profiles-dir . --target prod",
    )

    report = BashOperator(
        task_id="quota_report",
        bash_command=f"""
            cd {PROJECT_DIR}
            python -c "
import psycopg2, os
conn = psycopg2.connect(host=os.environ['DB_HOST'], dbname=os.environ['DB_NAME'],
                        user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'])
cur = conn.cursor()
cur.execute('SELECT * FROM v_quota_today')
row = cur.fetchone()
cols = [d[0] for d in cur.description]
print(dict(zip(cols, row)))
conn.close()
"
        """,
        trigger_rule=TriggerRule.ALL_DONE,
    )

    check_quota >> fetch_events >> [refresh_prices, enrich_artists] >> dbt_run >> dbt_test >> report
