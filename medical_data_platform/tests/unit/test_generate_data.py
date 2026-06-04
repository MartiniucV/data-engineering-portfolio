"""
Unit tests for data generation module.
"""

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.settings import Settings
from scripts.generate_data import DataGenerator, _fake_cnp, _seasonal_weight


@pytest.fixture
def settings(tmp_path):
    s = Settings()
    s.data.raw_dir = tmp_path / "raw"
    s.data.bronze_dir = tmp_path / "bronze"
    s.data.silver_dir = tmp_path / "silver"
    s.data.gold_dir = tmp_path / "gold"
    s.data.exports_dir = tmp_path / "exports"
    s.data.ensure_dirs()
    return s


@pytest.fixture
def generator(settings):
    return DataGenerator(settings)


class TestFakeCnp:
    def test_cnp_length(self):
        cnp = _fake_cnp("M", date(1985, 6, 15))
        assert len(cnp) == 13

    def test_cnp_is_digits(self):
        cnp = _fake_cnp("F", date(1990, 3, 22))
        assert cnp.isdigit()


class TestSeasonalWeight:
    def test_summer_is_lower(self):
        aug = _seasonal_weight(date(2023, 8, 15))
        oct = _seasonal_weight(date(2023, 10, 15))
        assert aug < oct

    def test_spring_is_higher(self):
        april = _seasonal_weight(date(2023, 4, 10))
        dec = _seasonal_weight(date(2023, 12, 25))
        assert april > dec

    def test_all_months_positive(self):
        for month in range(1, 13):
            assert _seasonal_weight(date(2023, month, 1)) > 0


class TestGenerateClinics:
    def test_returns_dataframe(self, generator):
        df = generator.generate_clinics()
        assert isinstance(df, pd.DataFrame)

    def test_has_six_clinics(self, generator):
        df = generator.generate_clinics()
        assert len(df) == 6

    def test_required_columns(self, generator):
        df = generator.generate_clinics()
        for col in ["clinic_id", "name", "city", "capacity"]:
            assert col in df.columns

    def test_unique_clinic_ids(self, generator):
        df = generator.generate_clinics()
        assert df["clinic_id"].nunique() == len(df)


class TestGenerateDoctors:
    def test_returns_fifty_doctors(self, generator):
        clinics = generator.generate_clinics()
        specialties = generator.generate_specialties()
        doctors = generator.generate_doctors(clinics, specialties)
        assert len(doctors) == 50

    def test_all_specialties_covered(self, generator):
        clinics = generator.generate_clinics()
        specialties = generator.generate_specialties()
        doctors = generator.generate_doctors(clinics, specialties)
        from scripts.generate_data import SPECIALTIES
        for sp in SPECIALTIES:
            assert sp in doctors["specialty"].values

    def test_ratings_in_range(self, generator):
        clinics = generator.generate_clinics()
        specialties = generator.generate_specialties()
        doctors = generator.generate_doctors(clinics, specialties)
        assert doctors["rating"].between(1.0, 5.0).all()

    def test_clinic_ids_valid(self, generator):
        clinics = generator.generate_clinics()
        specialties = generator.generate_specialties()
        doctors = generator.generate_doctors(clinics, specialties)
        valid_clinics = set(clinics["clinic_id"])
        assert all(cid in valid_clinics for cid in doctors["clinic_id"])


class TestGeneratePatients:
    def test_returns_correct_count(self, generator):
        patients = generator.generate_patients()
        assert len(patients) == generator.settings.data.num_patients

    def test_ages_in_valid_range(self, generator):
        patients = generator.generate_patients()
        assert (patients["age"] >= 0).all()
        assert (patients["age"] <= 120).all()

    def test_gender_valid_values(self, generator):
        patients = generator.generate_patients()
        assert set(patients["gender"].unique()).issubset({"M", "F"})

    def test_cities_are_valid(self, generator):
        from scripts.generate_data import CITIES
        patients = generator.generate_patients()
        assert all(c in CITIES for c in patients["city"])


class TestGenerateAppointments:
    @pytest.fixture
    def base_data(self, generator):
        clinics = generator.generate_clinics()
        specialties = generator.generate_specialties()
        services = generator.generate_services()
        doctors = generator.generate_doctors(clinics, specialties)
        patients = generator.generate_patients()
        return clinics, specialties, services, doctors, patients

    def test_generates_appointments(self, generator, base_data):
        clinics, specialties, services, doctors, patients = base_data
        apts = generator.generate_appointments(patients, doctors, services, clinics)
        assert len(apts) > 0

    def test_status_valid_values(self, generator, base_data):
        clinics, specialties, services, doctors, patients = base_data
        apts = generator.generate_appointments(patients, doctors, services, clinics)
        valid = {"completed", "cancelled", "no_show", "rescheduled"}
        assert set(apts["status"].unique()).issubset(valid)

    def test_completed_have_price(self, generator, base_data):
        clinics, specialties, services, doctors, patients = base_data
        apts = generator.generate_appointments(patients, doctors, services, clinics)
        completed = apts[apts["status"] == "completed"]
        assert (completed["actual_price"] >= 0).all()
