from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime

PYTHON = "python3"
SCRIPT = "/opt/medallion/pipeline.py"

with DAG(
    dag_id="medallion_pipeline",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False
) as dag:

    bronze = BashOperator(task_id="bronze", bash_command=f"{PYTHON} {SCRIPT} bronze")
    silver = BashOperator(task_id="silver", bash_command=f"{PYTHON} {SCRIPT} silver")
    gold   = BashOperator(task_id="gold",   bash_command=f"{PYTHON} {SCRIPT} gold")

    bronze >> silver >> gold
