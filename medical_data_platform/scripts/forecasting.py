"""
MedInsight Analytics Platform - Advanced Analytics & Forecasting
Revenue forecasting, no-show prediction, churn analysis, RFM segmentation,
cohort retention, and anomaly detection.
"""

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger
from rich.console import Console
from rich.table import Table
from sklearn.ensemble import GradientBoostingClassifier, IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sqlalchemy import create_engine, text
from statsmodels.tsa.holtwinters import ExponentialSmoothing

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import Settings

console = Console()


class MedInsightForecaster:
    """Runs all predictive analytics models for MedInsight."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine = create_engine(settings.db.url, pool_pre_ping=True)
        self.exports = settings.data.exports_dir
        self.exports.mkdir(exist_ok=True)

    def _query(self, sql: str) -> pd.DataFrame:
        with self.engine.connect() as conn:
            return pd.read_sql(text(sql), conn)

    # ── Revenue forecasting ───────────────────────────────────────────────────

    def forecast_revenue(self, periods: int = 6) -> pd.DataFrame:
        logger.info("Revenue forecasting with Holt-Winters ETS")
        df = self._query("""
            SELECT DATE_TRUNC('month', invoice_date)::DATE AS month,
                   SUM(total_amount)                        AS revenue
            FROM raw.billing
            GROUP BY 1 ORDER BY 1
        """)
        if len(df) < 12:
            logger.warning("Not enough history for revenue forecast")
            return df

        ts = df.set_index("month")["revenue"].astype(float)
        ts.index = pd.DatetimeIndex(ts.index, freq="MS")

        try:
            model = ExponentialSmoothing(ts, trend="add", seasonal="add", seasonal_periods=12)
            fit = model.fit(optimized=True)
            forecast = fit.forecast(periods)
            future_dates = pd.date_range(ts.index[-1] + pd.DateOffset(months=1), periods=periods, freq="MS")
            result = pd.DataFrame({"month": future_dates, "forecasted_revenue": forecast.values})
            result.to_csv(self.exports / "revenue_forecast.csv", index=False)
            logger.info(f"Revenue forecast: {periods} months ahead saved")
            return result
        except Exception as e:
            logger.error(f"Revenue forecast failed: {e}")
            return df

    # ── No-show prediction ────────────────────────────────────────────────────

    def predict_no_shows(self) -> dict:
        logger.info("Training no-show prediction model")
        df = self._query("""
            SELECT a.status,
                   EXTRACT(DOW  FROM a.scheduled_at)::INT AS dow,
                   EXTRACT(HOUR FROM a.scheduled_at)::INT AS hour,
                   EXTRACT(MONTH FROM a.scheduled_at)::INT AS month,
                   p.age,
                   p.risk_score,
                   CASE p.insurance_status WHEN 'CNAS' THEN 0 WHEN 'Private' THEN 1 ELSE 2 END AS insurance_enc,
                   CASE a.channel
                     WHEN 'Online' THEN 0 WHEN 'Telefon' THEN 1 WHEN 'Fizic' THEN 2
                     WHEN 'Aplicatie mobila' THEN 3 ELSE 4 END AS channel_enc,
                   CASE a.urgency_level
                     WHEN 'Electiv' THEN 0 WHEN 'Semigur' THEN 1 ELSE 2 END AS urgency_enc
            FROM raw.appointments a
            JOIN raw.patients p ON a.patient_id = p.patient_id
            WHERE a.status IN ('completed', 'no_show')
        """)

        if len(df) < 500:
            logger.warning("Insufficient data for no-show model")
            return {}

        df["label"] = (df["status"] == "no_show").astype(int)
        features = ["dow", "hour", "month", "age", "risk_score",
                    "insurance_enc", "channel_enc", "urgency_enc"]
        df = df.dropna(subset=features)
        X, y = df[features], df["label"]

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)

        model = GradientBoostingClassifier(n_estimators=100, random_state=42)
        model.fit(X_train_s, y_train)
        y_pred = model.predict(X_test_s)
        y_prob = model.predict_proba(X_test_s)[:, 1]

        auc = roc_auc_score(y_test, y_prob)
        logger.info(f"No-show model AUC: {auc:.4f}")

        fi = pd.DataFrame({"feature": features, "importance": model.feature_importances_})
        fi.sort_values("importance", ascending=False).to_csv(
            self.exports / "noshw_feature_importance.csv", index=False
        )

        return {"auc": auc, "n_train": len(X_train), "n_test": len(X_test), "no_show_rate": float(y.mean())}

    # ── Patient churn prediction ──────────────────────────────────────────────

    def predict_churn(self) -> dict:
        logger.info("Running patient churn analysis")
        df = self._query("""
            SELECT p.patient_id,
                   p.age,
                   p.risk_score,
                   p.insurance_status,
                   COUNT(a.appointment_id)                            AS total_visits,
                   MAX(a.scheduled_at::DATE)                          AS last_visit,
                   MIN(a.scheduled_at::DATE)                          AS first_visit,
                   AVG(a.actual_price)                                AS avg_spend,
                   COUNT(a.appointment_id) FILTER (WHERE a.status='no_show') AS no_shows,
                   COUNT(a.appointment_id) FILTER (WHERE a.status='cancelled') AS cancellations
            FROM raw.patients p
            LEFT JOIN raw.appointments a ON p.patient_id = a.patient_id
            GROUP BY p.patient_id, p.age, p.risk_score, p.insurance_status
        """)

        today = pd.Timestamp("2025-01-01")
        df["last_visit"] = pd.to_datetime(df["last_visit"])
        df["first_visit"] = pd.to_datetime(df["first_visit"])
        df["days_since_last_visit"] = (today - df["last_visit"]).dt.days.fillna(999)
        df["tenure_days"] = (today - df["first_visit"]).dt.days.fillna(0)

        # Define churn: no visit in last 180 days AND had >= 1 visit
        df["churned"] = ((df["days_since_last_visit"] > 180) & (df["total_visits"] > 0)).astype(int)
        churn_rate = df["churned"].mean()
        logger.info(f"Patient churn rate: {churn_rate:.2%}")

        # RFM segmentation
        def safe_qcut_score(series: pd.Series, n_bins: int, ascending: bool = True) -> pd.Series:
            try:
                ranked = series.rank(method="first", na_option="bottom")
                score = pd.cut(ranked, bins=n_bins, labels=range(1, n_bins + 1)).astype(float)
                if not ascending:
                    score = n_bins + 1 - score
                return score.fillna(1).astype(int)
            except Exception:
                return pd.Series(1, index=series.index)

        df["recency_score"] = safe_qcut_score(df["days_since_last_visit"], 4, ascending=False)
        df["frequency_score"] = safe_qcut_score(df["total_visits"], 4, ascending=True)
        df["monetary_score"] = safe_qcut_score(df["avg_spend"].fillna(0), 4, ascending=True)
        df["rfm_score"] = df["recency_score"] + df["frequency_score"] + df["monetary_score"]

        df["segment"] = pd.cut(
            df["rfm_score"],
            bins=[2, 5, 8, 11, 13],
            labels=["At Risk", "Needs Attention", "Loyal", "Champions"],
        )

        segment_summary = df.groupby("segment", observed=False).agg(
            count=("patient_id", "count"),
            avg_visits=("total_visits", "mean"),
            churn_rate=("churned", "mean"),
        ).round(3)

        segment_summary.to_csv(self.exports / "patient_rfm_segments.csv")
        df[["patient_id", "rfm_score", "segment", "churned", "days_since_last_visit"]].to_csv(
            self.exports / "patient_churn_scores.csv", index=False
        )

        logger.info(f"RFM segmentation complete:\n{segment_summary.to_string()}")
        return {"churn_rate": float(churn_rate), "segments": segment_summary.to_dict()}

    # ── Cohort retention analysis ─────────────────────────────────────────────

    def cohort_retention(self) -> pd.DataFrame:
        logger.info("Computing cohort retention analysis")
        df = self._query("""
            SELECT patient_id,
                   DATE_TRUNC('month', scheduled_at)::DATE AS visit_month
            FROM raw.appointments
            WHERE status = 'completed'
            GROUP BY patient_id, DATE_TRUNC('month', scheduled_at)::DATE
        """)

        df["visit_month"] = pd.to_datetime(df["visit_month"])
        first_visit = df.groupby("patient_id")["visit_month"].min().reset_index()
        first_visit.columns = ["patient_id", "cohort_month"]

        df = df.merge(first_visit, on="patient_id")
        df["period"] = (
            (df["visit_month"].dt.year - df["cohort_month"].dt.year) * 12
            + df["visit_month"].dt.month - df["cohort_month"].dt.month
        )

        cohort_size = first_visit.groupby("cohort_month")["patient_id"].nunique()
        retention = df.groupby(["cohort_month", "period"])["patient_id"].nunique().reset_index()
        retention = retention.merge(cohort_size.rename("cohort_size"), on="cohort_month")
        retention["retention_rate"] = retention["patient_id"] / retention["cohort_size"]

        pivot = retention.pivot_table(index="cohort_month", columns="period", values="retention_rate")
        pivot.to_csv(self.exports / "cohort_retention.csv")
        logger.info("Cohort retention matrix saved")
        return pivot

    # ── Anomaly detection ────────────────────────────────────────────────────

    def detect_anomalies(self) -> pd.DataFrame:
        logger.info("Running anomaly detection on billing data")
        df = self._query("""
            SELECT b.billing_id, b.total_amount, b.service_price,
                   b.discount_amount, b.insurance_reimbursement,
                   a.waiting_time_minutes
            FROM raw.billing b
            JOIN raw.appointments a ON b.appointment_id = a.appointment_id
        """)

        features = ["total_amount", "service_price", "discount_amount",
                    "insurance_reimbursement"]
        X = df[features].fillna(0)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        iso = IsolationForest(contamination=0.05, random_state=42)
        df["anomaly_score"] = iso.fit_predict(X_scaled)
        df["is_anomaly"] = df["anomaly_score"] == -1

        anomalies = df[df["is_anomaly"]]
        anomalies.to_csv(self.exports / "billing_anomalies.csv", index=False)
        logger.info(f"Detected {len(anomalies)} billing anomalies ({len(anomalies)/len(df):.2%})")
        return anomalies

    # ── Doctor utilisation ────────────────────────────────────────────────────

    def doctor_utilization(self) -> pd.DataFrame:
        logger.info("Computing doctor utilization rates")
        df = self._query("""
            SELECT d.doctor_id, d.full_name, d.specialty,
                   COUNT(a.appointment_id)                              AS total_slots,
                   COUNT(a.appointment_id) FILTER (WHERE a.status='completed') AS completed,
                   COUNT(a.appointment_id) FILTER (WHERE a.status='no_show')   AS no_shows,
                   COUNT(a.appointment_id) FILTER (WHERE a.status='cancelled') AS cancellations,
                   AVG(a.waiting_time_minutes)                          AS avg_wait_min,
                   SUM(b.total_amount)                                  AS total_revenue
            FROM raw.doctors d
            LEFT JOIN raw.appointments a ON d.doctor_id = a.doctor_id
            LEFT JOIN raw.billing      b ON a.appointment_id = b.appointment_id
            GROUP BY d.doctor_id, d.full_name, d.specialty
        """)

        df["utilization_rate"] = df["completed"] / df["total_slots"].clip(lower=1)
        df["no_show_rate"] = df["no_shows"] / df["total_slots"].clip(lower=1)
        df["cancellation_rate"] = df["cancellations"] / df["total_slots"].clip(lower=1)

        df.sort_values("utilization_rate", ascending=False).to_csv(
            self.exports / "doctor_utilization.csv", index=False
        )
        logger.info("Doctor utilization report saved")
        return df

    # ── Run all ───────────────────────────────────────────────────────────────

    def run(self) -> None:
        logger.info("Starting MedInsight Analytics & Forecasting suite")
        results = {}

        try:
            forecast = self.forecast_revenue()
            results["revenue_forecast"] = f"{len(forecast)} months forecasted"
        except Exception as e:
            logger.error(f"Revenue forecast error: {e}")

        try:
            noshw = self.predict_no_shows()
            results["no_show_model"] = f"AUC={noshw.get('auc', 'N/A'):.3f}"
        except Exception as e:
            logger.error(f"No-show prediction error: {e}")

        try:
            churn = self.predict_churn()
            results["churn_analysis"] = f"Churn rate={churn['churn_rate']:.2%}"
        except Exception as e:
            logger.error(f"Churn analysis error: {e}")

        try:
            cohort = self.cohort_retention()
            results["cohort_retention"] = f"{len(cohort)} cohorts analyzed"
        except Exception as e:
            logger.error(f"Cohort retention error: {e}")

        try:
            anomalies = self.detect_anomalies()
            results["anomaly_detection"] = f"{len(anomalies)} anomalies detected"
        except Exception as e:
            logger.error(f"Anomaly detection error: {e}")

        try:
            util = self.doctor_utilization()
            results["doctor_utilization"] = f"{len(util)} doctors analyzed"
        except Exception as e:
            logger.error(f"Doctor utilization error: {e}")

        tbl = Table(title="[bold green]Analytics Suite Results", header_style="bold magenta")
        tbl.add_column("Module", style="cyan")
        tbl.add_column("Result", style="green")
        for module, result in results.items():
            tbl.add_row(module, result)
        console.print(tbl)

        logger.success("Forecasting suite complete")


def main() -> None:
    settings = Settings()
    forecaster = MedInsightForecaster(settings)
    forecaster.run()


if __name__ == "__main__":
    main()
