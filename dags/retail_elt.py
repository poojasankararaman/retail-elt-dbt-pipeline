"""Daily retail ELT: load raw -> check freshness -> dbt build -> snapshot.

Paths assume the repo is mounted at /opt/airflow/project (see docker-compose.yml).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT = "/opt/airflow/project"
DBT = f"cd {PROJECT}/retail && dbt"

default_args = {
    "owner": "data-eng",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="retail_elt",
    description="Raw load -> dbt build/test -> SCD2 snapshot",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    default_args=default_args,
    tags=["retail", "dbt"],
) as dag:
    load_raw = BashOperator(
        task_id="load_raw",
        bash_command=f"cd {PROJECT} && python ingestion/load_raw.py --mode append",
    )

    source_freshness = BashOperator(
        task_id="source_freshness",
        bash_command=f"{DBT} source freshness --profiles-dir .",
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=f"{DBT} build --profiles-dir .",
    )

    dbt_snapshot = BashOperator(
        task_id="dbt_snapshot",
        bash_command=f"{DBT} snapshot --profiles-dir .",
    )

    load_raw >> source_freshness >> dbt_build >> dbt_snapshot
