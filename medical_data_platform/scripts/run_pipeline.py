"""
MedInsight Analytics Platform - Pipeline Orchestrator
Runs the full data pipeline: generate -> load -> transform -> dbt -> quality.
"""

import subprocess
import sys
import time
from pathlib import Path

from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import Settings
from scripts.generate_data import DataGenerator
from scripts.load_postgres import PostgresLoader
from scripts.transform_data import SilverTransformer
from scripts.quality_checks import DataQualityChecker

console = Console()


class Pipeline:
    """Orchestrates the end-to-end MedInsight data pipeline."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.steps: list[tuple[str, callable]] = []
        self._register_steps()

    def _register_steps(self) -> None:
        self.steps = [
            ("Generate Synthetic Data", self._run_generate),
            ("Load Raw -> PostgreSQL", self._run_load),
            ("Transform Bronze -> Silver", self._run_transform),
            ("Run dbt Models", self._run_dbt),
            ("Data Quality Checks", self._run_quality),
        ]

    def _run_generate(self) -> None:
        gen = DataGenerator(self.settings)
        gen.run()

    def _run_load(self) -> None:
        loader = PostgresLoader(self.settings)
        loader.run()

    def _run_transform(self) -> None:
        transformer = SilverTransformer(self.settings)
        transformer.run()

    def _run_dbt(self) -> None:
        dbt_dir = self.settings.base_dir / "dbt"
        if not dbt_dir.exists():
            logger.warning("dbt directory not found — skipping dbt run")
            return

        # Write profiles.yml at runtime
        profiles_content = f"""
medinsight:
  target: dev
  outputs:
    dev:
      type: postgres
      host: {self.settings.db.host}
      port: {self.settings.db.port}
      user: {self.settings.db.user}
      password: {self.settings.db.password}
      dbname: {self.settings.db.name}
      schema: staging
      threads: 4
      keepalives_idle: 0
      connect_timeout: 10
"""
        profiles_path = dbt_dir / "profiles.yml"
        profiles_path.write_text(profiles_content)

        commands = [
            (["dbt", "deps"], "Installing dbt packages"),
            (["dbt", "run", "--profiles-dir", "."], "Running dbt models"),
            (["dbt", "test", "--profiles-dir", "."], "Running dbt tests"),
        ]
        for cmd, label in commands:
            logger.info(f"dbt: {label}")
            result = subprocess.run(cmd, cwd=dbt_dir, capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning(f"dbt command failed: {result.stderr[:500]}")
            else:
                logger.info(f"dbt OK: {label}")

    def _run_quality(self) -> None:
        checker = DataQualityChecker(self.settings)
        report = checker.run()
        logger.info(
            f"Quality: {report.passed} passed, {report.warnings} warnings, {report.failed} failed"
        )

    def run(self, skip_dbt: bool = False) -> None:
        console.print(Panel.fit(
            "[bold cyan]MedInsight Analytics Platform[/bold cyan]\n"
            "[dim]Enterprise Healthcare Data Pipeline[/dim]",
            border_style="cyan",
        ))

        start = time.time()
        errors = []

        for name, fn in self.steps:
            if skip_dbt and name == "Run dbt Models":
                logger.info(f"Skipping: {name}")
                continue

            console.print(f"\n[bold yellow]▶ {name}[/bold yellow]")
            step_start = time.time()
            try:
                fn()
                elapsed = time.time() - step_start
                console.print(f"  [green]✓ {name}[/green] ({elapsed:.1f}s)")
            except Exception as exc:
                elapsed = time.time() - step_start
                logger.error(f"Step failed: {name} | {exc}")
                console.print(f"  [red]✗ {name} FAILED: {exc}[/red] ({elapsed:.1f}s)")
                errors.append((name, str(exc)))

        total = time.time() - start
        console.print(Panel(
            f"Pipeline complete in [bold]{total:.1f}s[/bold]\n"
            f"[green]Steps: {len(self.steps) - len(errors)}/{len(self.steps)} succeeded[/green]"
            + (f"\n[red]Errors: {len(errors)}[/red]" if errors else ""),
            border_style="green" if not errors else "red",
        ))

        if errors:
            for name, msg in errors:
                logger.error(f"Failed step: {name} — {msg}")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="MedInsight Pipeline Orchestrator")
    parser.add_argument("--skip-dbt", action="store_true", help="Skip dbt models")
    args = parser.parse_args()

    settings = Settings()
    pipeline = Pipeline(settings)
    pipeline.run(skip_dbt=args.skip_dbt)


if __name__ == "__main__":
    main()
