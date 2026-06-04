"""
Unity Catalog Data Lineage Demo

In Databricks Unity Catalog, column-level lineage is captured automatically
whenever you read or write a table via Spark SQL or the DataFrame API.
No code changes needed — the system traces which source columns flow into
which target columns for every table write.

You can query lineage via the system tables:

    -- Table-level lineage
    SELECT * FROM system.access.table_lineage
    WHERE target_table_name = 'weather_daily';

    -- Column-level lineage (Unity Catalog Premium tier)
    SELECT source_table_name, source_column_name,
           target_table_name, target_column_name
    FROM system.access.column_lineage
    WHERE target_table_name = 'weather_daily';

Or visualise it in the Catalog Explorer UI:
    Catalog Explorer → table → Lineage tab → Column lineage graph

This script simulates the lineage graph for our medallion pipeline by
manually declaring the transformation edges. On real Databricks, this
information is captured automatically — you'd just query system tables.

Lineage is valuable for:
  - Impact analysis ("which dashboards break if I rename this column?")
  - Root cause analysis ("where did this null come from?")
  - Compliance ("which tables contain PII sourced from the GDPR scope?")
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

DIVIDER = "─" * 68


@dataclass
class ColumnLineageEdge:
    """
    Represents one column-to-column lineage edge.
    Maps directly to a row in system.access.column_lineage on Databricks.
    """
    source_catalog: str
    source_schema:  str
    source_table:   str
    source_column:  str

    target_catalog: str
    target_schema:  str
    target_table:   str
    target_column:  str

    transform: Optional[str] = None

    @property
    def source_fqn(self) -> str:
        return f"{self.source_catalog}.{self.source_schema}.{self.source_table}"

    @property
    def target_fqn(self) -> str:
        return f"{self.target_catalog}.{self.target_schema}.{self.target_table}"


@dataclass
class LineageGraph:
    edges: list[ColumnLineageEdge] = field(default_factory=list)

    def add(self, edge: ColumnLineageEdge) -> None:
        self.edges.append(edge)

    def upstream_tables(self, target_table: str) -> set[str]:
        """Return all tables that feed into target_table (direct parents)."""
        return {
            e.source_fqn for e in self.edges
            if e.target_table == target_table
        }

    def downstream_tables(self, source_table: str) -> set[str]:
        """Return all tables that consume source_table (direct children)."""
        return {
            e.target_fqn for e in self.edges
            if e.source_table == source_table
        }

    def columns_for_table(self, target_table: str) -> list[ColumnLineageEdge]:
        return [e for e in self.edges if e.target_table == target_table]

    def show_column_lineage(self, target_table: str) -> None:
        edges = self.columns_for_table(target_table)
        if not edges:
            logger.info("  No lineage recorded for: %s", target_table)
            return

        fqn = edges[0].target_fqn
        logger.info("  Target: %s", fqn)
        logger.info("  %-28s  ←  %-35s  [%s]", "TARGET COLUMN", "SOURCE", "TRANSFORM")
        logger.info("  %s", "─" * 66)
        for e in edges:
            src = f"{e.source_table}.{e.source_column}"
            logger.info("  %-28s  ←  %-35s  [%s]",
                        e.target_column, src, e.transform or "direct")

    def impact_analysis(self, source_table: str, source_column: str) -> list[ColumnLineageEdge]:
        """Find all downstream columns that depend on a given source column."""
        return [
            e for e in self.edges
            if e.source_table == source_table and e.source_column == source_column
        ]


def build_medallion_lineage(catalog: str = "portfolio") -> LineageGraph:
    """
    Declare the lineage graph for the weather medallion pipeline.

    On Databricks this is captured automatically by the Delta Lake engine —
    you would never write this manually. It's shown here so you can see
    exactly what Unity Catalog records under the hood.
    """
    graph = LineageGraph()

    def edge(
        src_schema: str, src_table: str, src_col: str,
        tgt_schema: str, tgt_table: str, tgt_col: str,
        transform: Optional[str] = None,
    ) -> ColumnLineageEdge:
        return ColumnLineageEdge(
            source_catalog=catalog, source_schema=src_schema,
            source_table=src_table, source_column=src_col,
            target_catalog=catalog, target_schema=tgt_schema,
            target_table=tgt_table, target_column=tgt_col,
            transform=transform,
        )

    # ── External source → Bronze ──────────────────────────────────────────────
    for col in ["date", "city", "temperature_max", "temperature_min",
                "precipitation_mm", "wind_speed_kmh", "weather_code"]:
        graph.add(ColumnLineageEdge(
            source_catalog="external", source_schema="open_meteo_api",
            source_table="weather_api_response", source_column=col,
            target_catalog=catalog, target_schema="bronze",
            target_table="raw_weather", target_column=col,
            transform="direct copy via requests.get()",
        ))

    # ── Bronze → Silver ───────────────────────────────────────────────────────
    for col in ["date", "city", "temperature_max", "temperature_min",
                "precipitation_mm", "wind_speed_kmh", "weather_code"]:
        graph.add(edge("bronze", "raw_weather", col,
                       "silver", "clean_weather", col,
                       transform="filter: max > min, precip >= 0"))

    graph.add(edge("bronze", "raw_weather", "temperature_max",
                   "silver", "clean_weather", "temp_range",
                   transform="temperature_max - temperature_min"))

    # ── Silver → Gold ─────────────────────────────────────────────────────────
    graph.add(edge("silver", "clean_weather", "date",
                   "gold", "weather_daily", "date",
                   transform="GROUP BY date"))
    graph.add(edge("silver", "clean_weather", "city",
                   "gold", "weather_daily", "city_count",
                   transform="count(city)"))
    graph.add(edge("silver", "clean_weather", "temperature_max",
                   "gold", "weather_daily", "global_avg_max_temp",
                   transform="avg(temperature_max)"))
    graph.add(edge("silver", "clean_weather", "temperature_min",
                   "gold", "weather_daily", "global_avg_min_temp",
                   transform="avg(temperature_min)"))
    graph.add(edge("silver", "clean_weather", "precipitation_mm",
                   "gold", "weather_daily", "total_precipitation",
                   transform="sum(precipitation_mm)"))
    graph.add(edge("silver", "clean_weather", "wind_speed_kmh",
                   "gold", "weather_daily", "avg_wind_speed",
                   transform="avg(wind_speed_kmh)"))

    return graph


def demo_lineage() -> None:
    graph = build_medallion_lineage()

    logger.info("=" * 68)
    logger.info("  DATA LINEAGE GRAPH — portfolio catalog")
    logger.info("  (Auto-captured by Unity Catalog in real Databricks)")
    logger.info("=" * 68)
    logger.info("Total lineage edges: %d", len(graph.edges))

    # ── Column-level lineage per table ────────────────────────────────────────
    logger.info("")
    logger.info(DIVIDER)
    logger.info("  COLUMN LINEAGE: bronze.raw_weather")
    logger.info(DIVIDER)
    graph.show_column_lineage("raw_weather")

    logger.info("")
    logger.info(DIVIDER)
    logger.info("  COLUMN LINEAGE: silver.clean_weather")
    logger.info(DIVIDER)
    graph.show_column_lineage("clean_weather")

    logger.info("")
    logger.info(DIVIDER)
    logger.info("  COLUMN LINEAGE: gold.weather_daily")
    logger.info(DIVIDER)
    graph.show_column_lineage("weather_daily")

    # ── Table-level dependency graph ──────────────────────────────────────────
    logger.info("")
    logger.info(DIVIDER)
    logger.info("  TABLE DEPENDENCY GRAPH")
    logger.info(DIVIDER)
    for table in ["raw_weather", "clean_weather", "weather_daily"]:
        up   = graph.upstream_tables(table)
        down = graph.downstream_tables(table)
        logger.info("  %-20s", table)
        logger.info("    ← upstream:   %s", ", ".join(up)   if up   else "(source)")
        logger.info("    → downstream: %s", ", ".join(down) if down else "(sink)")

    # ── Impact analysis ───────────────────────────────────────────────────────
    logger.info("")
    logger.info(DIVIDER)
    logger.info("  IMPACT ANALYSIS: if bronze.raw_weather.temperature_max changes")
    logger.info(DIVIDER)
    impacts = graph.impact_analysis("raw_weather", "temperature_max")
    for e in impacts:
        logger.info("  → %s.%s  [%s]", e.target_fqn, e.target_column, e.transform)

    # ── Real Databricks equivalent ────────────────────────────────────────────
    logger.info("")
    logger.info(DIVIDER)
    logger.info("  REAL DATABRICKS EQUIVALENT (system table queries)")
    logger.info(DIVIDER)
    logger.info("  -- Column lineage")
    logger.info("  SELECT source_table_name, source_column_name,")
    logger.info("         target_table_name, target_column_name, transform_type")
    logger.info("  FROM system.access.column_lineage")
    logger.info("  WHERE target_table_name = 'weather_daily'")
    logger.info("  ORDER BY target_column_name;")
    logger.info("")
    logger.info("  -- Find all tables that would break if we drop a column")
    logger.info("  SELECT DISTINCT target_table_full_name")
    logger.info("  FROM system.access.column_lineage")
    logger.info("  WHERE source_table_full_name = 'portfolio.bronze.raw_weather'")
    logger.info("    AND source_column_name     = 'temperature_max';")


if __name__ == "__main__":
    demo_lineage()
