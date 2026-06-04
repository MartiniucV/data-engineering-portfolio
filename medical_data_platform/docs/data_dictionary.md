# MedInsight Analytics Platform — Data Dictionary

## raw.appointments

| Column | Type | Description |
|--------|------|-------------|
| appointment_id | VARCHAR(12) | Primary key. Format: APT######. |
| patient_id | VARCHAR(10) | FK → raw.patients |
| doctor_id | VARCHAR(10) | FK → raw.doctors |
| service_id | VARCHAR(10) | FK → raw.services |
| clinic_id | VARCHAR(10) | FK → raw.clinics |
| specialty | VARCHAR(100) | Specialty at time of appointment |
| scheduled_at | TIMESTAMPTZ | Original scheduled datetime |
| actual_start | TIMESTAMPTZ | When consultation actually started (completed only) |
| actual_end | TIMESTAMPTZ | When consultation ended |
| status | VARCHAR(20) | completed / cancelled / no_show / rescheduled |
| waiting_time_minutes | INT | Minutes from check-in to consultation start |
| consultation_duration_minutes | INT | Duration of completed consultation |
| channel | VARCHAR(50) | Booking channel: Online/Telefon/Fizic/Aplicatie mobila/Referinta medic |
| urgency_level | VARCHAR(20) | Electiv / Semigur / Urgent |
| referral_source | VARCHAR(100) | How patient was referred |
| cancellation_reason | VARCHAR(200) | Reason for cancellation (nullable) |
| actual_price | NUMERIC(10,2) | Price charged after discount (0 for non-completed) |
| discount_pct | NUMERIC(5,4) | Discount applied (0.00–1.00) |
| rating | NUMERIC(3,1) | Patient satisfaction score (1.0–5.0, nullable) |
| notes | TEXT | Free-text clinical notes (nullable) |

## raw.patients

| Column | Type | Description |
|--------|------|-------------|
| patient_id | VARCHAR(10) | Primary key. Format: PAT#####. |
| cnp | VARCHAR(15) | Synthetic Romanian personal ID (not real) |
| first_name | VARCHAR(100) | Romanian given name |
| last_name | VARCHAR(100) | Romanian family name |
| gender | CHAR(1) | M / F |
| birth_date | DATE | Date of birth |
| age | INT | Age in years |
| blood_type | VARCHAR(5) | ABO + Rh type |
| city | VARCHAR(50) | One of the 6 clinic cities |
| county | VARCHAR(50) | Romanian county |
| insurance_status | VARCHAR(30) | CNAS / Private / Neasigurat |
| chronic_conditions | TEXT | Semicolon-separated list of chronic diagnoses (nullable) |
| risk_score | NUMERIC(5,1) | Computed risk score 0–100 |
| registration_date | DATE | Date patient registered in the system |

## raw.billing

| Column | Type | Description |
|--------|------|-------------|
| billing_id | VARCHAR(12) | Primary key |
| appointment_id | VARCHAR(12) | FK → raw.appointments |
| invoice_date | DATE | Invoice issue date |
| service_price | NUMERIC(10,2) | Gross price before discounts |
| discount_amount | NUMERIC(10,2) | Absolute discount amount |
| insurance_reimbursement | NUMERIC(10,2) | Amount covered by insurer |
| patient_paid | NUMERIC(10,2) | Amount billed to patient |
| tax_amount | NUMERIC(10,2) | VAT amount |
| total_amount | NUMERIC(10,2) | Total patient-facing amount |
| refund_amount | NUMERIC(10,2) | Refund issued (0 if none) |
| net_revenue | NUMERIC(10,2) | total_amount - refund_amount |
| payment_method | VARCHAR(50) | Card / Numerar / Transfer bancar / Asigurare privata / CNAS |
| payment_status | VARCHAR(30) | paid / pending / partial / refunded |

## analytics.fct_appointments (Gold Layer)

All columns from stg_appointments plus:

| Column | Type | Description |
|--------|------|-------------|
| net_revenue | NUMERIC | Revenue after refunds |
| insurance_reimbursement | NUMERIC | Insurer contribution |
| doctor_name | VARCHAR | Full doctor name |
| clinic_name | VARCHAR | Full clinic name |
| clinic_city | VARCHAR | City of clinic |
| service_name | VARCHAR | Service performed |
| service_category | VARCHAR | Category of service |
| profitability_margin | NUMERIC | Service-level margin (0–1) |
| wait_tier | VARCHAR | Excellent/Good/Acceptable/Poor |
| time_of_day | VARCHAR | Morning/Midday/Afternoon/Evening |

## analytics.dim_patients (Gold Layer)

All cleaned patient attributes plus:

| Column | Type | Description |
|--------|------|-------------|
| total_visits | INT | Total appointment count |
| completed_visits | INT | Completed appointment count |
| lifetime_value | NUMERIC | Sum of net revenue from this patient |
| first_visit_date | DATE | Date of first completed visit |
| last_visit_date | DATE | Date of most recent completed visit |
| days_since_last_visit | INT | Recency metric |
| churn_risk | VARCHAR | Low / Medium / High |
| engagement_level | VARCHAR | Inactive / Low / Medium / High |
| age_band | VARCHAR | 0-17 / 18-34 / 35-49 / 50-64 / 65+ |
| risk_category | VARCHAR | Low / Medium / High / Critical |
