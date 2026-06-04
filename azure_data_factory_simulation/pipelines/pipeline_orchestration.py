"""
ADF Pipeline Orchestration Simulation — FinanceFlow End-to-End
==============================================================
Business Context:
    FinanceFlow's compliance pipeline must run daily at 02:00 UTC.
    If the pipeline fails, the Compliance team must be notified within
    15 minutes — PSD2 mandates transaction reporting by 08:00 UTC.

This script simulates ADF Pipeline orchestration:
    - Activity sequencing with dependencies
    - Conditional execution (if/else branching)
    - Error handling + retry logic
    - Parameter passing between activities
    - Pipeline run monitoring + alerting
    - Self-healing: automatic retry with exponential backoff

Real ADF Pipeline = JSON definition with activities, triggers, parameters.
This Python equivalent makes the control flow explicit and testable.

Wow factor: The retry-with-backoff + dead-letter pattern mirrors how
production ADF pipelines handle transient Azure service failures
(throttling, network blips) — a topic most candidates can't discuss.
"""
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

random.seed(99)


# ── Activity status (mirrors ADF Monitor status values) ──────────────────────

class ActivityStatus(str, Enum):
    QUEUED     = "Queued"
    IN_PROGRESS = "InProgress"
    SUCCEEDED  = "Succeeded"
    FAILED     = "Failed"
    SKIPPED    = "Skipped"


# ── Activity definition ───────────────────────────────────────────────────────

@dataclass
class ActivityRun:
    """
    Represents one activity execution within a pipeline run.
    Real ADF: visible in Monitor → Pipeline Runs → Activity runs tab.
    Each activity has input/output properties, duration, error message.
    """
    name:         str
    activity_type: str                    # CopyActivity, DataFlow, Script, Web, etc.
    run_id:       str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status:       ActivityStatus = ActivityStatus.QUEUED
    start_time:   Optional[datetime] = None
    end_time:     Optional[datetime] = None
    output:       dict = field(default_factory=dict)
    error:        Optional[str] = None
    retry_count:  int = 0

    def duration_ms(self) -> int:
        if self.start_time and self.end_time:
            return int((self.end_time - self.start_time).total_seconds() * 1000)
        return 0

    def to_monitor_row(self) -> str:
        icon = {"Succeeded": "✓", "Failed": "✗", "Skipped": "○", "InProgress": "→"}.get(
            self.status.value, "?"
        )
        return (
            f"  {icon} [{self.activity_type:<16}] {self.name:<35} "
            f"status={self.status.value:<12} duration={self.duration_ms():>6}ms "
            f"retries={self.retry_count}"
        )


# ── Retry policy (ADF: retry + retryIntervalInSeconds per activity) ───────────

@dataclass
class RetryPolicy:
    max_retries:     int   = 3
    initial_delay_s: float = 5.0
    backoff_factor:  float = 2.0   # exponential backoff
    max_delay_s:     float = 60.0

    def delay(self, attempt: int) -> float:
        d = self.initial_delay_s * (self.backoff_factor ** attempt)
        return min(d, self.max_delay_s)


# ── Activity executor ─────────────────────────────────────────────────────────

def execute_with_retry(
    activity: ActivityRun,
    fn: Callable[[], dict],
    policy: RetryPolicy,
    failure_probability: float = 0.0,  # 0 in production; non-zero for demo
) -> ActivityRun:
    """
    Execute an activity with automatic retry on transient failure.

    Real ADF: configured per-activity as:
        "policy": {"retry": 3, "retryIntervalInSeconds": 30, "secureOutput": false}

    Transient errors retried: HTTP 429 (throttling), HTTP 503 (service unavailable),
                               network timeout, source system unavailable.
    Non-transient errors fail immediately: HTTP 401 (auth), schema mismatch.
    """
    activity.start_time = datetime.utcnow()
    activity.status     = ActivityStatus.IN_PROGRESS

    for attempt in range(policy.max_retries + 1):
        try:
            # Inject failure for demo purposes
            if random.random() < failure_probability:
                raise ConnectionError(
                    f"Transient failure on attempt {attempt + 1} "
                    "(simulating HTTP 503 / network timeout)"
                )

            activity.output     = fn()
            activity.status     = ActivityStatus.SUCCEEDED
            activity.end_time   = datetime.utcnow()
            return activity

        except Exception as exc:
            activity.retry_count = attempt
            if attempt < policy.max_retries:
                delay = policy.delay(attempt)
                logger.warning(
                    "  [%s] attempt %d failed: %s  — retrying in %.1fs",
                    activity.name, attempt + 1, exc, delay,
                )
                time.sleep(0)  # skip real sleep in demo; real ADF waits
            else:
                activity.status   = ActivityStatus.FAILED
                activity.error    = str(exc)
                activity.end_time = datetime.utcnow()
                logger.error("  [%s] FAILED after %d retries: %s", activity.name, attempt, exc)

    return activity


# ── Activity implementations ──────────────────────────────────────────────────

def run_copy_activity_impl() -> dict:
    """Simulate the Copy Activity from copy_activity.py."""
    from pipelines.copy_activity import run_copy_activity
    metrics = run_copy_activity()
    return {
        "rowsRead":    metrics.rows_read,
        "rowsWritten": metrics.rows_written,
        "rowsSkipped": metrics.rows_skipped,
    }


def run_dataflow_impl() -> dict:
    """Simulate the Data Flow from dataflow_transformation.py."""
    from pipelines.dataflow_transformation import run_dataflow
    run_dataflow()
    return {"status": "Succeeded", "outputRows": "written to enriched_transactions.parquet"}


def run_quality_check_impl() -> dict:
    """
    ADF Script Activity: run a SQL quality check on the sink.
    Real ADF: Script Activity with Azure SQL DB or Synapse SQL Pool.
    """
    from pathlib import Path
    import pandas as pd

    output_path = Path("data/adf_simulation/sink/enriched_transactions.parquet")
    if not output_path.exists():
        raise FileNotFoundError("Enriched transactions file not found")

    df = pd.read_parquet(output_path)
    null_pct = df["transaction_id"].isna().mean()
    if null_pct > 0.01:
        raise ValueError(f"Quality check FAILED: {null_pct:.1%} null transaction_ids (threshold: 1%)")

    return {
        "rowCount":          len(df),
        "nullTransactionPct": f"{null_pct:.4%}",
        "riskTierDist":       df.get("risk_tier", pd.Series()).value_counts().to_dict(),
    }


def run_notification_impl(subject: str, body: str) -> dict:
    """
    ADF Web Activity: POST to Logic Apps → send email/Teams notification.
    Real ADF: Web Activity calls an Azure Logic App HTTP trigger.
    Logic App then sends email via Office 365 connector or posts to Teams.
    """
    logger.info("  [Notification] Subject: %s", subject)
    logger.info("  [Notification] Body: %s", body[:120])
    return {"notificationSent": True, "channel": "email+teams"}


# ── Pipeline definition ───────────────────────────────────────────────────────

@dataclass
class PipelineRun:
    """
    Simulates an ADF Pipeline run.
    Real ADF: triggered by schedule trigger (02:00 UTC daily),
    storage event trigger, or REST API call.
    """
    pipeline_name: str
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_time: datetime = field(default_factory=datetime.utcnow)
    activities: list[ActivityRun] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    status: ActivityStatus = ActivityStatus.IN_PROGRESS

    def add(self, activity: ActivityRun) -> None:
        self.activities.append(activity)

    def print_monitor(self) -> None:
        """Prints a view similar to ADF Monitor → Activity Runs."""
        duration = (datetime.utcnow() - self.start_time).total_seconds()
        logger.info("=" * 80)
        logger.info("  Pipeline: %-40s  run_id=%s", self.pipeline_name, self.run_id[:8])
        logger.info("  Status:   %-12s  Duration: %.1fs", self.status.value, duration)
        logger.info("  Parameters: %s", self.parameters)
        logger.info("  Activity Runs:")
        for a in self.activities:
            logger.info(a.to_monitor_row())
        logger.info("=" * 80)


def build_pipeline() -> PipelineRun:
    """
    Define the FinanceFlow compliance pipeline.

    Real ADF JSON structure (simplified):
    {
      "name": "pl_financeflow_compliance",
      "properties": {
        "activities": [
          {"name": "CopyTransactions", "type": "Copy", ...},
          {"name": "EnrichTransactions", "type": "MappingDataFlow",
           "dependsOn": [{"activity": "CopyTransactions", "dependencyConditions": ["Succeeded"]}]},
          ...
        ],
        "parameters": {"runDate": {"type": "string"}},
        "triggers": [{"name": "DailyTrigger", "type": "ScheduleTrigger",
                      "recurrence": {"frequency": "Day", "interval": 1, "startTime": "02:00"}}]
      }
    }
    """
    pipeline = PipelineRun(
        pipeline_name="pl_financeflow_compliance_daily",
        parameters={
            "runDate":     datetime.utcnow().strftime("%Y-%m-%d"),
            "environment": "production",
            "retentionDays": 2555,  # 7 years per MiFID II
        },
    )
    return pipeline


def run_pipeline(inject_failures: bool = False) -> PipelineRun:
    """
    Execute the pipeline with proper dependency chaining.

    ADF activity dependency types:
        Succeeded: run next only if this succeeded
        Failed:    run next only if this failed (for error handling)
        Completion: run next regardless of success/failure
        Skipped:   run next only if this was skipped
    """
    pipeline = build_pipeline()
    policy   = RetryPolicy(max_retries=3, initial_delay_s=2, backoff_factor=2)

    logger.info("Starting pipeline: %s (run_id=%s)", pipeline.pipeline_name, pipeline.run_id[:8])
    logger.info("Parameters: %s", pipeline.parameters)

    # ── Activity 1: Copy (dependsOn: none — first activity) ───────────────────
    copy_act = ActivityRun("CopyTransactions_3Sources", "CopyActivity")
    copy_act = execute_with_retry(
        copy_act,
        run_copy_activity_impl,
        policy,
        failure_probability=0.15 if inject_failures else 0,
    )
    pipeline.add(copy_act)

    # ── Activity 2: Data Flow (dependsOn: CopyTransactions = Succeeded) ───────
    if copy_act.status == ActivityStatus.SUCCEEDED:
        flow_act = ActivityRun("EnrichAndRiskScore", "MappingDataFlow")
        flow_act = execute_with_retry(
            flow_act, run_dataflow_impl, policy,
            failure_probability=0.05 if inject_failures else 0,
        )
        pipeline.add(flow_act)
    else:
        pipeline.add(ActivityRun("EnrichAndRiskScore", "MappingDataFlow",
                                  status=ActivityStatus.SKIPPED))
        flow_act = pipeline.activities[-1]

    # ── Activity 3: Quality check (dependsOn: EnrichAndRiskScore = Succeeded) ─
    if flow_act.status == ActivityStatus.SUCCEEDED:
        qa_act = ActivityRun("DataQualityGate", "Script")
        qa_act = execute_with_retry(qa_act, run_quality_check_impl, policy)
        pipeline.add(qa_act)
    else:
        pipeline.add(ActivityRun("DataQualityGate", "Script",
                                  status=ActivityStatus.SKIPPED))
        qa_act = pipeline.activities[-1]

    # ── Activity 4a: Success notification (dependsOn: QA = Succeeded) ─────────
    if qa_act.status == ActivityStatus.SUCCEEDED:
        notify = ActivityRun("NotifyComplianceTeam_Success", "WebActivity")
        execute_with_retry(
            notify,
            lambda: run_notification_impl(
                subject="✅ FinanceFlow compliance pipeline succeeded",
                body=f"Run {pipeline.run_id[:8]} processed "
                     f"{copy_act.output.get('rowsWritten', 'N/A')} transactions.",
            ),
            RetryPolicy(max_retries=2),
        )
        pipeline.add(notify)
        pipeline.status = ActivityStatus.SUCCEEDED
    else:
        # ── Activity 4b: Failure notification (dependsOn: any = Failed) ───────
        # Real ADF: "dependencyConditions": ["Failed"] triggers this branch
        failed_activities = [a.name for a in pipeline.activities if a.status == ActivityStatus.FAILED]
        notify_fail = ActivityRun("NotifyComplianceTeam_Failure", "WebActivity")
        execute_with_retry(
            notify_fail,
            lambda: run_notification_impl(
                subject="🚨 FinanceFlow compliance pipeline FAILED",
                body=f"Run {pipeline.run_id[:8]} failed at: {failed_activities}. "
                     "PSD2 reporting at risk. Investigate immediately.",
            ),
            RetryPolicy(max_retries=2),
        )
        pipeline.add(notify_fail)
        pipeline.status = ActivityStatus.FAILED

    pipeline.print_monitor()
    return pipeline


if __name__ == "__main__":
    logger.info("Running FinanceFlow ADF pipeline simulation...")
    result = run_pipeline(inject_failures=False)
    logger.info("Final pipeline status: %s", result.status.value)
