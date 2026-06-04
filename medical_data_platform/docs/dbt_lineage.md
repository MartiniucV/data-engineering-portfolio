# MedInsight Analytics Platform — dbt Lineage

## Model Dependency Graph

```
raw.appointments ──────────────────────────────────────────────────┐
raw.patients ───────────────────────────────────────────────────┐   │
raw.doctors ──────────────────────────────────────────────────┐ │   │
raw.clinics ────────────────────────────────────────────────┐ │ │   │
raw.services ─────────────────────────────────────────────┐ │ │ │   │
raw.billing ────────────────────────────────────────────┐ │ │ │ │   │
raw.prescriptions ────────────────────────────────────┐ │ │ │ │ │   │
raw.lab_results ────────────────────────────────────┐ │ │ │ │ │ │   │
                                                    │ │ │ │ │ │ │   │
  STAGING (views)                                  │ │ │ │ │ │ │   │
  ┌─────────────────┐                              │ │ │ │ │ │ │   │
  │ stg_lab_results │◄─────────────────────────────┘ │ │ │ │ │ │   │
  │ stg_prescriptions◄──────────────────────────────┘ │ │ │ │ │   │
  │ stg_payments    │◄────────────────────────────────┘ │ │ │ │   │
  │ stg_services    │◄──────────────────────────────────┘ │ │ │   │
  │ stg_clinics     │◄────────────────────────────────────┘ │ │   │
  │ stg_doctors     │◄──────────────────────────────────────┘ │   │
  │ stg_patients    │◄────────────────────────────────────────┘   │
  │ stg_appointments│◄────────────────────────────────────────────┘
  └─────────────────┘
           │
  INTERMEDIATE (views)
  ┌────────────────────────────────────┐
  │ int_appointment_metrics            │◄── stg_appointments + stg_doctors
  │                                    │    + stg_clinics + stg_services
  │                                    │    + stg_payments
  │ int_doctor_metrics                 │◄── int_appointment_metrics + stg_doctors
  │ int_patient_metrics                │◄── int_appointment_metrics + stg_patients
  │ int_revenue_metrics                │◄── stg_payments + stg_appointments
  │                                    │    + stg_clinics
  │ int_operational_metrics            │◄── int_appointment_metrics
  └────────────────────────────────────┘
           │
  MARTS (tables — analytics schema)
  ┌────────────────────────────────────┐
  │ fct_appointments                   │◄── int_appointment_metrics
  │ fct_daily_revenue                  │◄── int_revenue_metrics
  │ fct_doctor_performance             │◄── int_doctor_metrics
  │ fct_patient_retention              │◄── stg_appointments
  │ fct_operational_efficiency         │◄── int_operational_metrics
  │                                    │
  │ dim_doctors                        │◄── int_doctor_metrics
  │ dim_patients                       │◄── int_patient_metrics
  │ dim_services                       │◄── stg_services
  │ dim_clinics                        │◄── stg_clinics + int_appointment_metrics
  └────────────────────────────────────┘
```

## Materialisation Strategy

| Layer | Materialisation | Reason |
|-------|----------------|--------|
| Staging | `view` | Thin transformations; no storage cost |
| Intermediate | `view` | Business logic; computed on-demand by mart queries |
| Marts | `table` | Pre-materialised for dashboard query performance |

## Key dbt Tests (29 total)

| Test Type | Applied To | Count |
|-----------|-----------|-------|
| `not_null` | Primary keys, FK columns, status fields | 12 |
| `unique` | All primary keys | 7 |
| `accepted_values` | status, gender, payment_status | 3 |
| `relationships` | FK to parent tables | 4 |
| Custom expression | base_price ≥ 0 | 3 |

## Macros

| Macro | Purpose |
|-------|---------|
| `generate_schema_name` | Override dbt default to use custom schema names without target prefix |
| `safe_divide` | Null-safe division — returns null instead of divide-by-zero error |
| `date_spine` | Wrapper around dbt_utils.date_spine for calendar generation |
| `generate_surrogate_key` | Wrapper around dbt_utils for composite key hashing |

## Running dbt

```bash
cd dbt

# Install packages
dbt deps

# Compile (check SQL without executing)
dbt compile --profiles-dir .

# Run all models
dbt run --profiles-dir .

# Run specific layer
dbt run --select staging --profiles-dir .
dbt run --select marts --profiles-dir .

# Run single model + dependencies
dbt run --select +fct_appointments --profiles-dir .

# Test all models
dbt test --profiles-dir .

# Generate and serve documentation
dbt docs generate --profiles-dir .
dbt docs serve --profiles-dir .
```
