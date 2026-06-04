"""
Airflow DAG — SmartCity End-to-End Pipeline Orchestration
=========================================================
Azure Production: This DAG runs on Azure-managed Airflow (via Azure Managed Airflow
in Azure Data Factory or Astronomer on AKS).

Alternatively on Databricks: replace with Databricks Workflows (jobs with tasks),
which is the preferred orchestrator when all compute is on Databricks clusters.

Pipeline schedule: Daily at 03:00 UTC
SLA: All tasks complete by 06:00 UTC (city council reports at 09:00)

DAG structure:
    ingest_api
         │
    transform_spark
         │
    store_delta ─── quality_check
         │                │
         └────────────────┘
                  │
           notify_success (or notify_failure on any upstream failure)

Airflow concepts demonstrated:
    - DAG with schedule_interval and catchup=False
    - PythonOperator for each pipeline step
    - XCom: pass file paths between tasks
    - TaskGroup: logical grouping of related tasks
    - SLA miss callback: alert if task takes too long
    - on_failure_callback: send alert to Azure Monitor / Teams
"""
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Graceful Airflow import ────────────────────────────────────────────────────
# Airflow may not be installed locally; the DAG definition is still useful
# as documentation and can be deployed to any Airflow environment.
try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
    from airflow.utils.task_group import TaskGroup
    from airflow.operators.empty import EmptyOperator
    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False
    logger.warning("Airflow not installed. DAG definition is for reference only.")
    # Stub classes so the file can be imported and inspected
    class DAG:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
    class PythonOperator:
        def __init__(self, *args, **kwargs): pass
    class TaskGroup:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
    class EmptyOperator:
        def __init__(self, *args, **kwargs): pass


# ── Callbacks (ADF equivalent: Web Activity → Logic App → send Teams notification) ──

def on_sla_miss(dag, task_list, blocking_task_list, slas, blocking_tis):
    """
    Called when a task misses its SLA.
    Real Azure: triggers Azure Monitor Alert → Action Group → Teams/email.
    """
    logger.warning("SLA MISS: tasks=%s blocking=%s", task_list, blocking_task_list)


def on_failure_callback(context: dict) -> None:
    """
    Called when any task fails.
    Real Azure: posts to Azure Monitor custom metric + Teams channel.
        import requests
        requests.post(teams_webhook_url, json={"text": f"FAILED: {context['task']}"})
    """
    logger.error(
        "TASK FAILED: dag=%s  task=%s  run_id=%s",
        context.get("dag").dag_id,
        context.get("task_instance").task_id,
        context.get("run_id"),
    )


def on_success_callback(context: dict) -> None:
    """Log pipeline completion with timing metrics."""
    ti       = context.get("task_instance")
    duration = (ti.end_date - ti.start_date).total_seconds() if ti else 0
    logger.info("TASK SUCCEEDED: %s  duration=%.1fs", ti.task_id if ti else "?", duration)


# ── Task implementations ──────────────────────────────────────────────────────

def task_ingest_api(**context) -> str:
    """
    Task 1: Ingest from Open-Meteo API.
    Real Azure: calls Azure Function via HTTP trigger (decoupled, serverless)
    XCom return: path to raw Parquet file for downstream tasks.
    """
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from ingestion.api_ingest import ingest
    output_path = ingest(days_back=7)
    # XCom push — real Airflow: ti.xcom_push(key='raw_path', value=str(output_path))
    return str(output_path)


def task_transform_spark(**context) -> str:
    """
    Task 2: Run Spark transformations.
    Real Azure: submits a Databricks job via Databricks REST API
    (DatabricksSubmitRunOperator from apache-airflow-providers-databricks).

        from airflow.providers.databricks.operators.databricks import DatabricksSubmitRunOperator
        DatabricksSubmitRunOperator(
            task_id='transform_spark',
            databricks_conn_id='databricks_default',
            json={"run_name": "smartcity_transform", "existing_cluster_id": cluster_id,
                  "spark_python_task": {"python_file": "dbfs:/jobs/spark_transform.py"}}
        )
    """
    from processing.spark_transform import run
    run()
    return str(Path("data/smartcity/gold/daily_station_metrics.parquet"))


def task_store_delta(**context) -> str:
    """Task 3: Write to Delta storage layer (simulates ADLS Gen2 write)."""
    from storage.delta_storage import ADLSGen2StorageLayer
    import pandas as pd

    gold_path = Path("data/smartcity/gold/daily_station_metrics.parquet")
    if not gold_path.exists():
        raise FileNotFoundError("Gold file not found — transform task must run first")

    storage = ADLSGen2StorageLayer()
    df      = pd.read_parquet(gold_path)
    out     = storage.write_delta_table(df, "analytics", "daily_station_metrics", mode="overwrite")
    return str(out)


def task_quality_check(**context) -> dict:
    """
    Task 4: Run data quality checks.
    Real Azure: calls Azure Function for lightweight checks, or runs
    Great Expectations suite via a Databricks notebook task.
    """
    from monitoring.data_quality import run_quality_suite
    return run_quality_suite()


def task_notify_success(**context) -> None:
    """
    Task 5: Send success notification.
    Real Azure: Web Activity → Logic App → POST to Teams/Slack webhook.
    """
    logger.info("SmartCity pipeline completed successfully.")
    logger.info("Dashboard available at: http://localhost:8501")
    logger.info("City council report ready for 09:00 UTC meeting.")


def task_notify_failure(**context) -> None:
    """Task 5 (failure branch): Alert on-call engineer."""
    logger.error("PIPELINE FAILURE — AQI data may be stale. On-call: check Azure Monitor.")


# ── DAG definition ─────────────────────────────────────────────────────────────

DEFAULT_ARGS = {
    "owner":              "data-engineering",
    "depends_on_past":    False,
    "retries":            2,
    "retry_delay":        timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay":    timedelta(minutes=30),
    "on_failure_callback": on_failure_callback,
    "on_success_callback": on_success_callback,
    "sla":                timedelta(hours=2),
}

with DAG(
    dag_id="smartcity_environmental_pipeline",
    description="Daily SmartCity AQI ingestion, processing, and dashboard refresh",
    schedule_interval="0 3 * * *",          # 03:00 UTC daily
    start_date=datetime(2024, 1, 1),
    catchup=False,                           # Don't backfill on first deployment
    max_active_runs=1,                       # Prevent concurrent runs
    default_args=DEFAULT_ARGS,
    tags=["smartcity", "environmental", "production"],
    sla_miss_callback=on_sla_miss,
    doc_md="""
    ## SmartCity Environmental Pipeline
    Ingests data from 8 monitoring stations, transforms to Silver/Gold,
    validates quality, and refreshes the public AQI dashboard.
    **SLA**: complete by 06:00 UTC  **Owner**: data-engineering@smartcity.gov
    """,
) as dag:

    start = EmptyOperator(task_id="pipeline_start")

    ingest = PythonOperator(
        task_id="ingest_api_data",
        python_callable=task_ingest_api,
        doc_md="Fetch environmental data from Open-Meteo for all 8 monitoring stations",
    )

    with TaskGroup("processing") as processing_group:
        transform = PythonOperator(
            task_id="spark_transform",
            python_callable=task_transform_spark,
        )
        store = PythonOperator(
            task_id="store_delta",
            python_callable=task_store_delta,
        )
        quality = PythonOperator(
            task_id="quality_check",
            python_callable=task_quality_check,
        )
        transform >> store >> quality

    notify_ok = PythonOperator(
        task_id="notify_success",
        python_callable=task_notify_success,
        trigger_rule="all_success",
    )
    notify_fail = PythonOperator(
        task_id="notify_failure",
        python_callable=task_notify_failure,
        trigger_rule="one_failed",
    )

    start >> ingest >> processing_group >> [notify_ok, notify_fail]


# ── Standalone runner (no Airflow needed) ─────────────────────────────────────

def run_standalone() -> None:
    """Run the full pipeline sequentially without Airflow."""
    logger.info("Running SmartCity pipeline in standalone mode (no Airflow)")
    ctx: dict = {}
    steps = [
        ("ingest_api_data",  task_ingest_api),
        ("spark_transform",  task_transform_spark),
        ("store_delta",      task_store_delta),
        ("quality_check",    task_quality_check),
        ("notify_success",   task_notify_success),
    ]
    for name, fn in steps:
        logger.info("--- Task: %s ---", name)
        try:
            result = fn(**ctx)
            if result:
                logger.info("  Output: %s", result)
        except Exception as exc:
            logger.error("  FAILED: %s", exc)
            task_notify_failure(**ctx)
            break


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_standalone()
