#!/usr/bin/env bash
# MedInsight Analytics Platform - One-Shot Setup Script
set -euo pipefail

PYTHON=${PYTHON:-python3}
PIP=${PIP:-pip3}

echo "=============================================="
echo "  MedInsight Analytics Platform Setup"
echo "=============================================="

# Check Python version
PYTHON_VERSION=$($PYTHON --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON -m venv .venv
fi

source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

# Copy .env if not exists
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ".env created from .env.example — please review credentials"
fi

# Create directories
mkdir -p data/{raw,bronze,silver,gold,exports} logs

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your PostgreSQL credentials"
echo "  2. source .venv/bin/activate"
echo "  3. python scripts/run_pipeline.py --skip-dbt   (quick run)"
echo "  4. streamlit run dashboard/dashboard.py"
echo ""
