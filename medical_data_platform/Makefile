.PHONY: all setup generate load transform dbt-run quality test dashboard clean help

PYTHON := python3
PIP := pip3
DBT := dbt
STREAMLIT := streamlit

## help: Show this help message
help:
	@echo "MedInsight Analytics Platform - Makefile Commands"
	@echo "=================================================="
	@grep -E '^## ' Makefile | sed 's/## /  /'

## all: Run the complete pipeline end-to-end
all: setup generate load transform dbt-run quality test

## setup: Create virtual environment and install dependencies
setup:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	cp -n .env.example .env || true
	@echo "Setup complete. Activate venv: source .venv/bin/activate"

## docker-up: Start PostgreSQL via Docker Compose
docker-up:
	docker-compose up -d postgres
	@echo "Waiting for PostgreSQL to be ready..."
	sleep 5

## docker-down: Stop all Docker services
docker-down:
	docker-compose down

## generate: Generate all synthetic healthcare datasets
generate:
	$(PYTHON) scripts/generate_data.py

## load: Load raw datasets into PostgreSQL
load:
	$(PYTHON) scripts/load_postgres.py

## seed: Seed reference tables
seed:
	$(PYTHON) scripts/seed_reference_tables.py

## transform: Run silver-layer transformations
transform:
	$(PYTHON) scripts/transform_data.py

## dbt-deps: Install dbt dependencies
dbt-deps:
	cd dbt && $(DBT) deps

## dbt-run: Run all dbt models
dbt-run:
	cd dbt && $(DBT) run --profiles-dir .

## dbt-test: Run dbt tests
dbt-test:
	cd dbt && $(DBT) test --profiles-dir .

## dbt-docs: Generate and serve dbt docs
dbt-docs:
	cd dbt && $(DBT) docs generate --profiles-dir . && $(DBT) docs serve --profiles-dir .

## quality: Run data quality checks
quality:
	$(PYTHON) scripts/quality_checks.py

## forecast: Run forecasting models
forecast:
	$(PYTHON) scripts/forecasting.py

## test: Run pytest suite
test:
	$(PYTHON) -m pytest tests/ -v --cov=scripts --cov-report=term-missing

## dashboard: Launch Streamlit dashboard
dashboard:
	$(STREAMLIT) run dashboard/dashboard.py --server.port 8501

## pipeline: Run full pipeline (generate -> load -> dbt -> quality)
pipeline:
	$(PYTHON) scripts/run_pipeline.py

## clean: Remove generated data files and logs
clean:
	find data/raw -name "*.csv" -delete
	find data/bronze -name "*.parquet" -delete
	find data/silver -name "*.parquet" -delete
	find data/gold -name "*.parquet" -delete
	find logs -name "*.log" -delete
	@echo "Cleaned generated artifacts"

## lint: Run code quality checks
lint:
	ruff check scripts/ dashboard/ config/ tests/
	black --check scripts/ dashboard/ config/ tests/

## format: Auto-format code
format:
	black scripts/ dashboard/ config/ tests/
	ruff check --fix scripts/ dashboard/ config/ tests/
