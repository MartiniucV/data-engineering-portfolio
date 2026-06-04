"""
MedInsight Dashboard - Shared Sidebar Filters
"""

import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboard.components.db import query


def render_sidebar_filters() -> dict:
    """Render all global sidebar filters and return selected values."""

    st.sidebar.markdown("## Filters")

    # Date range
    st.sidebar.markdown("### Date Range")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("From", value=date(2023, 1, 1), key="filter_start")
    with col2:
        end_date = st.date_input("To", value=date(2024, 12, 31), key="filter_end")

    # Specialty
    specialties_df = query("SELECT DISTINCT specialty FROM analytics.fct_appointments ORDER BY 1")
    specialties = ["All"] + specialties_df["specialty"].dropna().tolist() if not specialties_df.empty else ["All"]
    selected_specialty = st.sidebar.selectbox("Specialty", specialties, key="filter_specialty")

    # City
    cities_df = query("SELECT DISTINCT clinic_city FROM analytics.fct_appointments ORDER BY 1")
    cities = ["All"] + cities_df["clinic_city"].dropna().tolist() if not cities_df.empty else ["All"]
    selected_city = st.sidebar.selectbox("City", cities, key="filter_city")

    # Doctor
    if selected_specialty != "All":
        doctors_df = query(
            "SELECT DISTINCT doctor_name FROM analytics.fct_appointments WHERE specialty = :spec ORDER BY 1",
            spec=selected_specialty,
        )
    else:
        doctors_df = query("SELECT DISTINCT doctor_name FROM analytics.fct_appointments ORDER BY 1")
    doctors = ["All"] + doctors_df["doctor_name"].dropna().tolist() if not doctors_df.empty else ["All"]
    selected_doctor = st.sidebar.selectbox("Doctor", doctors, key="filter_doctor")

    st.sidebar.markdown("---")
    st.sidebar.caption("MedInsight Analytics Platform v1.0")

    return {
        "start_date": start_date,
        "end_date": end_date,
        "specialty": selected_specialty,
        "city": selected_city,
        "doctor": selected_doctor,
    }


def build_where_clause(filters: dict, table_alias: str = "") -> tuple[str, dict]:
    """Build a SQL WHERE clause from the filters dict."""
    prefix = f"{table_alias}." if table_alias else ""
    conditions = [
        f"{prefix}appointment_date >= :start_date",
        f"{prefix}appointment_date <= :end_date",
    ]
    params: dict = {
        "start_date": filters["start_date"],
        "end_date": filters["end_date"],
    }
    if filters.get("specialty") and filters["specialty"] != "All":
        conditions.append(f"{prefix}specialty = :specialty")
        params["specialty"] = filters["specialty"]
    if filters.get("city") and filters["city"] != "All":
        conditions.append(f"{prefix}clinic_city = :city")
        params["city"] = filters["city"]
    if filters.get("doctor") and filters["doctor"] != "All":
        conditions.append(f"{prefix}doctor_name = :doctor")
        params["doctor"] = filters["doctor"]

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    return where, params
