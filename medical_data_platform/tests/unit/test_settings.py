"""
Unit tests for configuration settings.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.settings import Settings, DatabaseSettings, DataSettings


class TestDatabaseSettings:
    def test_url_format(self):
        db = DatabaseSettings()
        assert db.url.startswith("postgresql://")
        assert db.host in db.url
        assert db.name in db.url

    def test_defaults(self):
        db = DatabaseSettings()
        assert db.host == "localhost"
        assert db.port == 5432


class TestDataSettings:
    def test_default_counts(self):
        d = DataSettings()
        assert d.num_doctors == 50
        assert d.num_patients == 5000
        assert d.num_appointments == 20000

    def test_dirs_are_paths(self):
        d = DataSettings()
        assert isinstance(d.raw_dir, Path)
        assert isinstance(d.bronze_dir, Path)


class TestSettings:
    def test_instantiation(self):
        s = Settings()
        assert s.db is not None
        assert s.data is not None
        assert s.app is not None

    def test_repr(self):
        s = Settings()
        r = repr(s)
        assert "Settings" in r
        assert "localhost" in r
