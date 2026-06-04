"""
MedInsight Analytics Platform - Synthetic Data Generator
Generates realistic Romanian healthcare data for 50 doctors, 5,000 patients,
and 20,000 appointments spanning 2023–2024.
"""

import hashlib
import random
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from faker import Faker
from loguru import logger
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import Settings

fake = Faker("ro_RO")
Faker.seed(42)
np.random.seed(42)
random.seed(42)

console = Console()

# ── Romanian reference data ─────────────────────────────────────────────────

MALE_NAMES = [
    "Andrei", "Alexandru", "Mihai", "Cristian", "Ioan", "Bogdan", "Radu",
    "Vlad", "Ștefan", "Daniel", "Marian", "Florin", "Cătălin", "Gabriel",
    "Ionuț", "Robert", "Victor", "Adrian", "Lucian", "George", "Claudiu",
    "Dragoș", "Valentin", "Cosmin", "Silviu", "Mădălin", "Ovidiu", "Sorin",
    "Relu", "Dinu", "Nicu", "Grigore", "Tiberiu", "Dorian", "Cristi",
]

FEMALE_NAMES = [
    "Maria", "Ana", "Elena", "Ioana", "Andreea", "Cristina", "Mihaela",
    "Alina", "Roxana", "Diana", "Laura", "Larisa", "Teodora", "Alexandra",
    "Simona", "Raluca", "Mădălina", "Gabriela", "Luminița", "Camelia",
    "Denisa", "Oana", "Loredana", "Florentina", "Valentina", "Beatrice",
    "Claudia", "Nicoleta", "Adriana", "Ramona", "Iuliana", "Carmen",
]

LAST_NAMES = [
    "Popescu", "Ionescu", "Popa", "Stan", "Gheorghiu", "Stoica", "Constantin",
    "Florea", "Matei", "Marin", "Dima", "Dumitru", "Moldovan", "Rădulescu",
    "Dragomir", "Șerban", "Grigorescu", "Niculescu", "Dobre", "Mihai",
    "Cristea", "Oprea", "Petrescu", "Andrei", "Tudor", "Manea", "Preda",
    "Mocanu", "Lazăr", "Nistor", "Toma", "Vlad", "Lungu", "Sava", "Ciobanu",
    "Ungureanu", "Marinescu", "Olaru", "Coman", "Iordache", "Barbu",
    "Dumitrescu", "Enache", "Filip", "Ghiță", "Chirilă", "Mureșan",
    "Ardelean", "Văduva", "Roșu",
]

CITIES = ["Cluj-Napoca", "București", "Timișoara", "Iași", "Brașov", "Constanța"]

CITY_TO_COUNTY = {
    "Cluj-Napoca": "Cluj",
    "București": "Ilfov",
    "Timișoara": "Timiș",
    "Iași": "Iași",
    "Brașov": "Brașov",
    "Constanța": "Constanța",
}

SPECIALTIES = [
    "Cardiologie", "Pediatrie", "Ortopedie", "Neurologie", "Dermatologie",
    "Oftalmologie", "Ginecologie", "Psihiatrie", "Oncologie", "Medicina Interna",
]

SPECIALTY_PRICE = {
    "Cardiologie": (250, 350), "Pediatrie": (180, 250), "Ortopedie": (230, 320),
    "Neurologie": (270, 380), "Dermatologie": (180, 280), "Oftalmologie": (180, 260),
    "Ginecologie": (220, 300), "Psihiatrie": (280, 380), "Oncologie": (350, 500),
    "Medicina Interna": (210, 300),
}

BLOOD_TYPES = ["O+", "A+", "B+", "AB+", "O-", "A-", "B-", "AB-"]
BLOOD_TYPE_WEIGHTS = [0.37, 0.36, 0.09, 0.03, 0.06, 0.06, 0.02, 0.01]

CHRONIC_CONDITIONS = [
    "Hipertensiune arteriala", "Diabet zaharat tip 2", "Astm bronsic",
    "Boala coronariana", "Obezitate", "Hipotiroidism", "Depresie",
    "Anxietate", "Artroza", "Cardiopatie ischemica", "Reflux gastroesofagian",
    "Migrena cronica", "Apnee in somn", "Insuficienta renala cronica",
]

INSURANCE_TYPES = ["CNAS", "Private", "Neasigurat"]
INSURANCE_WEIGHTS = [0.55, 0.35, 0.10]

APPOINTMENT_CHANNELS = ["Online", "Telefon", "Fizic", "Aplicatie mobila", "Referinta medic"]
CHANNEL_WEIGHTS = [0.35, 0.30, 0.15, 0.15, 0.05]

URGENCY_LEVELS = ["Electiv", "Urgent", "Semigur"]
URGENCY_WEIGHTS = [0.70, 0.20, 0.10]

REFERRAL_SOURCES = [
    "Medic de familie", "Auto-referire", "Recomandare pacient",
    "Publicitate online", "Campanie medicala", "Specialist intern",
]

APPOINTMENT_STATUSES = ["completed", "cancelled", "no_show", "rescheduled"]
STATUS_WEIGHTS = [0.72, 0.14, 0.09, 0.05]

CANCELLATION_REASONS = [
    "Conflict program", "Motiv personal", "Transport indisponibil",
    "Alta clinica", "Imbunatatire stare sanatate", "Cost prea ridicat",
    "Lipsa comunicare", "Asteptare prea lunga",
]

PAYMENT_METHODS = ["Card", "Numerar", "Transfer bancar", "Asigurare privata", "CNAS"]
PAYMENT_WEIGHTS = [0.45, 0.20, 0.10, 0.17, 0.08]

MEDICATIONS = [
    "Metformin 500mg", "Lisinopril 10mg", "Atorvastatin 20mg", "Omeprazol 20mg",
    "Amlodipina 5mg", "Bisoprolol 5mg", "Levotiroxina 50mcg", "Aspirina 75mg",
    "Paracetamol 500mg", "Ibuprofen 400mg", "Amoxicilina 500mg", "Azitromicina 500mg",
    "Metoprolol 25mg", "Furosemid 40mg", "Spironolactona 25mg", "Ramipril 5mg",
    "Clopidogrel 75mg", "Warfarina 5mg", "Insulina NPH", "Prednison 5mg",
    "Pantoprazol 40mg", "Escitalopram 10mg", "Sertralin 50mg", "Alprazolam 0.5mg",
    "Lorazepam 1mg", "Quetiapina 25mg", "Paracetamol 1g", "Tramadol 50mg",
]

LAB_TESTS = [
    {"name": "Hemoglobina", "unit": "g/dL", "normal_range": (12.0, 17.5), "std": 1.5},
    {"name": "Leucocite", "unit": "10^3/uL", "normal_range": (4.5, 11.0), "std": 2.0},
    {"name": "Trombocite", "unit": "10^3/uL", "normal_range": (150.0, 400.0), "std": 50.0},
    {"name": "Glicemie a jeun", "unit": "mg/dL", "normal_range": (70.0, 100.0), "std": 15.0},
    {"name": "Colesterol total", "unit": "mg/dL", "normal_range": (0.0, 200.0), "std": 40.0},
    {"name": "LDL Colesterol", "unit": "mg/dL", "normal_range": (0.0, 130.0), "std": 30.0},
    {"name": "HDL Colesterol", "unit": "mg/dL", "normal_range": (40.0, 60.0), "std": 10.0},
    {"name": "Trigliceride", "unit": "mg/dL", "normal_range": (0.0, 150.0), "std": 40.0},
    {"name": "Creatinina", "unit": "mg/dL", "normal_range": (0.7, 1.2), "std": 0.2},
    {"name": "Uree", "unit": "mg/dL", "normal_range": (15.0, 45.0), "std": 8.0},
    {"name": "ALT", "unit": "U/L", "normal_range": (0.0, 40.0), "std": 15.0},
    {"name": "AST", "unit": "U/L", "normal_range": (0.0, 40.0), "std": 12.0},
    {"name": "TSH", "unit": "mIU/L", "normal_range": (0.4, 4.0), "std": 1.0},
    {"name": "INR", "unit": "-", "normal_range": (0.8, 1.2), "std": 0.2},
    {"name": "Vitamina D", "unit": "ng/mL", "normal_range": (30.0, 100.0), "std": 20.0},
]

SERVICES_DEF = [
    {"code": "CONS", "name": "Consultatie medicala", "category": "consultatie",
     "price_range": (150, 450), "duration": 30, "margin": 0.70, "reimbursement": 0.30},
    {"code": "ECO", "name": "Ecografie abdominala", "category": "imagistica",
     "price_range": (150, 350), "duration": 30, "margin": 0.55, "reimbursement": 0.25},
    {"code": "RMN", "name": "Rezonanta Magnetica Nucleara", "category": "imagistica",
     "price_range": (600, 1200), "duration": 60, "margin": 0.45, "reimbursement": 0.20},
    {"code": "CT", "name": "Computer Tomograf", "category": "imagistica",
     "price_range": (400, 900), "duration": 45, "margin": 0.50, "reimbursement": 0.20},
    {"code": "RX", "name": "Radiografie", "category": "imagistica",
     "price_range": (80, 200), "duration": 15, "margin": 0.60, "reimbursement": 0.30},
    {"code": "ALAB", "name": "Analize de laborator", "category": "laborator",
     "price_range": (50, 500), "duration": 15, "margin": 0.65, "reimbursement": 0.40},
    {"code": "CHIR", "name": "Interventie chirurgicala mica", "category": "interventie",
     "price_range": (500, 2500), "duration": 90, "margin": 0.40, "reimbursement": 0.15},
    {"code": "PSIH", "name": "Sedinta psihoterapie", "category": "terapie",
     "price_range": (150, 350), "duration": 50, "margin": 0.80, "reimbursement": 0.10},
    {"code": "CTRL", "name": "Control periodic", "category": "preventie",
     "price_range": (100, 300), "duration": 30, "margin": 0.72, "reimbursement": 0.35},
    {"code": "VACC", "name": "Vaccinare", "category": "preventie",
     "price_range": (80, 350), "duration": 15, "margin": 0.60, "reimbursement": 0.45},
    {"code": "FIZIO", "name": "Sedinta fizioterapie", "category": "recuperare",
     "price_range": (100, 250), "duration": 45, "margin": 0.65, "reimbursement": 0.25},
    {"code": "ENDO", "name": "Endoscopie digestiva", "category": "investigatie",
     "price_range": (400, 800), "duration": 45, "margin": 0.48, "reimbursement": 0.20},
    {"code": "ECO_CARD", "name": "Ecocardiografie", "category": "imagistica",
     "price_range": (250, 500), "duration": 40, "margin": 0.55, "reimbursement": 0.25},
    {"code": "EEG", "name": "Electroencefalograma", "category": "investigatie",
     "price_range": (200, 400), "duration": 60, "margin": 0.55, "reimbursement": 0.20},
    {"code": "EMG", "name": "Electromiografie", "category": "investigatie",
     "price_range": (250, 500), "duration": 60, "margin": 0.50, "reimbursement": 0.15},
    {"code": "COLO", "name": "Colonoscopie", "category": "investigatie",
     "price_range": (600, 1000), "duration": 60, "margin": 0.45, "reimbursement": 0.20},
]


def _fake_cnp(gender: str, birth_date: date) -> str:
    """Generate a plausible (non-real) Romanian CNP."""
    year_2digit = birth_date.strftime("%y")
    month = birth_date.strftime("%m")
    day = birth_date.strftime("%d")
    sex_digit = "1" if gender == "M" else "2"
    county_code = str(random.randint(1, 46)).zfill(2)
    seq = str(random.randint(1, 999)).zfill(3)
    partial = f"{sex_digit}{year_2digit}{month}{day}{county_code}{seq}"
    checksum = str(random.randint(0, 9))
    return partial + checksum


def _seasonal_weight(dt: date) -> float:
    """Higher appointment volume in spring/autumn, lower in summer/winter holidays."""
    month = dt.month
    weights = {1: 0.7, 2: 0.85, 3: 1.1, 4: 1.2, 5: 1.15, 6: 1.0,
               7: 0.80, 8: 0.65, 9: 1.15, 10: 1.25, 11: 1.1, 12: 0.75}
    return weights.get(month, 1.0)


class DataGenerator:
    """Generates all synthetic data tables for the MedInsight platform."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cfg = self._load_config()
        settings.data.ensure_dirs()

    def _load_config(self) -> dict[str, Any]:
        config_path = self.settings.base_dir / "config" / "config.yaml"
        with open(config_path) as f:
            return yaml.safe_load(f)

    # ── Clinics ──────────────────────────────────────────────────────────────

    def generate_clinics(self) -> pd.DataFrame:
        rows = []
        for c in self.cfg["clinics"]:
            rows.append({
                "clinic_id": c["id"],
                "name": c["name"],
                "city": c["city"],
                "county": c["county"],
                "address": c["address"],
                "phone": c["phone"],
                "capacity": c["capacity"],
                "opening_date": fake.date_between(start_date=date(2010, 1, 1), end_date=date(2020, 12, 31)),
                "is_active": True,
            })
        return pd.DataFrame(rows)

    # ── Specialties ──────────────────────────────────────────────────────────

    def generate_specialties(self) -> pd.DataFrame:
        rows = []
        for sp in self.cfg["specialties"]:
            rows.append({
                "specialty_id": sp["id"],
                "name": sp["name"],
                "avg_consultation_price": sp["avg_consultation_price"],
                "avg_duration_min": sp["avg_duration_min"],
            })
        return pd.DataFrame(rows)

    # ── Services ─────────────────────────────────────────────────────────────

    def generate_services(self) -> pd.DataFrame:
        rows = []
        for i, svc in enumerate(SERVICES_DEF, start=1):
            price = random.randint(*svc["price_range"])
            rows.append({
                "service_id": f"SVC{i:03d}",
                "code": svc["code"],
                "name": svc["name"],
                "category": svc["category"],
                "base_price": price,
                "duration_minutes": svc["duration"],
                "profitability_margin": svc["margin"],
                "reimbursement_pct": svc["reimbursement"],
                "is_active": True,
            })
        return pd.DataFrame(rows)

    # ── Doctors ──────────────────────────────────────────────────────────────

    def generate_doctors(
        self, clinics: pd.DataFrame, specialties: pd.DataFrame
    ) -> pd.DataFrame:
        rows = []
        clinic_ids = clinics["clinic_id"].tolist()
        # Distribute 50 doctors: ~5 per specialty
        for i in range(1, self.settings.data.num_doctors + 1):
            specialty_name = SPECIALTIES[(i - 1) % len(SPECIALTIES)]
            gender = random.choice(["M", "F"])
            first_name = random.choice(MALE_NAMES if gender == "M" else FEMALE_NAMES)
            last_name = random.choice(LAST_NAMES)
            yoe = random.randint(3, 30)
            rating = round(np.clip(np.random.normal(4.3, 0.4), 3.0, 5.0), 1)
            cons_lo, cons_hi = SPECIALTY_PRICE[specialty_name]
            cons_price = random.randint(cons_lo, cons_hi)
            hire_date = fake.date_between(start_date=date(2010, 1, 1), end_date=date(2023, 6, 30))
            clinic_id = random.choice(clinic_ids)

            rows.append({
                "doctor_id": f"DOC{i:03d}",
                "first_name": first_name,
                "last_name": last_name,
                "full_name": f"Dr. {last_name} {first_name}",
                "gender": gender,
                "specialty": specialty_name,
                "clinic_id": clinic_id,
                "years_experience": yoe,
                "hire_date": hire_date,
                "consultation_price": cons_price,
                "rating": rating,
                "monthly_salary": round(random.uniform(8000, 25000), 2),
                "performance_score": round(np.clip(np.random.normal(78, 12), 40, 100), 1),
                "is_active": True,
                "email": f"{first_name.lower().replace('ș','s').replace('ț','t').replace('â','a').replace('î','i').replace('ă','a')}.{last_name.lower().replace('ș','s').replace('ț','t').replace('â','a').replace('î','i').replace('ă','a')}@medinsight.ro",
                "phone": fake.phone_number(),
            })
        return pd.DataFrame(rows)

    # ── Patients ─────────────────────────────────────────────────────────────

    def generate_patients(self) -> pd.DataFrame:
        rows = []
        city_weights = [0.20, 0.35, 0.15, 0.12, 0.10, 0.08]

        for i in range(1, self.settings.data.num_patients + 1):
            gender = random.choice(["M", "F"])
            first_name = random.choice(MALE_NAMES if gender == "M" else FEMALE_NAMES)
            last_name = random.choice(LAST_NAMES)
            age = int(np.clip(np.random.normal(45, 18), 1, 90))
            birth_date = date.today() - timedelta(days=age * 365 + random.randint(0, 364))
            city = random.choices(CITIES, weights=city_weights, k=1)[0]
            blood_type = random.choices(BLOOD_TYPES, weights=BLOOD_TYPE_WEIGHTS, k=1)[0]
            insurance = random.choices(INSURANCE_TYPES, weights=INSURANCE_WEIGHTS, k=1)[0]

            num_conditions = random.choices([0, 1, 2, 3], weights=[0.50, 0.30, 0.15, 0.05])[0]
            conditions = (
                "; ".join(random.sample(CHRONIC_CONDITIONS, num_conditions))
                if num_conditions > 0
                else None
            )

            reg_date = fake.date_between(start_date=date(2020, 1, 1), end_date=date(2023, 12, 31))

            first_clean = first_name.lower().translate(str.maketrans("șțâîă", "staia"))
            last_clean = last_name.lower().translate(str.maketrans("șțâîă", "staia"))

            rows.append({
                "patient_id": f"PAT{i:05d}",
                "cnp": _fake_cnp(gender, birth_date),
                "first_name": first_name,
                "last_name": last_name,
                "full_name": f"{last_name} {first_name}",
                "gender": gender,
                "birth_date": birth_date,
                "age": age,
                "blood_type": blood_type,
                "city": city,
                "county": CITY_TO_COUNTY[city],
                "email": f"{first_clean}.{last_clean}{random.randint(1,99)}@{random.choice(['gmail.com','yahoo.com','hotmail.com'])}",
                "phone": fake.phone_number(),
                "insurance_status": insurance,
                "chronic_conditions": conditions,
                "risk_score": round(np.clip(np.random.exponential(scale=25), 0, 100), 1),
                "registration_date": reg_date,
                "is_active": True,
            })
        return pd.DataFrame(rows)

    # ── Appointments ─────────────────────────────────────────────────────────

    def generate_appointments(
        self,
        patients: pd.DataFrame,
        doctors: pd.DataFrame,
        services: pd.DataFrame,
        clinics: pd.DataFrame,
    ) -> pd.DataFrame:
        start_dt = datetime(2023, 1, 2)
        end_dt = datetime(2024, 12, 31, 18, 0)
        all_days = []
        current = start_dt.date()
        while current <= end_dt.date():
            if current.weekday() < 5 or (current.weekday() == 5 and random.random() < 0.6):
                all_days.append(current)
            current += timedelta(days=1)

        patient_ids = patients["patient_id"].tolist()
        doctor_ids = doctors["doctor_id"].tolist()
        doctor_clinic = dict(zip(doctors["doctor_id"], doctors["clinic_id"]))
        doctor_specialty = dict(zip(doctors["doctor_id"], doctors["specialty"]))
        service_ids = services["service_id"].tolist()
        service_prices = dict(zip(services["service_id"], services["base_price"]))
        service_durations = dict(zip(services["service_id"], services["duration_minutes"]))

        # Give heavier patients more appointments (realistic)
        patient_visit_weights = np.random.exponential(scale=1.0, size=len(patient_ids)) + 0.1
        patient_visit_weights /= patient_visit_weights.sum()

        rows = []
        appt_num = 0
        target = self.settings.data.num_appointments

        for appt_day in all_days:
            if appt_num >= target:
                break
            day_load = int(target / len(all_days) * _seasonal_weight(appt_day) * random.uniform(0.7, 1.3))
            day_load = max(1, min(day_load, 120))

            for _ in range(day_load):
                if appt_num >= target:
                    break

                patient_id = random.choices(patient_ids, weights=patient_visit_weights, k=1)[0]
                doctor_id = random.choice(doctor_ids)
                service_id = random.choice(service_ids)
                clinic_id = doctor_clinic[doctor_id]

                hour = random.choices(
                    range(8, 18),
                    weights=[0.08, 0.12, 0.13, 0.12, 0.10, 0.08, 0.10, 0.10, 0.10, 0.07],
                    k=1,
                )[0]
                minute = random.choice([0, 15, 30, 45])
                scheduled_at = datetime(appt_day.year, appt_day.month, appt_day.day, hour, minute)

                status = random.choices(APPOINTMENT_STATUSES, weights=STATUS_WEIGHTS, k=1)[0]
                duration = service_durations[service_id] + random.randint(-5, 15)
                wait_time = int(np.clip(np.random.exponential(scale=12), 0, 90)) if status == "completed" else None
                actual_start = scheduled_at + timedelta(minutes=(wait_time or 0)) if status == "completed" else None
                actual_end = actual_start + timedelta(minutes=max(duration, 5)) if actual_start else None

                base_price = service_prices[service_id]
                discount = random.choices([0, 0.05, 0.10, 0.15], weights=[0.65, 0.15, 0.12, 0.08])[0]
                actual_price = round(base_price * (1 - discount), 2) if status == "completed" else 0

                rating = None
                if status == "completed" and random.random() < 0.65:
                    rating = round(np.clip(np.random.normal(4.3, 0.6), 1.0, 5.0), 1)

                cancel_reason = None
                if status in ("cancelled", "rescheduled"):
                    cancel_reason = random.choice(CANCELLATION_REASONS)

                rows.append({
                    "appointment_id": f"APT{appt_num + 1:06d}",
                    "patient_id": patient_id,
                    "doctor_id": doctor_id,
                    "service_id": service_id,
                    "clinic_id": clinic_id,
                    "specialty": doctor_specialty[doctor_id],
                    "scheduled_at": scheduled_at,
                    "actual_start": actual_start,
                    "actual_end": actual_end,
                    "status": status,
                    "waiting_time_minutes": wait_time,
                    "consultation_duration_minutes": duration if status == "completed" else None,
                    "channel": random.choices(APPOINTMENT_CHANNELS, weights=CHANNEL_WEIGHTS, k=1)[0],
                    "urgency_level": random.choices(URGENCY_LEVELS, weights=URGENCY_WEIGHTS, k=1)[0],
                    "referral_source": random.choices(REFERRAL_SOURCES, k=1)[0],
                    "cancellation_reason": cancel_reason,
                    "actual_price": actual_price,
                    "discount_pct": discount,
                    "rating": rating,
                    "notes": fake.sentence(nb_words=6) if random.random() < 0.20 else None,
                })
                appt_num += 1

        return pd.DataFrame(rows)

    # ── Billing ──────────────────────────────────────────────────────────────

    def generate_billing(
        self, appointments: pd.DataFrame, services: pd.DataFrame
    ) -> pd.DataFrame:
        service_reimbursement = dict(
            zip(services["service_id"], services["reimbursement_pct"])
        )
        completed = appointments[appointments["status"] == "completed"].copy()
        rows = []
        for idx, row in completed.iterrows():
            reimbursement_rate = service_reimbursement.get(row["service_id"], 0.20)
            insurance_status = random.choices(INSURANCE_TYPES, weights=INSURANCE_WEIGHTS)[0]

            gross = float(row["actual_price"])
            insurance_reimb = round(gross * reimbursement_rate, 2) if insurance_status != "Neasigurat" else 0.0
            patient_pays = round(gross - insurance_reimb, 2)
            tax = round(patient_pays * 0.19, 2)  # Romanian VAT for medical services (some exempt)
            refund = round(gross * 0.05, 2) if random.random() < 0.03 else 0.0
            payment_method = random.choices(PAYMENT_METHODS, weights=PAYMENT_WEIGHTS, k=1)[0]
            payment_status = random.choices(
                ["paid", "pending", "partial", "refunded"],
                weights=[0.88, 0.05, 0.04, 0.03],
            )[0]

            invoice_date = row["actual_end"].date() if pd.notna(row["actual_end"]) else row["scheduled_at"].date()

            rows.append({
                "billing_id": f"BILL{idx + 1:07d}",
                "appointment_id": row["appointment_id"],
                "patient_id": row["patient_id"],
                "invoice_date": invoice_date,
                "service_price": gross,
                "discount_amount": round(gross * float(row["discount_pct"]), 2),
                "insurance_reimbursement": insurance_reimb,
                "patient_paid": patient_pays,
                "tax_amount": tax,
                "total_amount": patient_pays,
                "refund_amount": refund,
                "payment_method": payment_method,
                "payment_status": payment_status,
                "insurance_type": insurance_status,
            })
        return pd.DataFrame(rows)

    # ── Prescriptions ────────────────────────────────────────────────────────

    def generate_prescriptions(
        self, appointments: pd.DataFrame, doctors: pd.DataFrame
    ) -> pd.DataFrame:
        completed = appointments[appointments["status"] == "completed"].copy()
        # ~40% of completed appointments result in a prescription
        mask = np.random.random(len(completed)) < 0.40
        subset = completed[mask].copy()
        rows = []
        for i, (_, row) in enumerate(subset.iterrows()):
            num_meds = random.choices([1, 2, 3], weights=[0.60, 0.30, 0.10])[0]
            meds = random.sample(MEDICATIONS, num_meds)
            for med in meds:
                rows.append({
                    "prescription_id": f"RX{len(rows) + 1:07d}",
                    "appointment_id": row["appointment_id"],
                    "doctor_id": row["doctor_id"],
                    "patient_id": row["patient_id"],
                    "medication_name": med,
                    "dosage": med.split(" ")[-1] if " " in med else "1cp",
                    "frequency": random.choice(["1x/zi", "2x/zi", "3x/zi", "la nevoie"]),
                    "duration_days": random.choice([5, 7, 10, 14, 21, 30, 60, 90]),
                    "prescribed_at": row["scheduled_at"],
                    "is_chronic": random.random() < 0.25,
                })
        return pd.DataFrame(rows)

    # ── Lab Results ──────────────────────────────────────────────────────────

    def generate_lab_results(self, appointments: pd.DataFrame) -> pd.DataFrame:
        lab_apts = appointments[
            (appointments["status"] == "completed") &
            (appointments["service_id"].isin(["SVC006"]) | (np.random.random(len(appointments)) < 0.20))
        ].copy()

        rows = []
        for _, row in lab_apts.iterrows():
            num_tests = random.randint(2, 6)
            tests = random.sample(LAB_TESTS, min(num_tests, len(LAB_TESTS)))
            collected_at = row["actual_start"] if pd.notna(row["actual_start"]) else row["scheduled_at"]
            result_at = collected_at + timedelta(hours=random.randint(1, 48))

            for test in tests:
                lo, hi = test["normal_range"]
                center = (lo + hi) / 2
                # ~15% abnormal
                if random.random() < 0.15:
                    if random.random() < 0.5:
                        value = round(random.uniform(lo * 0.5, lo * 0.95), 2)
                        is_abnormal = True
                    else:
                        value = round(random.uniform(hi * 1.05, hi * 1.5), 2)
                        is_abnormal = True
                else:
                    value = round(np.clip(np.random.normal(center, test["std"]), lo, hi), 2)
                    is_abnormal = False

                rows.append({
                    "lab_result_id": f"LAB{len(rows) + 1:08d}",
                    "appointment_id": row["appointment_id"],
                    "patient_id": row["patient_id"],
                    "test_name": test["name"],
                    "value": value,
                    "unit": test["unit"],
                    "reference_range_low": lo,
                    "reference_range_high": hi,
                    "is_abnormal": is_abnormal,
                    "collected_at": collected_at,
                    "result_at": result_at,
                })
        return pd.DataFrame(rows)

    # ── Persistence ──────────────────────────────────────────────────────────

    def _save_csv(self, df: pd.DataFrame, name: str) -> Path:
        path = self.settings.data.raw_dir / f"{name}.csv"
        df.to_csv(path, index=False)
        logger.info(f"Saved CSV: {path} ({len(df):,} rows)")
        return path

    def _save_parquet(self, df: pd.DataFrame, name: str) -> Path:
        path = self.settings.data.bronze_dir / f"{name}.parquet"
        table = pa.Table.from_pandas(df)
        pq.write_table(table, path, compression="snappy")
        logger.info(f"Saved Parquet: {path} ({len(df):,} rows)")
        return path

    def _save(self, df: pd.DataFrame, name: str) -> None:
        self._save_csv(df, name)
        self._save_parquet(df, name)

    # ── Main ─────────────────────────────────────────────────────────────────

    def run(self) -> dict[str, pd.DataFrame]:
        logger.info("Starting data generation for MedInsight Analytics Platform")

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(),
            TextColumn("[green]{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            steps = [
                "Clinics", "Specialties", "Services", "Doctors",
                "Patients", "Appointments", "Billing", "Prescriptions", "Lab Results",
            ]
            task = progress.add_task("Generating datasets", total=len(steps))

            progress.update(task, description="Generating Clinics...")
            clinics = self.generate_clinics()
            self._save(clinics, "clinics")
            progress.advance(task)

            progress.update(task, description="Generating Specialties...")
            specialties = self.generate_specialties()
            self._save(specialties, "specialties")
            progress.advance(task)

            progress.update(task, description="Generating Services...")
            services = self.generate_services()
            self._save(services, "services")
            progress.advance(task)

            progress.update(task, description="Generating Doctors...")
            doctors = self.generate_doctors(clinics, specialties)
            self._save(doctors, "doctors")
            progress.advance(task)

            progress.update(task, description="Generating Patients (5,000)...")
            patients = self.generate_patients()
            self._save(patients, "patients")
            progress.advance(task)

            progress.update(task, description="Generating Appointments (20,000)...")
            appointments = self.generate_appointments(patients, doctors, services, clinics)
            self._save(appointments, "appointments")
            progress.advance(task)

            progress.update(task, description="Generating Billing records...")
            billing = self.generate_billing(appointments, services)
            self._save(billing, "billing")
            progress.advance(task)

            progress.update(task, description="Generating Prescriptions...")
            prescriptions = self.generate_prescriptions(appointments, doctors)
            self._save(prescriptions, "prescriptions")
            progress.advance(task)

            progress.update(task, description="Generating Lab Results...")
            lab_results = self.generate_lab_results(appointments)
            self._save(lab_results, "lab_results")
            progress.advance(task)

        # Summary table
        datasets = {
            "clinics": clinics, "specialties": specialties, "services": services,
            "doctors": doctors, "patients": patients, "appointments": appointments,
            "billing": billing, "prescriptions": prescriptions, "lab_results": lab_results,
        }
        table = Table(title="[bold green]Generated Datasets Summary", show_header=True, header_style="bold magenta")
        table.add_column("Dataset", style="cyan")
        table.add_column("Rows", justify="right", style="green")
        table.add_column("Columns", justify="right")
        for name, df in datasets.items():
            table.add_row(name, f"{len(df):,}", str(len(df.columns)))
        console.print(table)

        logger.success("Data generation complete.")
        return datasets


def main() -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from config.settings import Settings

    settings = Settings()
    generator = DataGenerator(settings)
    generator.run()


if __name__ == "__main__":
    main()
