"""
MedInsight Analytics Platform - Enterprise Data Generator
Vectorised generation: 500k patients, 500 doctors, 60 clinics, 2M appointments, 2020-2024.
"""

import random
import sys
from datetime import date
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

# ── Romanian names ────────────────────────────────────────────────────────────

MALE_NAMES = [
    "Andrei","Alexandru","Mihai","Cristian","Ioan","Bogdan","Radu","Vlad","Ștefan",
    "Daniel","Marian","Florin","Cătălin","Gabriel","Ionuț","Robert","Victor","Adrian",
    "Lucian","George","Claudiu","Dragoș","Valentin","Cosmin","Silviu","Mădălin","Ovidiu",
    "Sorin","Relu","Dinu","Nicu","Grigore","Tiberiu","Dorian","Cristi","Bogdan","Andrei",
    "Rareș","Cezar","Octavian","Traian","Mircea","Corneliu","Eugen","Liviu","Petre","Aurel",
]

FEMALE_NAMES = [
    "Maria","Ana","Elena","Ioana","Andreea","Cristina","Mihaela","Alina","Roxana","Diana",
    "Laura","Larisa","Teodora","Alexandra","Simona","Raluca","Mădălina","Gabriela","Luminița",
    "Camelia","Denisa","Oana","Loredana","Florentina","Valentina","Beatrice","Claudia",
    "Nicoleta","Adriana","Ramona","Iuliana","Carmen","Dorina","Mariana","Florica","Aurelia",
    "Georgiana","Daniela","Mioara","Veronica","Rodica","Geanina","Petronela","Viorica",
]

LAST_NAMES = [
    "Popescu","Ionescu","Popa","Stan","Gheorghiu","Stoica","Constantin","Florea","Matei",
    "Marin","Dima","Dumitru","Moldovan","Rădulescu","Dragomir","Șerban","Grigorescu",
    "Niculescu","Dobre","Mihai","Cristea","Oprea","Petrescu","Andrei","Tudor","Manea",
    "Preda","Mocanu","Lazăr","Nistor","Toma","Vlad","Lungu","Sava","Ciobanu","Ungureanu",
    "Marinescu","Olaru","Coman","Iordache","Barbu","Dumitrescu","Enache","Filip","Ghiță",
    "Chirilă","Mureșan","Ardelean","Văduva","Roșu","Blaga","Zamfir","Voinea","Neagu",
    "Manolescu","Drăghici","Simion","Pandele","Tudose","Stănescu","Ionita","Sandu",
]

# ── 60 Clinics ────────────────────────────────────────────────────────────────

CLINICS_60 = [
    # București (15)
    {"id":"CLN001","name":"MedInsight București Central","city":"București","county":"Ilfov","region":"Sud","capacity":40,"focus":"Cardiologie","cost":85000},
    {"id":"CLN002","name":"MedInsight București Floreasca","city":"București","county":"Ilfov","region":"Sud","capacity":35,"focus":"Chirurgie","cost":78000},
    {"id":"CLN003","name":"MedInsight București Unirii","city":"București","county":"Ilfov","region":"Sud","capacity":30,"focus":"Pediatrie","cost":70000},
    {"id":"CLN004","name":"MedInsight București Militari","city":"București","county":"Ilfov","region":"Sud","capacity":28,"focus":"Ortopedie","cost":65000},
    {"id":"CLN005","name":"MedInsight București Băneasa","city":"București","county":"Ilfov","region":"Sud","capacity":32,"focus":"Neurologie","cost":72000},
    {"id":"CLN006","name":"MedInsight București Titan","city":"București","county":"Ilfov","region":"Sud","capacity":25,"focus":"Dermatologie","cost":58000},
    {"id":"CLN007","name":"MedInsight București Drumul Taberei","city":"București","county":"Ilfov","region":"Sud","capacity":22,"focus":"Medicina Interna","cost":52000},
    {"id":"CLN008","name":"MedInsight București Colentina","city":"București","county":"Ilfov","region":"Sud","capacity":20,"focus":"Oftalmologie","cost":48000},
    {"id":"CLN009","name":"MedInsight București Cotroceni","city":"București","county":"Ilfov","region":"Sud","capacity":30,"focus":"Ginecologie","cost":68000},
    {"id":"CLN010","name":"MedInsight București Dacia","city":"București","county":"Ilfov","region":"Sud","capacity":28,"focus":"Psihiatrie","cost":62000},
    {"id":"CLN011","name":"MedInsight București Dorobanți","city":"București","county":"Ilfov","region":"Sud","capacity":38,"focus":"Oncologie","cost":90000},
    {"id":"CLN012","name":"MedInsight București Tineretului","city":"București","county":"Ilfov","region":"Sud","capacity":18,"focus":"Pediatrie","cost":44000},
    {"id":"CLN013","name":"MedInsight Ilfov Otopeni","city":"Ilfov","county":"Ilfov","region":"Sud","capacity":15,"focus":"Medicina Interna","cost":38000},
    {"id":"CLN014","name":"MedInsight Ilfov Voluntari","city":"Ilfov","county":"Ilfov","region":"Sud","capacity":14,"focus":"Dermatologie","cost":35000},
    {"id":"CLN015","name":"MedInsight Ilfov Popești-Leordeni","city":"Ilfov","county":"Ilfov","region":"Sud","capacity":12,"focus":"Pediatrie","cost":30000},
    # Cluj (8)
    {"id":"CLN016","name":"MedInsight Cluj Central","city":"Cluj-Napoca","county":"Cluj","region":"Nord-Vest","capacity":35,"focus":"Cardiologie","cost":75000},
    {"id":"CLN017","name":"MedInsight Cluj Mărăști","city":"Cluj-Napoca","county":"Cluj","region":"Nord-Vest","capacity":28,"focus":"Neurologie","cost":60000},
    {"id":"CLN018","name":"MedInsight Cluj Gheorgheni","city":"Cluj-Napoca","county":"Cluj","region":"Nord-Vest","capacity":22,"focus":"Ortopedie","cost":50000},
    {"id":"CLN019","name":"MedInsight Cluj Zorilor","city":"Cluj-Napoca","county":"Cluj","region":"Nord-Vest","capacity":20,"focus":"Dermatologie","cost":46000},
    {"id":"CLN020","name":"MedInsight Turda","city":"Turda","county":"Cluj","region":"Nord-Vest","capacity":12,"focus":"Medicina Interna","cost":28000},
    {"id":"CLN021","name":"MedInsight Dej","city":"Dej","county":"Cluj","region":"Nord-Vest","capacity":10,"focus":"Pediatrie","cost":25000},
    {"id":"CLN022","name":"MedInsight Câmpia Turzii","city":"Câmpia Turzii","county":"Cluj","region":"Nord-Vest","capacity":8,"focus":"Medicina Interna","cost":20000},
    {"id":"CLN023","name":"MedInsight Gherla","city":"Gherla","county":"Cluj","region":"Nord-Vest","capacity":8,"focus":"Pediatrie","cost":20000},
    # Timișoara (7)
    {"id":"CLN024","name":"MedInsight Timișoara Central","city":"Timișoara","county":"Timiș","region":"Vest","capacity":32,"focus":"Cardiologie","cost":70000},
    {"id":"CLN025","name":"MedInsight Timișoara Fabric","city":"Timișoara","county":"Timiș","region":"Vest","capacity":24,"focus":"Ginecologie","cost":54000},
    {"id":"CLN026","name":"MedInsight Timișoara Dacia","city":"Timișoara","county":"Timiș","region":"Vest","capacity":20,"focus":"Ortopedie","cost":46000},
    {"id":"CLN027","name":"MedInsight Timișoara Mehala","city":"Timișoara","county":"Timiș","region":"Vest","capacity":18,"focus":"Pediatrie","cost":42000},
    {"id":"CLN028","name":"MedInsight Lugoj","city":"Lugoj","county":"Timiș","region":"Vest","capacity":10,"focus":"Medicina Interna","cost":24000},
    {"id":"CLN029","name":"MedInsight Deva","city":"Deva","county":"Hunedoara","region":"Vest","capacity":12,"focus":"Neurologie","cost":28000},
    {"id":"CLN030","name":"MedInsight Hunedoara","city":"Hunedoara","county":"Hunedoara","region":"Vest","capacity":10,"focus":"Ortopedie","cost":24000},
    # Iași (6)
    {"id":"CLN031","name":"MedInsight Iași Central","city":"Iași","county":"Iași","region":"Nord-Est","capacity":30,"focus":"Neurologie","cost":65000},
    {"id":"CLN032","name":"MedInsight Iași Copou","city":"Iași","county":"Iași","region":"Nord-Est","capacity":24,"focus":"Cardiologie","cost":54000},
    {"id":"CLN033","name":"MedInsight Iași Tătărași","city":"Iași","county":"Iași","region":"Nord-Est","capacity":20,"focus":"Pediatrie","cost":46000},
    {"id":"CLN034","name":"MedInsight Iași Podu Roș","city":"Iași","county":"Iași","region":"Nord-Est","capacity":18,"focus":"Medicina Interna","cost":42000},
    {"id":"CLN035","name":"MedInsight Bacău","city":"Bacău","county":"Bacău","region":"Nord-Est","capacity":15,"focus":"Cardiologie","cost":34000},
    {"id":"CLN036","name":"MedInsight Suceava","city":"Suceava","county":"Suceava","region":"Nord-Est","capacity":14,"focus":"Medicina Interna","cost":32000},
    # Constanța (5)
    {"id":"CLN037","name":"MedInsight Constanța Central","city":"Constanța","county":"Constanța","region":"Sud-Est","capacity":28,"focus":"Cardiologie","cost":60000},
    {"id":"CLN038","name":"MedInsight Constanța Mamaia","city":"Constanța","county":"Constanța","region":"Sud-Est","capacity":20,"focus":"Dermatologie","cost":46000},
    {"id":"CLN039","name":"MedInsight Constanța Tomis","city":"Constanța","county":"Constanța","region":"Sud-Est","capacity":18,"focus":"Medicina Interna","cost":42000},
    {"id":"CLN040","name":"MedInsight Medgidia","city":"Medgidia","county":"Constanța","region":"Sud-Est","capacity":10,"focus":"Pediatrie","cost":24000},
    {"id":"CLN041","name":"MedInsight Mangalia","city":"Mangalia","county":"Constanța","region":"Sud-Est","capacity":8,"focus":"Medicina Interna","cost":20000},
    # Brașov (5)
    {"id":"CLN042","name":"MedInsight Brașov Central","city":"Brașov","county":"Brașov","region":"Centru","capacity":30,"focus":"Ortopedie","cost":65000},
    {"id":"CLN043","name":"MedInsight Brașov Astra","city":"Brașov","county":"Brașov","region":"Centru","capacity":22,"focus":"Cardiologie","cost":50000},
    {"id":"CLN044","name":"MedInsight Brașov Bartolomeu","city":"Brașov","county":"Brașov","region":"Centru","capacity":18,"focus":"Neurologie","cost":42000},
    {"id":"CLN045","name":"MedInsight Sinaia","city":"Sinaia","county":"Prahova","region":"Centru","capacity":10,"focus":"Medicina Interna","cost":24000},
    {"id":"CLN046","name":"MedInsight Sfântu Gheorghe","city":"Sfântu Gheorghe","county":"Covasna","region":"Centru","capacity":10,"focus":"Pediatrie","cost":24000},
    # Other major cities (14)
    {"id":"CLN047","name":"MedInsight Craiova Central","city":"Craiova","county":"Dolj","region":"Sud-Vest","capacity":25,"focus":"Cardiologie","cost":55000},
    {"id":"CLN048","name":"MedInsight Craiova Romanescu","city":"Craiova","county":"Dolj","region":"Sud-Vest","capacity":18,"focus":"Neurologie","cost":42000},
    {"id":"CLN049","name":"MedInsight Ploiești Central","city":"Ploiești","county":"Prahova","region":"Sud","capacity":22,"focus":"Medicina Interna","cost":50000},
    {"id":"CLN050","name":"MedInsight Ploiești Mihai Bravu","city":"Ploiești","county":"Prahova","region":"Sud","capacity":18,"focus":"Ortopedie","cost":42000},
    {"id":"CLN051","name":"MedInsight Oradea Central","city":"Oradea","county":"Bihor","region":"Nord-Vest","capacity":20,"focus":"Cardiologie","cost":46000},
    {"id":"CLN052","name":"MedInsight Oradea Nufărul","city":"Oradea","county":"Bihor","region":"Nord-Vest","capacity":15,"focus":"Pediatrie","cost":35000},
    {"id":"CLN053","name":"MedInsight Sibiu Central","city":"Sibiu","county":"Sibiu","region":"Centru","capacity":20,"focus":"Cardiologie","cost":46000},
    {"id":"CLN054","name":"MedInsight Sibiu Strand","city":"Sibiu","county":"Sibiu","region":"Centru","capacity":15,"focus":"Ortopedie","cost":35000},
    {"id":"CLN055","name":"MedInsight Galați","city":"Galați","county":"Galați","region":"Sud-Est","capacity":18,"focus":"Medicina Interna","cost":42000},
    {"id":"CLN056","name":"MedInsight Arad Central","city":"Arad","county":"Arad","region":"Vest","capacity":18,"focus":"Cardiologie","cost":42000},
    {"id":"CLN057","name":"MedInsight Târgu Mureș","city":"Târgu Mureș","county":"Mureș","region":"Centru","capacity":20,"focus":"Neurologie","cost":46000},
    {"id":"CLN058","name":"MedInsight Pitești","city":"Pitești","county":"Argeș","region":"Sud","capacity":16,"focus":"Ortopedie","cost":38000},
    {"id":"CLN059","name":"MedInsight Baia Mare","city":"Baia Mare","county":"Maramureș","region":"Nord-Vest","capacity":15,"focus":"Medicina Interna","cost":35000},
    {"id":"CLN060","name":"MedInsight Alba Iulia","city":"Alba Iulia","county":"Alba","region":"Centru","capacity":14,"focus":"Cardiologie","cost":32000},
]

CLINIC_CITIES = sorted(set(c["city"] for c in CLINICS_60))
CLINIC_CITY_WEIGHTS = {
    "București": 0.28, "Cluj-Napoca": 0.08, "Timișoara": 0.07, "Iași": 0.07,
    "Constanța": 0.05, "Brașov": 0.05, "Craiova": 0.04, "Ploiești": 0.03,
    "Oradea": 0.03, "Sibiu": 0.03,
}
DEFAULT_CITY_WEIGHT = 0.01

SPECIALTIES = [
    "Cardiologie","Pediatrie","Ortopedie","Neurologie","Dermatologie",
    "Oftalmologie","Ginecologie","Psihiatrie","Oncologie","Medicina Interna",
]

SPECIALTY_PRICE = {
    "Cardiologie":(250,380),"Pediatrie":(180,260),"Ortopedie":(230,340),
    "Neurologie":(270,400),"Dermatologie":(180,290),"Oftalmologie":(180,270),
    "Ginecologie":(220,310),"Psihiatrie":(280,400),"Oncologie":(350,550),
    "Medicina Interna":(210,310),
}

BLOOD_TYPES = ["O+","A+","B+","AB+","O-","A-","B-","AB-"]
BLOOD_TYPE_WEIGHTS = [0.37,0.36,0.09,0.03,0.06,0.06,0.02,0.01]

CHRONIC_CONDITIONS = [
    "Hipertensiune arteriala","Diabet zaharat tip 2","Astm bronsic","Boala coronariana",
    "Obezitate","Hipotiroidism","Depresie","Anxietate","Artroza","Cardiopatie ischemica",
    "Reflux gastroesofagian","Migrena cronica","Apnee in somn","Insuficienta renala cronica",
]

INSURANCE_TYPES = ["CNAS","Private","Neasigurat"]
INSURANCE_WEIGHTS = [0.55,0.35,0.10]

SERVICES_DEF = [
    {"code":"CONS","name":"Consultatie medicala","category":"consultatie","price_range":(150,450),"duration":30,"margin":0.70,"reimbursement":0.30},
    {"code":"ECO","name":"Ecografie abdominala","category":"imagistica","price_range":(150,350),"duration":30,"margin":0.55,"reimbursement":0.25},
    {"code":"RMN","name":"Rezonanta Magnetica Nucleara","category":"imagistica","price_range":(600,1200),"duration":60,"margin":0.45,"reimbursement":0.20},
    {"code":"CT","name":"Computer Tomograf","category":"imagistica","price_range":(400,900),"duration":45,"margin":0.50,"reimbursement":0.20},
    {"code":"RX","name":"Radiografie","category":"imagistica","price_range":(80,200),"duration":15,"margin":0.60,"reimbursement":0.30},
    {"code":"ALAB","name":"Analize de laborator","category":"laborator","price_range":(50,500),"duration":15,"margin":0.65,"reimbursement":0.40},
    {"code":"CHIR","name":"Interventie chirurgicala mica","category":"interventie","price_range":(500,2500),"duration":90,"margin":0.40,"reimbursement":0.15},
    {"code":"PSIH","name":"Sedinta psihoterapie","category":"terapie","price_range":(150,350),"duration":50,"margin":0.80,"reimbursement":0.10},
    {"code":"CTRL","name":"Control periodic","category":"preventie","price_range":(100,300),"duration":30,"margin":0.72,"reimbursement":0.35},
    {"code":"VACC","name":"Vaccinare","category":"preventie","price_range":(80,350),"duration":15,"margin":0.60,"reimbursement":0.45},
    {"code":"FIZIO","name":"Sedinta fizioterapie","category":"recuperare","price_range":(100,250),"duration":45,"margin":0.65,"reimbursement":0.25},
    {"code":"ENDO","name":"Endoscopie digestiva","category":"investigatie","price_range":(400,800),"duration":45,"margin":0.48,"reimbursement":0.20},
    {"code":"ECO_CARD","name":"Ecocardiografie","category":"imagistica","price_range":(250,500),"duration":40,"margin":0.55,"reimbursement":0.25},
    {"code":"EEG","name":"Electroencefalograma","category":"investigatie","price_range":(200,400),"duration":60,"margin":0.55,"reimbursement":0.20},
    {"code":"EMG","name":"Electromiografie","category":"investigatie","price_range":(250,500),"duration":60,"margin":0.50,"reimbursement":0.15},
    {"code":"COLO","name":"Colonoscopie","category":"investigatie","price_range":(600,1000),"duration":60,"margin":0.45,"reimbursement":0.20},
]

CANCELLATION_REASONS = [
    "Conflict program","Motiv personal","Transport indisponibil","Alta clinica",
    "Imbunatatire stare sanatate","Cost prea ridicat","Lipsa comunicare","Asteptare prea lunga",
]

PAYMENT_METHODS = ["Card","Numerar","Transfer bancar","Asigurare privata","CNAS"]
PAYMENT_WEIGHTS = [0.45,0.20,0.10,0.17,0.08]

MEDICATIONS = [
    "Metformin 500mg","Lisinopril 10mg","Atorvastatin 20mg","Omeprazol 20mg","Amlodipina 5mg",
    "Bisoprolol 5mg","Levotiroxina 50mcg","Aspirina 75mg","Paracetamol 500mg","Ibuprofen 400mg",
    "Amoxicilina 500mg","Azitromicina 500mg","Metoprolol 25mg","Furosemid 40mg","Ramipril 5mg",
    "Clopidogrel 75mg","Insulina NPH","Prednison 5mg","Pantoprazol 40mg","Escitalopram 10mg",
    "Sertralin 50mg","Alprazolam 0.5mg","Quetiapina 25mg","Tramadol 50mg","Nifedipina 10mg",
]

LAB_TESTS = [
    {"name":"Hemoglobina","unit":"g/dL","normal_range":(12.0,17.5),"std":1.5},
    {"name":"Leucocite","unit":"10^3/uL","normal_range":(4.5,11.0),"std":2.0},
    {"name":"Glicemie a jeun","unit":"mg/dL","normal_range":(70.0,100.0),"std":15.0},
    {"name":"Colesterol total","unit":"mg/dL","normal_range":(0.0,200.0),"std":40.0},
    {"name":"LDL Colesterol","unit":"mg/dL","normal_range":(0.0,130.0),"std":30.0},
    {"name":"Trigliceride","unit":"mg/dL","normal_range":(0.0,150.0),"std":40.0},
    {"name":"Creatinina","unit":"mg/dL","normal_range":(0.7,1.2),"std":0.2},
    {"name":"ALT","unit":"U/L","normal_range":(0.0,40.0),"std":15.0},
    {"name":"TSH","unit":"mIU/L","normal_range":(0.4,4.0),"std":1.0},
    {"name":"Vitamina D","unit":"ng/mL","normal_range":(30.0,100.0),"std":20.0},
]


def _fake_cnp(gender_arr: np.ndarray, birth_arr: np.ndarray) -> np.ndarray:
    n = len(gender_arr)
    sex = np.where(gender_arr == "M", "1", "2")
    years = np.array([str(d.year)[-2:] for d in birth_arr])
    months = np.array([f"{d.month:02d}" for d in birth_arr])
    days = np.array([f"{d.day:02d}" for d in birth_arr])
    counties = np.random.randint(1, 47, n).astype(str)
    counties = np.char.zfill(counties, 2)
    seqs = np.random.randint(1, 1000, n).astype(str)
    seqs = np.char.zfill(seqs, 3)
    checks = np.random.randint(0, 10, n).astype(str)
    return np.char.add(
        np.char.add(np.char.add(np.char.add(np.char.add(np.char.add(sex, years), months), days), counties), seqs),
        checks
    )


class DataGenerator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        settings.data.ensure_dirs()

    def generate_clinics(self) -> pd.DataFrame:
        rows = []
        for c in CLINICS_60:
            rows.append({
                "clinic_id": c["id"],
                "name": c["name"],
                "city": c["city"],
                "county": c["county"],
                "region": c["region"],
                "address": f"Str. Principală {np.random.randint(1,200)}, {c['city']}",
                "phone": f"+40{np.random.randint(200000000,299999999)}",
                "capacity": c["capacity"],
                "opening_date": date(np.random.randint(2008,2020), np.random.randint(1,12), np.random.randint(1,28)),
                "specialization_focus": c["focus"],
                "operational_cost": c["cost"],
                "is_active": True,
            })
        return pd.DataFrame(rows)

    def generate_specialties(self) -> pd.DataFrame:
        cfg_path = self.settings.base_dir / "config" / "config.yaml"
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f)
        rows = [{"specialty_id": s["id"], "name": s["name"],
                 "avg_consultation_price": s["avg_consultation_price"],
                 "avg_duration_min": s["avg_duration_min"]} for s in cfg["specialties"]]
        return pd.DataFrame(rows)

    def generate_services(self) -> pd.DataFrame:
        rows = []
        for i, s in enumerate(SERVICES_DEF, 1):
            price = np.random.randint(*s["price_range"])
            rows.append({"service_id": f"SVC{i:03d}", "code": s["code"], "name": s["name"],
                         "category": s["category"], "base_price": price,
                         "duration_minutes": s["duration"], "profitability_margin": s["margin"],
                         "reimbursement_pct": s["reimbursement"], "is_active": True})
        return pd.DataFrame(rows)

    def generate_doctors(self, clinics: pd.DataFrame, specialties: pd.DataFrame) -> pd.DataFrame:
        n = self.settings.data.num_doctors
        clinic_ids = clinics["clinic_id"].values
        rows = []
        for i in range(1, n + 1):
            sp = SPECIALTIES[(i - 1) % len(SPECIALTIES)]
            gender = "M" if i % 3 != 0 else "F"
            fname = np.random.choice(MALE_NAMES if gender == "M" else FEMALE_NAMES)
            lname = np.random.choice(LAST_NAMES)
            yoe = np.random.randint(2, 32)
            rating = float(np.clip(np.random.normal(4.3, 0.4), 3.0, 5.0).round(1))
            lo, hi = SPECIALTY_PRICE[sp]
            hire_year = max(2008, 2024 - yoe)
            fclean = fname.lower().translate(str.maketrans("șțâîă","staia"))
            lclean = lname.lower().translate(str.maketrans("șțâîă","staia"))
            rows.append({
                "doctor_id": f"DOC{i:03d}",
                "first_name": fname, "last_name": lname,
                "full_name": f"Dr. {lname} {fname}", "gender": gender,
                "specialty": sp,
                "clinic_id": clinic_ids[i % len(clinic_ids)],
                "years_experience": yoe,
                "hire_date": date(hire_year, np.random.randint(1,12), np.random.randint(1,28)),
                "consultation_price": np.random.randint(lo, hi),
                "rating": rating,
                "monthly_salary": round(float(np.random.uniform(8000, 30000)), 2),
                "performance_score": round(float(np.clip(np.random.normal(78, 12), 40, 100)), 1),
                "burnout_risk_score": round(float(np.clip(np.random.normal(35, 18), 0, 100)), 1),
                "is_active": True,
                "email": f"{fclean}.{lclean}@medinsight.ro",
                "phone": f"+407{np.random.randint(0,99999999):08d}",
            })
        return pd.DataFrame(rows)

    def generate_patients(self) -> pd.DataFrame:
        n = self.settings.data.num_patients
        logger.info(f"Generating {n:,} patients (vectorised)")

        # Gender split
        genders = np.where(np.random.random(n) < 0.52, "F", "M")
        # First names — vectorised
        male_idx = np.random.randint(0, len(MALE_NAMES), n)
        female_idx = np.random.randint(0, len(FEMALE_NAMES), n)
        first_names = np.where(
            genders == "M",
            np.array(MALE_NAMES)[male_idx],
            np.array(FEMALE_NAMES)[female_idx],
        )
        last_idx = np.random.randint(0, len(LAST_NAMES), n)
        last_names = np.array(LAST_NAMES)[last_idx]

        ages = np.clip(np.random.normal(44, 18, n).astype(int), 1, 92)
        birth_years = 2024 - ages
        birth_months = np.random.randint(1, 13, n)
        birth_days = np.random.randint(1, 29, n)
        birth_dates = pd.to_datetime({
            "year": birth_years, "month": birth_months, "day": birth_days
        }, errors="coerce").dt.date

        blood_types = np.random.choice(BLOOD_TYPES, n, p=BLOOD_TYPE_WEIGHTS)
        insurance = np.random.choice(INSURANCE_TYPES, n, p=INSURANCE_WEIGHTS)

        # City distribution using clinic cities
        cities_list = list(CLINIC_CITY_WEIGHTS.keys())
        city_w = np.array([CLINIC_CITY_WEIGHTS[c] for c in cities_list])
        remaining = sorted(set(CLINIC_CITIES) - set(cities_list))
        all_cities = cities_list + remaining
        all_w = np.concatenate([city_w, np.full(len(remaining), DEFAULT_CITY_WEIGHT)])
        all_w /= all_w.sum()
        cities = np.random.choice(all_cities, n, p=all_w)

        county_map = {c["city"]: c["county"] for c in CLINICS_60}
        counties = np.array([county_map.get(c, "Romania") for c in cities])

        # Chronic conditions (vectorised string join)
        n_cond = np.random.choice([0,1,2,3], n, p=[0.50,0.30,0.15,0.05])
        conditions = np.array([
            "; ".join(np.random.choice(CHRONIC_CONDITIONS, nc, replace=False).tolist()) if nc > 0 else ""
            for nc in n_cond
        ])

        risk_scores = np.clip(np.random.exponential(25, n), 0, 100).round(1)

        reg_years = np.random.randint(2018, 2024, n)
        reg_months = np.random.randint(1, 13, n)
        reg_days = np.random.randint(1, 29, n)
        reg_dates = pd.to_datetime({
            "year": reg_years, "month": reg_months, "day": reg_days
        }, errors="coerce").dt.date

        # Emails — vectorised
        fclean = np.vectorize(lambda x: x.lower().translate(str.maketrans("șțâîă","staia")))(first_names)
        lclean = np.vectorize(lambda x: x.lower().translate(str.maketrans("șțâîă","staia")))(last_names)
        suffixes = np.random.randint(1, 999, n).astype(str)
        domains = np.random.choice(["gmail.com","yahoo.com","hotmail.com"], n)
        emails = np.char.add(
            np.char.add(np.char.add(np.char.add(fclean, "."), lclean), suffixes),
            np.char.add("@", domains),
        )
        phones = np.array([f"+407{np.random.randint(0,99999999):08d}" for _ in range(n)])
        patient_ids = np.array([f"PAT{i+1:06d}" for i in range(n)])
        cnps = _fake_cnp(genders, birth_dates)

        return pd.DataFrame({
            "patient_id": patient_ids,
            "cnp": cnps,
            "first_name": first_names, "last_name": last_names,
            "full_name": np.char.add(np.char.add(last_names, " "), first_names),
            "gender": genders,
            "birth_date": birth_dates, "age": ages,
            "blood_type": blood_types, "city": cities, "county": counties,
            "email": emails, "phone": phones,
            "insurance_status": insurance,
            "chronic_conditions": np.where(conditions == "", None, conditions),
            "risk_score": risk_scores,
            "registration_date": reg_dates,
            "is_active": True,
        })

    def generate_appointments(
        self,
        patients: pd.DataFrame,
        doctors: pd.DataFrame,
        services: pd.DataFrame,
        clinics: pd.DataFrame,
    ) -> pd.DataFrame:
        n = self.settings.data.num_appointments
        logger.info(f"Generating {n:,} appointments (fully vectorised)")

        # Pre-build index arrays
        pat_ids = patients["patient_id"].values
        doc_ids = doctors["doctor_id"].values
        svc_ids = services["service_id"].values
        svc_prices = services["base_price"].values.astype(float)
        svc_durations = services["duration_minutes"].values.astype(int)
        doc_clinic = doctors["clinic_id"].values
        doc_specialty = doctors["specialty"].values

        n_pat, n_doc, n_svc = len(pat_ids), len(doc_ids), len(svc_ids)

        # Patient visit weights — exponential (power-law behaviour)
        pat_w = np.random.exponential(1.0, n_pat) + 0.1
        pat_w /= pat_w.sum()

        pat_idx = np.random.choice(n_pat, size=n, p=pat_w)
        doc_idx = np.random.choice(n_doc, size=n)
        svc_idx = np.random.choice(n_svc, size=n)

        # Business-day dates with seasonality
        biz_days = pd.bdate_range(
            self.settings.data.start_date,
            self.settings.data.end_date,
        )
        month_w = np.array([0.70,0.85,1.10,1.20,1.15,1.00,0.80,0.65,1.15,1.25,1.10,0.75])
        day_w = month_w[biz_days.month - 1]
        # Saturday clinic weight bump (60% of clinics open)
        sat_days = pd.date_range(
            self.settings.data.start_date,
            self.settings.data.end_date,
            freq="W-SAT",
        )
        biz_days_combined = biz_days.append(sat_days).sort_values().unique()
        day_w_full = month_w[pd.DatetimeIndex(biz_days_combined).month - 1]
        day_w_full /= day_w_full.sum()

        day_idx = np.random.choice(len(biz_days_combined), size=n, p=day_w_full)
        appt_dates = biz_days_combined[day_idx]

        hour_w = np.array([0.08,0.12,0.13,0.12,0.10,0.08,0.10,0.10,0.10,0.07])
        hours = np.random.choice(range(8, 18), size=n, p=hour_w)
        minutes = np.random.choice([0,15,30,45], size=n)

        # Build scheduled_at via timedelta arithmetic (vectorised)
        base_ts = pd.to_datetime(appt_dates).values
        time_offset = (hours.astype("int64") * 60 + minutes.astype("int64")).astype("timedelta64[m]")
        scheduled_at = base_ts + time_offset

        # Statuses
        statuses = np.random.choice(
            ["completed","cancelled","no_show","rescheduled"],
            size=n, p=[0.72,0.14,0.09,0.05],
        )
        completed = statuses == "completed"

        # Prices
        base_prices = svc_prices[svc_idx]
        disc = np.random.choice([0,0.05,0.10,0.15], size=n, p=[0.65,0.15,0.12,0.08])
        actual_prices = np.where(completed, (base_prices * (1 - disc)).round(2), 0.0)

        # Ratings
        rating_mask = completed & (np.random.random(n) < 0.65)
        raw_ratings = np.clip(np.random.normal(4.3, 0.6, n), 1.0, 5.0).round(1)
        ratings = np.where(rating_mask, raw_ratings, np.nan)

        # Wait times
        raw_wait = np.clip(np.random.exponential(12, n), 0, 90).round(0)
        wait_times = np.where(completed, raw_wait, np.nan)

        # Actual start/end
        wait_td = np.where(
            completed,
            raw_wait.astype("int64"),
            0,
        ).astype("timedelta64[m]")
        dur = svc_durations[svc_idx] + np.random.randint(-5, 16, size=n)
        dur_td = np.where(completed, dur.astype("int64"), 0).astype("timedelta64[m]")
        actual_start = np.where(completed, scheduled_at + wait_td, pd.NaT)
        actual_end = np.where(completed, scheduled_at + wait_td + dur_td, pd.NaT)

        # Channels / urgency / referral
        channels = np.random.choice(
            ["Online","Telefon","Fizic","Aplicatie mobila","Referinta medic"],
            size=n, p=[0.35,0.30,0.15,0.15,0.05],
        )
        urgency = np.random.choice(
            ["Electiv","Urgent","Semigur"], size=n, p=[0.70,0.20,0.10],
        )
        referrals = np.random.choice(
            ["Medic de familie","Auto-referire","Recomandare pacient","Publicitate online","Specialist intern"],
            size=n,
        )
        cancel_mask = np.isin(statuses, ["cancelled","rescheduled"])
        cancel_reasons = np.where(
            cancel_mask,
            np.random.choice(CANCELLATION_REASONS, size=n),
            None,
        )
        consult_dur = np.where(completed, dur.astype(float), np.nan)

        # String IDs — vectorised
        ids_num = np.arange(1, n + 1)
        appt_ids = np.char.add("APT", np.char.zfill(ids_num.astype(str), 7))

        return pd.DataFrame({
            "appointment_id": appt_ids,
            "patient_id": pat_ids[pat_idx],
            "doctor_id": doc_ids[doc_idx],
            "service_id": svc_ids[svc_idx],
            "clinic_id": doc_clinic[doc_idx],
            "specialty": doc_specialty[doc_idx],
            "scheduled_at": pd.to_datetime(scheduled_at),
            "actual_start": pd.to_datetime(actual_start),
            "actual_end": pd.to_datetime(actual_end),
            "status": statuses,
            "waiting_time_minutes": wait_times,
            "consultation_duration_minutes": consult_dur,
            "channel": channels,
            "urgency_level": urgency,
            "referral_source": referrals,
            "cancellation_reason": cancel_reasons,
            "actual_price": actual_prices,
            "discount_pct": disc,
            "rating": ratings,
            "notes": None,
        })

    def generate_billing(self, appointments: pd.DataFrame, services: pd.DataFrame) -> pd.DataFrame:
        completed = appointments[appointments["status"] == "completed"].copy()
        n = len(completed)
        logger.info(f"Generating {n:,} billing records (vectorised)")

        svc_reimb = dict(zip(services["service_id"], services["reimbursement_pct"]))
        reimb_rates = np.array([svc_reimb.get(s, 0.20) for s in completed["service_id"]])
        insurance = np.random.choice(INSURANCE_TYPES, n, p=INSURANCE_WEIGHTS)
        gross = completed["actual_price"].values.astype(float)
        insurance_reimb = np.where(insurance != "Neasigurat", (gross * reimb_rates).round(2), 0.0)
        patient_paid = (gross - insurance_reimb).round(2)
        tax = (patient_paid * 0.05).round(2)
        refund = np.where(np.random.random(n) < 0.03, (gross * 0.05).round(2), 0.0)
        net_revenue = (patient_paid - refund).clip(0)
        payment_method = np.random.choice(PAYMENT_METHODS, n, p=PAYMENT_WEIGHTS)
        payment_status = np.random.choice(
            ["paid","pending","partial","refunded"], n, p=[0.88,0.05,0.04,0.03]
        )

        invoice_dates = pd.to_datetime(
            completed["actual_end"].fillna(completed["scheduled_at"])
        ).dt.date.values

        ids_num = np.arange(1, n + 1)
        billing_ids = np.char.add("BILL", np.char.zfill(ids_num.astype(str), 8))

        return pd.DataFrame({
            "billing_id": billing_ids,
            "appointment_id": completed["appointment_id"].values,
            "patient_id": completed["patient_id"].values,
            "invoice_date": invoice_dates,
            "service_price": gross,
            "discount_amount": (gross * completed["discount_pct"].values).round(2),
            "insurance_reimbursement": insurance_reimb,
            "patient_paid": patient_paid,
            "tax_amount": tax,
            "total_amount": patient_paid,
            "refund_amount": refund,
            "net_revenue": net_revenue,
            "payment_method": payment_method,
            "payment_status": payment_status,
            "insurance_type": insurance,
        })

    def generate_prescriptions(self, appointments: pd.DataFrame, doctors: pd.DataFrame) -> pd.DataFrame:
        completed = appointments[appointments["status"] == "completed"]
        mask = np.random.random(len(completed)) < 0.35
        subset = completed[mask]
        n = len(subset)
        logger.info(f"Generating prescriptions for {n:,} appointments")

        med_count = np.random.choice([1,2,3], n, p=[0.62,0.30,0.08])
        rows = []
        rx_num = 0
        for i, (_, row) in enumerate(subset.iterrows()):
            for med in np.random.choice(MEDICATIONS, med_count[i], replace=False):
                rx_num += 1
                rows.append({
                    "prescription_id": f"RX{rx_num:08d}",
                    "appointment_id": row["appointment_id"],
                    "doctor_id": row["doctor_id"],
                    "patient_id": row["patient_id"],
                    "medication_name": med,
                    "dosage": med.split(" ")[-1] if " " in med else "1cp",
                    "frequency": np.random.choice(["1x/zi","2x/zi","3x/zi","la nevoie"]),
                    "duration_days": int(np.random.choice([5,7,10,14,21,30,60,90])),
                    "prescribed_at": row["scheduled_at"],
                    "is_chronic": bool(np.random.random() < 0.25),
                })
        return pd.DataFrame(rows)

    def generate_lab_results(self, appointments: pd.DataFrame) -> pd.DataFrame:
        lab_apts = appointments[
            (appointments["status"] == "completed") &
            (np.random.random(len(appointments)) < 0.18)
        ]
        n = len(lab_apts)
        logger.info(f"Generating lab results for {n:,} appointments")

        rows = []
        lab_num = 0
        for _, row in lab_apts.iterrows():
            tests = np.random.choice(LAB_TESTS, np.random.randint(2, 6), replace=False)
            collected_at = row["actual_start"] if pd.notna(row["actual_start"]) else row["scheduled_at"]
            result_at = collected_at + pd.Timedelta(hours=int(np.random.randint(1, 49)))
            for t in tests:
                lab_num += 1
                lo, hi = t["normal_range"]
                center = (lo + hi) / 2
                is_abnormal = np.random.random() < 0.15
                if is_abnormal:
                    value = round(float(np.random.uniform(lo * 0.5, lo * 0.95) if np.random.random() < 0.5
                                        else np.random.uniform(hi * 1.05, hi * 1.5)), 2)
                else:
                    value = round(float(np.clip(np.random.normal(center, t["std"]), lo, hi)), 2)
                rows.append({
                    "lab_result_id": f"LAB{lab_num:09d}",
                    "appointment_id": row["appointment_id"],
                    "patient_id": row["patient_id"],
                    "test_name": t["name"], "value": value, "unit": t["unit"],
                    "reference_range_low": lo, "reference_range_high": hi,
                    "is_abnormal": is_abnormal,
                    "collected_at": collected_at, "result_at": result_at,
                })
        return pd.DataFrame(rows)

    def _save_csv(self, df: pd.DataFrame, name: str) -> None:
        path = self.settings.data.raw_dir / f"{name}.csv"
        df.to_csv(path, index=False)
        logger.info(f"CSV: {path.name} ({len(df):,} rows)")

    def _save_parquet(self, df: pd.DataFrame, name: str, partition_col: str | None = None) -> None:
        if partition_col and partition_col in df.columns:
            # Partition by year
            years = df[partition_col].dt.year.unique() if hasattr(df[partition_col].dt, 'year') else []
            for yr in sorted(years):
                part_path = self.settings.data.bronze_dir / f"{name}_year={yr}.parquet"
                chunk = df[df[partition_col].dt.year == yr]
                pq.write_table(pa.Table.from_pandas(chunk), part_path, compression="snappy")
            logger.info(f"Parquet (partitioned): {name} — {len(years)} partitions")
        else:
            path = self.settings.data.bronze_dir / f"{name}.parquet"
            pq.write_table(pa.Table.from_pandas(df), path, compression="snappy")
            logger.info(f"Parquet: {path.name} ({len(df):,} rows)")

    def run(self) -> dict[str, pd.DataFrame]:
        logger.info("MedInsight Enterprise Data Generation starting")

        with Progress(
            SpinnerColumn(), TextColumn("[bold cyan]{task.description}"),
            BarColumn(), TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(), console=console,
        ) as progress:
            task = progress.add_task("Generating", total=9)

            progress.update(task, description="Clinics (60)")
            clinics = self.generate_clinics()
            self._save_csv(clinics, "clinics"); self._save_parquet(clinics, "clinics")
            progress.advance(task)

            progress.update(task, description="Specialties")
            specialties = self.generate_specialties()
            self._save_csv(specialties, "specialties"); self._save_parquet(specialties, "specialties")
            progress.advance(task)

            progress.update(task, description="Services")
            services = self.generate_services()
            self._save_csv(services, "services"); self._save_parquet(services, "services")
            progress.advance(task)

            progress.update(task, description="Doctors (500)")
            doctors = self.generate_doctors(clinics, specialties)
            self._save_csv(doctors, "doctors"); self._save_parquet(doctors, "doctors")
            progress.advance(task)

            progress.update(task, description="Patients (500,000)")
            patients = self.generate_patients()
            self._save_csv(patients, "patients"); self._save_parquet(patients, "patients")
            progress.advance(task)

            progress.update(task, description="Appointments (2,000,000)")
            appointments = self.generate_appointments(patients, doctors, services, clinics)
            self._save_csv(appointments, "appointments")
            self._save_parquet(appointments, "appointments", partition_col="scheduled_at")
            progress.advance(task)

            progress.update(task, description="Billing")
            billing = self.generate_billing(appointments, services)
            self._save_csv(billing, "billing"); self._save_parquet(billing, "billing")
            progress.advance(task)

            progress.update(task, description="Prescriptions")
            prescriptions = self.generate_prescriptions(appointments, doctors)
            self._save_csv(prescriptions, "prescriptions"); self._save_parquet(prescriptions, "prescriptions")
            progress.advance(task)

            progress.update(task, description="Lab Results")
            lab_results = self.generate_lab_results(appointments)
            self._save_csv(lab_results, "lab_results"); self._save_parquet(lab_results, "lab_results")
            progress.advance(task)

        datasets = {
            "clinics": clinics, "specialties": specialties, "services": services,
            "doctors": doctors, "patients": patients, "appointments": appointments,
            "billing": billing, "prescriptions": prescriptions, "lab_results": lab_results,
        }
        tbl = Table(title="[bold green]Enterprise Dataset Summary", header_style="bold magenta")
        tbl.add_column("Dataset", style="cyan")
        tbl.add_column("Rows", justify="right", style="green")
        for name, df in datasets.items():
            tbl.add_row(name, f"{len(df):,}")
        console.print(tbl)
        logger.success("Data generation complete")
        return datasets


def main() -> None:
    settings = Settings()
    DataGenerator(settings).run()


if __name__ == "__main__":
    main()
