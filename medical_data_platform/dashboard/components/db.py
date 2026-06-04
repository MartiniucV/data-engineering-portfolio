"""
MedInsight Dashboard - Database Connection & Query Utilities
"""

import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st
from loguru import logger
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.settings import Settings


@st.cache_resource
def get_engine():
    settings = Settings()
    engine = create_engine(settings.db.url, pool_pre_ping=True, pool_size=5, max_overflow=10)
    return engine


@st.cache_data(ttl=300)
def query(_sql: str, **params) -> pd.DataFrame:
    """Execute SQL and return DataFrame. Result is cached for 5 minutes."""
    engine = get_engine()
    try:
        with engine.connect() as conn:
            return pd.read_sql(text(_sql), conn, params=params)
    except Exception as e:
        logger.error(f"Query failed: {e}")
        st.error(f"Database error: {e}")
        return pd.DataFrame()


def kpi_metric(label: str, value: str, delta: str | None = None, delta_color: str = "normal") -> None:
    """Render a styled KPI metric."""
    st.metric(label=label, value=value, delta=delta, delta_color=delta_color)
