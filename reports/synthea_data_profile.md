# Synthea CSV Data Profile Report

- Generated: 2026-07-19T18:31:59
- Source directory: `E:\rwe-project\data\synthea_csv`
- Tables: 18

## Dataset Overview

| Table | Rows | Columns | Primary Key |
| --- | ---: | ---: | --- |
| allergies | 1,086 | 15 | (composite - no single surrogate key) |
| careplans | 3,781 | 9 | Id |
| claims | 121,500 | 31 | Id |
| claims_transactions | 1,068,109 | 33 | ID |
| conditions | 40,022 | 7 | (composite - no single surrogate key) |
| devices | 6,384 | 7 | UDI |
| encounters | 66,657 | 15 | Id |
| imaging_studies | 103,045 | 13 | INSTANCE_UID |
| immunizations | 16,711 | 6 | (composite - no single surrogate key) |
| medications | 54,843 | 13 | (composite - no single surrogate key) |
| observations | 831,646 | 9 | (composite - no single surrogate key) |
| organizations | 814 | 11 | Id |
| patients | 1,135 | 28 | Id |
| payer_transitions | 41,168 | 8 | (composite - no single surrogate key) |
| payers | 10 | 22 | Id |
| procedures | 181,797 | 10 | (composite - no single surrogate key) |
| providers | 814 | 13 | Id |
| supplies | 29,208 | 6 | (composite - no single surrogate key) |

## Entity Relationships

| Source Table | Source Column | Target Table | Target Column | Match % | Confidence |
| --- | --- | --- | --- | ---: | --- |
| allergies | ENCOUNTER | encounters | Id | 100.00 | high |
| allergies | PATIENT | patients | Id | 100.00 | high |
| careplans | ENCOUNTER | encounters | Id | 100.00 | high |
| careplans | PATIENT | patients | Id | 100.00 | high |
| claims | APPOINTMENTID | encounters | Id | 100.00 | high |
| claims | PATIENTID | patients | Id | 100.00 | high |
| claims | PRIMARYPATIENTINSURANCEID | payers | Id | 100.00 | high |
| claims | PROVIDERID | providers | Id | 100.00 | high |
| claims | SECONDARYPATIENTINSURANCEID | payers | Id | 100.00 | high |
| claims | SUPERVISINGPROVIDERID | providers | Id | 100.00 | high |
| claims_transactions | APPOINTMENTID | encounters | Id | 100.00 | high |
| claims_transactions | CLAIMID | claims | Id | 100.00 | high |
| claims_transactions | PATIENTID | patients | Id | 100.00 | high |
| claims_transactions | PATIENTINSURANCEID | payer_transitions | MEMBERID | 98.54 | medium |
| claims_transactions | PROVIDERID | providers | Id | 100.00 | high |
| claims_transactions | SUPERVISINGPROVIDERID | providers | Id | 100.00 | high |
| conditions | ENCOUNTER | encounters | Id | 100.00 | high |
| conditions | PATIENT | patients | Id | 100.00 | high |
| devices | ENCOUNTER | encounters | Id | 100.00 | high |
| devices | PATIENT | patients | Id | 100.00 | high |
| encounters | ORGANIZATION | organizations | Id | 100.00 | high |
| encounters | PATIENT | patients | Id | 100.00 | high |
| encounters | PAYER | payers | Id | 100.00 | high |
| encounters | PROVIDER | providers | Id | 100.00 | high |
| imaging_studies | ENCOUNTER | encounters | Id | 100.00 | high |
| imaging_studies | PATIENT | patients | Id | 100.00 | high |
| immunizations | ENCOUNTER | encounters | Id | 100.00 | high |
| immunizations | PATIENT | patients | Id | 100.00 | high |
| medications | ENCOUNTER | encounters | Id | 100.00 | high |
| medications | PATIENT | patients | Id | 100.00 | high |
| medications | PAYER | payers | Id | 100.00 | high |
| observations | ENCOUNTER | encounters | Id | 100.00 | high |
| observations | PATIENT | patients | Id | 100.00 | high |
| payer_transitions | PATIENT | patients | Id | 100.00 | high |
| payer_transitions | PAYER | payers | Id | 100.00 | high |
| payer_transitions | SECONDARY_PAYER | payers | Id | 100.00 | high |
| procedures | ENCOUNTER | encounters | Id | 100.00 | high |
| procedures | PATIENT | patients | Id | 100.00 | high |
| providers | ORGANIZATION | organizations | Id | 100.00 | high |
| supplies | ENCOUNTER | encounters | Id | 100.00 | high |
| supplies | PATIENT | patients | Id | 100.00 | high |

## allergies

- **File:** `allergies.csv`
- **Shape:** 1,086 rows × 15 columns
- **Primary key(s):** (composite - no single surrogate key)

### Columns

| Column | Dtype | Non-Null | Null % | Unique | Unique % | Sample Values |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| START | object | 1,086 | 0.0 | 192 | 17.68 | 2025-04-27, 2025-04-27, 2025-04-27 |
| STOP | float64 | 0 | 100.0 | 0 | 0.0 |  |
| PATIENT | object | 1,086 | 0.0 | 192 | 17.68 | 7cfebcfc-e1cc-2993-d512-9c450d4457b8, 7cfebcfc-e1cc-2993-d512-9c450d4457b8, 7cfebcfc-e1cc-2993-d512-9c450d4457b8 |
| ENCOUNTER | object | 1,086 | 0.0 | 192 | 17.68 | 7cfebcfc-e1cc-2993-ba51-6882b240e26e, 7cfebcfc-e1cc-2993-ba51-6882b240e26e, 7cfebcfc-e1cc-2993-ba51-6882b240e26e |
| CODE | int64 | 1,086 | 0.0 | 22 | 2.03 | 609328004, 1191, 102263004 |
| SYSTEM | object | 1,086 | 0.0 | 2 | 0.18 | SNOMED-CT, RxNorm, SNOMED-CT |
| DESCRIPTION | object | 1,086 | 0.0 | 22 | 2.03 | Allergic disposition (finding), Aspirin, Eggs (edible) (substance) |
| TYPE | object | 1,086 | 0.0 | 2 | 0.18 | allergy, allergy, allergy |
| CATEGORY | object | 1,086 | 0.0 | 3 | 0.28 | environment, medication, food |
| REACTION1 | float64 | 475 | 56.26 | 17 | 3.58 | 247472004.0, 247472004.0, 247472004.0 |
| DESCRIPTION1 | object | 475 | 56.26 | 17 | 3.58 | Wheal (finding), Wheal (finding), Wheal (finding) |
| SEVERITY1 | object | 475 | 56.26 | 3 | 0.63 | MODERATE, MODERATE, MILD |
| REACTION2 | float64 | 274 | 74.77 | 13 | 4.74 | 49727002.0, 300359004.0, 49727002.0 |
| DESCRIPTION2 | object | 274 | 74.77 | 13 | 4.74 | Cough (finding), Finding of vomiting (finding), Cough (finding) |
| SEVERITY2 | object | 274 | 74.77 | 2 | 0.73 | MODERATE, MILD, MODERATE |

### Foreign Keys

- `ENCOUNTER` → `encounters.Id` (100.00% of 1,086 values matched)
- `PATIENT` → `patients.Id` (100.00% of 1,086 values matched)

## careplans

- **File:** `careplans.csv`
- **Shape:** 3,781 rows × 9 columns
- **Primary key(s):** Id

### Columns

| Column | Dtype | Non-Null | Null % | Unique | Unique % | Sample Values |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Id | object | 3,781 | 0.0 | 3,781 | 100.0 | 7cfebcfc-e1cc-2993-d449-76fa52d1c079, bbf5f505-3df2-3cb7-2580-84a9c50fcf78, bbf5f505-3df2-3cb7-7895-18b7df956076 |
| START | object | 3,781 | 0.0 | 3,018 | 79.82 | 2025-04-12, 2021-10-03, 2021-10-31 |
| STOP | object | 1,940 | 48.69 | 1,571 | 80.98 | 2021-12-05, 2024-04-05, 2021-01-19 |
| PATIENT | object | 3,781 | 0.0 | 1,038 | 27.45 | 7cfebcfc-e1cc-2993-d512-9c450d4457b8, bbf5f505-3df2-3cb7-c066-de2487fba44b, bbf5f505-3df2-3cb7-c066-de2487fba44b |
| ENCOUNTER | object | 3,781 | 0.0 | 3,673 | 97.14 | 7cfebcfc-e1cc-2993-c1c1-55f56f2cf27d, bbf5f505-3df2-3cb7-e413-73a1f999a112, bbf5f505-3df2-3cb7-9fb2-e4f9a46fc599 |
| CODE | int64 | 3,781 | 0.0 | 36 | 0.95 | 384758001, 384758001, 773513001 |
| DESCRIPTION | object | 3,781 | 0.0 | 36 | 0.95 | Self-care interventions (procedure), Self-care interventions (procedure), Physiotherapy care plan (record artifact) |
| REASONCODE | float64 | 1,980 | 47.63 | 57 | 2.88 | 44465007.0, 33737001.0, 24079001.0 |
| REASONDESCRIPTION | object | 1,980 | 47.63 | 57 | 2.88 | Sprain of ankle (disorder), Fracture of rib (disorder), Atopic dermatitis (disorder) |

### Foreign Keys

- `ENCOUNTER` → `encounters.Id` (100.00% of 3,781 values matched)
- `PATIENT` → `patients.Id` (100.00% of 3,781 values matched)

## claims

- **File:** `claims.csv`
- **Shape:** 121,500 rows × 31 columns
- **Primary key(s):** Id

### Columns

| Column | Dtype | Non-Null | Null % | Unique | Unique % | Sample Values |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Id | object | 121,500 | 0.0 | 121,500 | 100.0 | 7cfebcfc-e1cc-2993-5d4c-3802d5d4b56d, 7cfebcfc-e1cc-2993-62ca-91fc31a8a240, 7cfebcfc-e1cc-2993-51a2-7ba22c5cdc8c |
| PATIENTID | object | 121,500 | 0.0 | 1,135 | 0.93 | 7cfebcfc-e1cc-2993-d512-9c450d4457b8, 7cfebcfc-e1cc-2993-d512-9c450d4457b8, 7cfebcfc-e1cc-2993-d512-9c450d4457b8 |
| PROVIDERID | object | 121,500 | 0.0 | 738 | 0.61 | 6803c7bc-0723-3c61-9699-466faeb5bb16, 6803c7bc-0723-3c61-9699-466faeb5bb16, 6803c7bc-0723-3c61-9699-466faeb5bb16 |
| PRIMARYPATIENTINSURANCEID | object | 110,046 | 9.43 | 10 | 0.01 | b046940f-1664-3047-bca7-dfa76be352a4, b046940f-1664-3047-bca7-dfa76be352a4, b046940f-1664-3047-bca7-dfa76be352a4 |
| SECONDARYPATIENTINSURANCEID | object | 37,336 | 69.27 | 2 | 0.01 | b046940f-1664-3047-bca7-dfa76be352a4, b046940f-1664-3047-bca7-dfa76be352a4, b046940f-1664-3047-bca7-dfa76be352a4 |
| DEPARTMENTID | int64 | 121,500 | 0.0 | 11 | 0.01 | 10, 10, 10 |
| PATIENTDEPARTMENTID | int64 | 121,500 | 0.0 | 11 | 0.01 | 10, 10, 10 |
| DIAGNOSIS1 | int64 | 121,500 | 0.0 | 211 | 0.17 | 314529007, 410620009, 314529007 |
| DIAGNOSIS2 | float64 | 34,689 | 71.45 | 191 | 0.55 | 444814009.0, 65363002.0, 65363002.0 |
| DIAGNOSIS3 | float64 | 11,700 | 90.37 | 117 | 1.0 | 44465007.0, 44465007.0, 33737001.0 |
| DIAGNOSIS4 | float64 | 3,507 | 97.11 | 63 | 1.8 | 66383009.0, 80583007.0, 80583007.0 |
| DIAGNOSIS5 | float64 | 986 | 99.19 | 37 | 3.75 | 66383009.0, 66383009.0, 424393004.0 |
| DIAGNOSIS6 | float64 | 306 | 99.75 | 23 | 7.52 | 66383009.0, 840539006.0, 840539006.0 |
| DIAGNOSIS7 | float64 | 75 | 99.94 | 11 | 14.67 | 36955009.0, 840539006.0, 57676002.0 |
| DIAGNOSIS8 | float64 | 25 | 99.98 | 6 | 24.0 | 840539006.0, 386661006.0, 840539006.0 |
| REFERRINGPROVIDERID | float64 | 0 | 100.0 | 0 | 0.0 |  |
| APPOINTMENTID | object | 121,500 | 0.0 | 66,657 | 54.86 | 7cfebcfc-e1cc-2993-0235-31263f549c60, 7cfebcfc-e1cc-2993-f4ac-81beb3739994, 7cfebcfc-e1cc-2993-b1f9-71d4df3db3d8 |
| CURRENTILLNESSDATE | object | 121,500 | 0.0 | 52,814 | 43.47 | 2023-12-18T13:31:25Z, 2024-01-22T13:31:25Z, 2024-03-25T13:31:25Z |
| SERVICEDATE | object | 121,500 | 0.0 | 65,716 | 54.09 | 2023-12-18T13:31:25Z, 2024-01-22T13:31:25Z, 2024-03-25T13:31:25Z |
| SUPERVISINGPROVIDERID | object | 121,500 | 0.0 | 738 | 0.61 | 6803c7bc-0723-3c61-9699-466faeb5bb16, 6803c7bc-0723-3c61-9699-466faeb5bb16, 6803c7bc-0723-3c61-9699-466faeb5bb16 |
| STATUS1 | object | 121,500 | 0.0 | 2 | 0.0 | CLOSED, CLOSED, CLOSED |
| STATUS2 | object | 84,162 | 30.73 | 2 | 0.0 | CLOSED, CLOSED, CLOSED |
| STATUSP | object | 121,500 | 0.0 | 2 | 0.0 | CLOSED, CLOSED, CLOSED |
| OUTSTANDING1 | float64 | 121,500 | 0.0 | 11 | 0.01 | 0.0, 0.0, 0.0 |
| OUTSTANDING2 | float64 | 84,162 | 30.73 | 9 | 0.01 | 0.0, 0.0, 0.0 |
| OUTSTANDINGP | float64 | 121,500 | 0.0 | 9 | 0.01 | 0.0, 0.0, 0.0 |
| LASTBILLEDDATE1 | object | 121,500 | 0.0 | 66,586 | 54.8 | 2023-12-18T13:46:25Z, 2024-01-22T13:46:25Z, 2024-03-25T13:46:25Z |
| LASTBILLEDDATE2 | object | 84,162 | 30.73 | 49,893 | 59.28 | 2023-12-18T13:46:25Z, 2024-01-22T13:46:25Z, 2024-03-25T13:46:25Z |
| LASTBILLEDDATEP | object | 121,500 | 0.0 | 66,586 | 54.8 | 2023-12-18T13:46:25Z, 2024-01-22T13:46:25Z, 2024-03-25T13:46:25Z |
| HEALTHCARECLAIMTYPEID1 | int64 | 121,500 | 0.0 | 2 | 0.0 | 1, 1, 1 |
| HEALTHCARECLAIMTYPEID2 | int64 | 121,500 | 0.0 | 3 | 0.0 | 1, 1, 1 |

### Foreign Keys

- `APPOINTMENTID` → `encounters.Id` (100.00% of 121,500 values matched)
- `PATIENTID` → `patients.Id` (100.00% of 121,500 values matched)
- `PRIMARYPATIENTINSURANCEID` → `payers.Id` (100.00% of 110,046 values matched)
- `PROVIDERID` → `providers.Id` (100.00% of 121,500 values matched)
- `SECONDARYPATIENTINSURANCEID` → `payers.Id` (100.00% of 37,336 values matched)
- `SUPERVISINGPROVIDERID` → `providers.Id` (100.00% of 121,500 values matched)

## claims_transactions

- **File:** `claims_transactions.csv`
- **Shape:** 1,068,109 rows × 33 columns
- **Primary key(s):** ID

### Columns

| Column | Dtype | Non-Null | Null % | Unique | Unique % | Sample Values |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| ID | object | 1,068,109 | 0.0 | 1,068,109 | 100.0 | f5132b1c-4f79-a4d8-88dd-372161b81227, ea2a5638-9ef3-49b1-11c6-6e42c370244f, d46aac71-3de6-9363-2392-dc8586e0489e |
| CLAIMID | object | 1,068,109 | 0.0 | 121,500 | 11.38 | 7cfebcfc-e1cc-2993-5d4c-3802d5d4b56d, 7cfebcfc-e1cc-2993-5d4c-3802d5d4b56d, 7cfebcfc-e1cc-2993-5d4c-3802d5d4b56d |
| CHARGEID | int64 | 1,068,109 | 0.0 | 1,068,109 | 100.0 | 0, 1, 2 |
| PATIENTID | object | 1,068,109 | 0.0 | 1,135 | 0.11 | 7cfebcfc-e1cc-2993-d512-9c450d4457b8, 7cfebcfc-e1cc-2993-d512-9c450d4457b8, 7cfebcfc-e1cc-2993-d512-9c450d4457b8 |
| TYPE | object | 1,068,109 | 0.0 | 4 | 0.0 | CHARGE, TRANSFEROUT, TRANSFERIN |
| AMOUNT | float64 | 490,690 | 54.06 | 36,776 | 7.49 | 136.8, 136.8, 136.0 |
| METHOD | object | 406,737 | 61.92 | 5 | 0.0 | CASH, CC, CHECK |
| FROMDATE | object | 1,068,109 | 0.0 | 182,641 | 17.1 | 2023-12-18T13:31:25Z, 2023-12-18T13:31:25Z, 2023-12-18T13:31:25Z |
| TODATE | object | 1,068,109 | 0.0 | 204,367 | 19.13 | 2023-12-18T13:46:25Z, 2023-12-18T13:46:25Z, 2023-12-18T13:46:25Z |
| PLACEOFSERVICE | object | 1,068,109 | 0.0 | 738 | 0.07 | b4e81d20-a3d6-39db-8b04-bcc4ab5de7b2, b4e81d20-a3d6-39db-8b04-bcc4ab5de7b2, b4e81d20-a3d6-39db-8b04-bcc4ab5de7b2 |
| PROCEDURECODE | int64 | 1,068,109 | 0.0 | 683 | 0.06 | 410620009, 410620009, 410620009 |
| MODIFIER1 | float64 | 0 | 100.0 | 0 | 0.0 |  |
| MODIFIER2 | float64 | 0 | 100.0 | 0 | 0.0 |  |
| DIAGNOSISREF1 | int64 | 1,068,109 | 0.0 | 1 | 0.0 | 1, 1, 1 |
| DIAGNOSISREF2 | float64 | 345,648 | 67.64 | 1 | 0.0 | 2.0, 2.0, 2.0 |
| DIAGNOSISREF3 | float64 | 105,345 | 90.14 | 1 | 0.0 | 3.0, 3.0, 3.0 |
| DIAGNOSISREF4 | float64 | 29,694 | 97.22 | 1 | 0.0 | 4.0, 4.0, 4.0 |
| UNITS | int64 | 1,068,109 | 0.0 | 1 | 0.0 | 1, 1, 1 |
| DEPARTMENTID | int64 | 1,068,109 | 0.0 | 11 | 0.0 | 10, 10, 10 |
| NOTES | object | 1,068,109 | 0.0 | 697 | 0.07 | Well child visit (procedure), Well child visit (procedure), Well child visit (procedure) |
| UNITAMOUNT | float64 | 1,068,109 | 0.0 | 26,164 | 2.45 | 136.8, 0.0, 0.0 |
| TRANSFEROUTID | float64 | 170,682 | 84.02 | 170,682 | 100.0 | 1.0, 6.0, 11.0 |
| TRANSFERTYPE | object | 490,690 | 54.06 | 3 | 0.0 | 1, p, 1 |
| PAYMENTS | float64 | 1,068,109 | 0.0 | 37,741 | 3.53 | 0.0, 0.0, 0.0 |
| ADJUSTMENTS | float64 | 1,068,109 | 0.0 | 1 | 0.0 | 0.0, 0.0, 0.0 |
| TRANSFERS | float64 | 341,364 | 68.04 | 15,231 | 4.46 | 136.8, 136.8, 136.0 |
| OUTSTANDING | float64 | 1,068,109 | 0.0 | 15,993 | 1.5 | 0.0, 136.8, 136.8 |
| APPOINTMENTID | object | 1,068,109 | 0.0 | 66,657 | 6.24 | 7cfebcfc-e1cc-2993-0235-31263f549c60, 7cfebcfc-e1cc-2993-0235-31263f549c60, 7cfebcfc-e1cc-2993-0235-31263f549c60 |
| LINENOTE | float64 | 0 | 100.0 | 0 | 0.0 |  |
| PATIENTINSURANCEID | object | 1,017,619 | 4.73 | 11,755 | 1.16 | 7cfebcfc-e1cc-2993-182c-0f1e485508d7, 7cfebcfc-e1cc-2993-182c-0f1e485508d7, 7cfebcfc-e1cc-2993-182c-0f1e485508d7 |
| FEESCHEDULEID | int64 | 1,068,109 | 0.0 | 1 | 0.0 | 1, 1, 1 |
| PROVIDERID | object | 1,068,109 | 0.0 | 738 | 0.07 | 6803c7bc-0723-3c61-9699-466faeb5bb16, 6803c7bc-0723-3c61-9699-466faeb5bb16, 6803c7bc-0723-3c61-9699-466faeb5bb16 |
| SUPERVISINGPROVIDERID | object | 1,068,109 | 0.0 | 738 | 0.07 | 6803c7bc-0723-3c61-9699-466faeb5bb16, 6803c7bc-0723-3c61-9699-466faeb5bb16, 6803c7bc-0723-3c61-9699-466faeb5bb16 |

### Foreign Keys

- `APPOINTMENTID` → `encounters.Id` (100.00% of 1,068,109 values matched)
- `CLAIMID` → `claims.Id` (100.00% of 1,068,109 values matched)
- `PATIENTID` → `patients.Id` (100.00% of 1,068,109 values matched)
- `PROVIDERID` → `providers.Id` (100.00% of 1,068,109 values matched)
- `SUPERVISINGPROVIDERID` → `providers.Id` (100.00% of 1,068,109 values matched)
- `PATIENTINSURANCEID` → `payer_transitions.MEMBERID` (98.54% of 1,017,619 values matched)

## conditions

- **File:** `conditions.csv`
- **Shape:** 40,022 rows × 7 columns
- **Primary key(s):** (composite - no single surrogate key)

### Columns

| Column | Dtype | Non-Null | Null % | Unique | Unique % | Sample Values |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| START | object | 40,022 | 0.0 | 10,047 | 25.1 | 2023-12-18, 2024-03-25, 2024-11-25 |
| STOP | object | 29,626 | 25.98 | 6,423 | 21.68 | 2024-01-22, 2024-08-26, 2026-05-25 |
| PATIENT | object | 40,022 | 0.0 | 1,135 | 2.84 | 7cfebcfc-e1cc-2993-d512-9c450d4457b8, 7cfebcfc-e1cc-2993-d512-9c450d4457b8, 7cfebcfc-e1cc-2993-d512-9c450d4457b8 |
| ENCOUNTER | object | 40,022 | 0.0 | 25,650 | 64.09 | 7cfebcfc-e1cc-2993-0235-31263f549c60, 7cfebcfc-e1cc-2993-b1f9-71d4df3db3d8, 7cfebcfc-e1cc-2993-6f1c-29f38b34bab7 |
| SYSTEM | object | 40,022 | 0.0 | 1 | 0.0 | http://snomed.info/sct, http://snomed.info/sct, http://snomed.info/sct |
| CODE | int64 | 40,022 | 0.0 | 264 | 0.66 | 314529007, 314529007, 314529007 |
| DESCRIPTION | object | 40,022 | 0.0 | 264 | 0.66 | Medication review due (situation), Medication review due (situation), Medication review due (situation) |

### Foreign Keys

- `ENCOUNTER` → `encounters.Id` (100.00% of 40,022 values matched)
- `PATIENT` → `patients.Id` (100.00% of 40,022 values matched)

## devices

- **File:** `devices.csv`
- **Shape:** 6,384 rows × 7 columns
- **Primary key(s):** UDI

### Columns

| Column | Dtype | Non-Null | Null % | Unique | Unique % | Sample Values |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| START | object | 6,384 | 0.0 | 5,908 | 92.54 | 2025-10-26T00:15:52Z, 2025-01-15T10:15:07Z, 2025-01-20T15:14:24Z |
| STOP | object | 4,103 | 35.73 | 3,832 | 93.4 | 2025-10-26T00:15:52Z, 2025-01-15T11:43:43Z, 2026-01-21T09:40:53Z |
| PATIENT | object | 6,384 | 0.0 | 1,021 | 15.99 | bbf5f505-3df2-3cb7-c066-de2487fba44b, 0cebaa05-dec4-3d8d-c216-65923479dd5a, 0cebaa05-dec4-3d8d-c216-65923479dd5a |
| ENCOUNTER | object | 6,384 | 0.0 | 5,402 | 84.62 | bbf5f505-3df2-3cb7-1b89-76198e64ecda, 0cebaa05-dec4-3d8d-9976-7de733884d70, 0cebaa05-dec4-3d8d-7308-567018e687d7 |
| CODE | int64 | 6,384 | 0.0 | 29 | 0.45 | 706298007, 225738002, 225738002 |
| DESCRIPTION | object | 6,384 | 0.0 | 29 | 0.45 | Dental x-ray system (physical object), Operating room (environment), Operating room (environment) |
| UDI | object | 6,384 | 0.0 | 6,384 | 100.0 | (01)34834339868074(11)251005(17)501020(10)855288023398284857(21)7074073870673454310, (01)33737821096986(11)241225(17)500109(10)40988708592308087(21)72896817894170, (01)37720768061240(11)251230(17)500114(10)945983955068785426(21)892271 |

### Foreign Keys

- `ENCOUNTER` → `encounters.Id` (100.00% of 6,384 values matched)
- `PATIENT` → `patients.Id` (100.00% of 6,384 values matched)

## encounters

- **File:** `encounters.csv`
- **Shape:** 66,657 rows × 15 columns
- **Primary key(s):** Id

### Columns

| Column | Dtype | Non-Null | Null % | Unique | Unique % | Sample Values |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Id | object | 66,657 | 0.0 | 66,657 | 100.0 | 7cfebcfc-e1cc-2993-0235-31263f549c60, 7cfebcfc-e1cc-2993-f4ac-81beb3739994, 7cfebcfc-e1cc-2993-b1f9-71d4df3db3d8 |
| START | object | 66,657 | 0.0 | 65,716 | 98.59 | 2023-12-18T13:31:25Z, 2024-01-22T13:31:25Z, 2024-03-25T13:31:25Z |
| STOP | object | 66,657 | 0.0 | 66,583 | 99.89 | 2023-12-18T13:46:25Z, 2024-01-22T13:46:25Z, 2024-03-25T13:46:25Z |
| PATIENT | object | 66,657 | 0.0 | 1,135 | 1.7 | 7cfebcfc-e1cc-2993-d512-9c450d4457b8, 7cfebcfc-e1cc-2993-d512-9c450d4457b8, 7cfebcfc-e1cc-2993-d512-9c450d4457b8 |
| ORGANIZATION | object | 66,657 | 0.0 | 738 | 1.11 | b4e81d20-a3d6-39db-8b04-bcc4ab5de7b2, b4e81d20-a3d6-39db-8b04-bcc4ab5de7b2, b4e81d20-a3d6-39db-8b04-bcc4ab5de7b2 |
| PROVIDER | object | 66,657 | 0.0 | 738 | 1.11 | 6803c7bc-0723-3c61-9699-466faeb5bb16, 6803c7bc-0723-3c61-9699-466faeb5bb16, 6803c7bc-0723-3c61-9699-466faeb5bb16 |
| PAYER | object | 66,657 | 0.0 | 10 | 0.02 | b046940f-1664-3047-bca7-dfa76be352a4, b046940f-1664-3047-bca7-dfa76be352a4, b046940f-1664-3047-bca7-dfa76be352a4 |
| ENCOUNTERCLASS | object | 66,657 | 0.0 | 10 | 0.02 | wellness, wellness, wellness |
| CODE | int64 | 66,657 | 0.0 | 55 | 0.08 | 410620009, 410620009, 410620009 |
| DESCRIPTION | object | 66,657 | 0.0 | 55 | 0.08 | Well child visit (procedure), Well child visit (procedure), Well child visit (procedure) |
| BASE_ENCOUNTER_COST | float64 | 66,657 | 0.0 | 11 | 0.02 | 136.8, 136.8, 136.8 |
| TOTAL_CLAIM_COST | float64 | 66,657 | 0.0 | 17,355 | 26.04 | 347.38, 1135.6, 816.8 |
| PAYER_COVERAGE | float64 | 66,657 | 0.0 | 17,453 | 26.18 | 0.0, 0.0, 0.0 |
| REASONCODE | float64 | 42,638 | 36.03 | 152 | 0.36 | 444814009.0, 102263004.0, 609328004.0 |
| REASONDESCRIPTION | object | 42,638 | 36.03 | 152 | 0.36 | Viral sinusitis (disorder), Eggs (edible) (substance), Allergic disposition (finding) |

### Foreign Keys

- `ORGANIZATION` → `organizations.Id` (100.00% of 66,657 values matched)
- `PATIENT` → `patients.Id` (100.00% of 66,657 values matched)
- `PAYER` → `payers.Id` (100.00% of 66,657 values matched)
- `PROVIDER` → `providers.Id` (100.00% of 66,657 values matched)

## imaging_studies

- **File:** `imaging_studies.csv`
- **Shape:** 103,045 rows × 13 columns
- **Primary key(s):** INSTANCE_UID

### Columns

| Column | Dtype | Non-Null | Null % | Unique | Unique % | Sample Values |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Id | object | 103,045 | 0.0 | 5,435 | 5.27 | bbf5f505-3df2-3cb7-e90d-5d88744b09b9, bbf5f505-3df2-3cb7-d26d-4e603690dbc1, 0cebaa05-dec4-3d8d-61b9-e91e17a88223 |
| DATE | object | 103,045 | 0.0 | 5,386 | 5.23 | 2024-03-03T22:15:32Z, 2025-10-26T00:15:52Z, 2026-01-21T09:40:53Z |
| PATIENT | object | 103,045 | 0.0 | 968 | 0.94 | bbf5f505-3df2-3cb7-c066-de2487fba44b, bbf5f505-3df2-3cb7-c066-de2487fba44b, 0cebaa05-dec4-3d8d-c216-65923479dd5a |
| ENCOUNTER | object | 103,045 | 0.0 | 4,799 | 4.66 | bbf5f505-3df2-3cb7-06e7-7c6bb407aa45, bbf5f505-3df2-3cb7-1b89-76198e64ecda, 0cebaa05-dec4-3d8d-0127-70978aee5618 |
| SERIES_UID | object | 103,045 | 0.0 | 5,435 | 5.27 | 1.2.840.99999999.1.86838847.1709504132360, 1.2.840.99999999.1.58909553.1761437752360, 1.2.840.99999999.1.67341731.1768988453627 |
| BODYSITE_CODE | int64 | 103,045 | 0.0 | 13 | 0.01 | 51185008, 700016008, 700016008 |
| BODYSITE_DESCRIPTION | object | 103,045 | 0.0 | 13 | 0.01 | Thoracic structure (body structure), Structure of region of internal part of mouth (body structure), Structure of region of internal part of mouth (body structure) |
| MODALITY_CODE | object | 103,045 | 0.0 | 6 | 0.01 | DX, DX, DX |
| MODALITY_DESCRIPTION | object | 103,045 | 0.0 | 6 | 0.01 | Digital Radiography, Digital Radiography, Digital Radiography |
| INSTANCE_UID | object | 103,045 | 0.0 | 103,045 | 100.0 | 1.2.840.99999999.1.1.73251723.1709504132360, 1.2.840.99999999.1.1.65204181.1761437752360, 1.2.840.99999999.1.1.39551684.1768988453627 |
| SOP_CODE | object | 103,045 | 0.0 | 7 | 0.01 | 1.2.840.10008.5.1.4.1.1.1.1, 1.2.840.10008.5.1.4.1.1.1.3, 1.2.840.10008.5.1.4.1.1.1.3 |
| SOP_DESCRIPTION | object | 103,045 | 0.0 | 8 | 0.01 | Digital X-Ray Image Storage, Digital Intra-Oral X-Ray Image Storage - For Presentation, Digital Intra-Oral X-Ray Image Storage - For Presentation |
| PROCEDURE_CODE | int64 | 103,045 | 0.0 | 17 | 0.02 | 399208008, 241046008, 241046008 |

### Foreign Keys

- `ENCOUNTER` → `encounters.Id` (100.00% of 103,045 values matched)
- `PATIENT` → `patients.Id` (100.00% of 103,045 values matched)

## immunizations

- **File:** `immunizations.csv`
- **Shape:** 16,711 rows × 6 columns
- **Primary key(s):** (composite - no single surrogate key)

### Columns

| Column | Dtype | Non-Null | Null % | Unique | Unique % | Sample Values |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| DATE | object | 16,711 | 0.0 | 11,382 | 68.11 | 2023-12-18T13:31:25Z, 2024-01-22T13:31:25Z, 2024-03-25T13:31:25Z |
| PATIENT | object | 16,711 | 0.0 | 1,132 | 6.77 | 7cfebcfc-e1cc-2993-d512-9c450d4457b8, 7cfebcfc-e1cc-2993-d512-9c450d4457b8, 7cfebcfc-e1cc-2993-d512-9c450d4457b8 |
| ENCOUNTER | object | 16,711 | 0.0 | 11,477 | 68.68 | 7cfebcfc-e1cc-2993-0235-31263f549c60, 7cfebcfc-e1cc-2993-f4ac-81beb3739994, 7cfebcfc-e1cc-2993-b1f9-71d4df3db3d8 |
| CODE | int64 | 16,711 | 0.0 | 22 | 0.13 | 8, 8, 49 |
| DESCRIPTION | object | 16,711 | 0.0 | 25 | 0.15 | Hep B  adolescent or pediatric, Hep B  adolescent or pediatric, Hib (PRP-OMP) |
| BASE_COST | float64 | 16,711 | 0.0 | 1 | 0.01 | 136.0, 136.0, 136.0 |

### Foreign Keys

- `ENCOUNTER` → `encounters.Id` (100.00% of 16,711 values matched)
- `PATIENT` → `patients.Id` (100.00% of 16,711 values matched)

## medications

- **File:** `medications.csv`
- **Shape:** 54,843 rows × 13 columns
- **Primary key(s):** (composite - no single surrogate key)

### Columns

| Column | Dtype | Non-Null | Null % | Unique | Unique % | Sample Values |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| START | object | 54,843 | 0.0 | 33,237 | 60.6 | 2025-04-27T15:04:26Z, 2025-04-27T15:04:26Z, 2021-06-05T22:15:32Z |
| STOP | object | 51,956 | 5.26 | 31,650 | 60.92 | 2021-06-19T22:15:32Z, 2021-10-02T03:00:32Z, 2021-12-04T22:15:32Z |
| PATIENT | object | 54,843 | 0.0 | 1,105 | 2.01 | 7cfebcfc-e1cc-2993-d512-9c450d4457b8, 7cfebcfc-e1cc-2993-d512-9c450d4457b8, bbf5f505-3df2-3cb7-c066-de2487fba44b |
| PAYER | object | 54,843 | 0.0 | 10 | 0.02 | b046940f-1664-3047-bca7-dfa76be352a4, b046940f-1664-3047-bca7-dfa76be352a4, 734afbd6-4794-363b-9bc0-6a3981533ed5 |
| ENCOUNTER | object | 54,843 | 0.0 | 29,875 | 54.47 | 7cfebcfc-e1cc-2993-ba51-6882b240e26e, 7cfebcfc-e1cc-2993-ba51-6882b240e26e, bbf5f505-3df2-3cb7-945d-dfc8a69601f4 |
| CODE | int64 | 54,843 | 0.0 | 252 | 0.46 | 1014676, 1870230, 198405 |
| DESCRIPTION | object | 54,843 | 0.0 | 263 | 0.48 | cetirizine hydrochloride 5 MG Oral Tablet, NDA020800 0.3 ML Epinephrine 1 MG/ML Auto-Injector, Ibuprofen 100 MG Oral Tablet |
| BASE_COST | float64 | 54,843 | 0.0 | 6,834 | 12.46 | 229.32, 53.91, 113.34 |
| PAYER_COVERAGE | float64 | 54,843 | 0.0 | 4,939 | 9.01 | 0.0, 0.0, 90.67 |
| DISPENSES | int64 | 54,843 | 0.0 | 416 | 0.76 | 14, 14, 1 |
| TOTALCOST | float64 | 54,843 | 0.0 | 8,133 | 14.83 | 3210.48, 754.74, 113.34 |
| REASONCODE | float64 | 45,185 | 17.61 | 58 | 0.13 | 103697008.0, 444814009.0, 103697008.0 |
| REASONDESCRIPTION | object | 45,185 | 17.61 | 58 | 0.13 | Patient referral for dental care (procedure), Viral sinusitis (disorder), Patient referral for dental care (procedure) |

### Foreign Keys

- `ENCOUNTER` → `encounters.Id` (100.00% of 54,843 values matched)
- `PATIENT` → `patients.Id` (100.00% of 54,843 values matched)
- `PAYER` → `payers.Id` (100.00% of 54,843 values matched)

## observations

- **File:** `observations.csv`
- **Shape:** 831,646 rows × 9 columns
- **Primary key(s):** (composite - no single surrogate key)

### Columns

| Column | Dtype | Non-Null | Null % | Unique | Unique % | Sample Values |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| DATE | object | 831,646 | 0.0 | 86,694 | 10.42 | 2023-12-18T13:31:25Z, 2023-12-18T13:31:25Z, 2023-12-18T13:31:25Z |
| PATIENT | object | 831,646 | 0.0 | 1,135 | 0.14 | 7cfebcfc-e1cc-2993-d512-9c450d4457b8, 7cfebcfc-e1cc-2993-d512-9c450d4457b8, 7cfebcfc-e1cc-2993-d512-9c450d4457b8 |
| ENCOUNTER | object | 801,247 | 3.66 | 36,203 | 4.52 | 7cfebcfc-e1cc-2993-0235-31263f549c60, 7cfebcfc-e1cc-2993-0235-31263f549c60, 7cfebcfc-e1cc-2993-0235-31263f549c60 |
| CATEGORY | object | 801,247 | 3.66 | 8 | 0.0 | vital-signs, vital-signs, vital-signs |
| CODE | object | 831,646 | 0.0 | 273 | 0.03 | 8302-2, 72514-3, 29463-7 |
| DESCRIPTION | object | 831,646 | 0.0 | 274 | 0.03 | Body Height, Pain severity - 0-10 verbal numeric rating [Score] - Reported, Body Weight |
| VALUE | object | 831,646 | 0.0 | 6,902 | 0.83 | 53.8, 2.0, 5.0 |
| UNITS | object | 606,475 | 27.08 | 50 | 0.01 | cm, {score}, kg |
| TYPE | object | 831,646 | 0.0 | 2 | 0.0 | numeric, numeric, numeric |

### Foreign Keys

- `ENCOUNTER` → `encounters.Id` (100.00% of 801,247 values matched)
- `PATIENT` → `patients.Id` (100.00% of 831,646 values matched)

## organizations

- **File:** `organizations.csv`
- **Shape:** 814 rows × 11 columns
- **Primary key(s):** Id

### Columns

| Column | Dtype | Non-Null | Null % | Unique | Unique % | Sample Values |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Id | object | 814 | 0.0 | 814 | 100.0 | 74ab949d-17ac-3309-83a0-13b4405c66aa, 588f6ce6-b8db-3588-8189-29db2680a313, 324b4137-57a0-3ae0-89db-1c33f57ae0c1 |
| NAME | object | 814 | 0.0 | 744 | 91.4 | Fitchburg Outpatient Clinic, BOSTON HEALTH CARE FOR THE HOMELESS PROGRAM INC, LOWN ACQUISITION LLC |
| ADDRESS | object | 814 | 0.0 | 768 | 94.35 | 881 Main Street, 461 WALNUT AVE, 134 NORTH ST |
| CITY | object | 814 | 0.0 | 250 | 30.71 | Fitchburg, JAMAICA PLAIN, NORTH READING |
| STATE | object | 814 | 0.0 | 1 | 0.12 | MA, MA, MA |
| ZIP | int64 | 814 | 0.0 | 758 | 93.12 | 1420, 21302331, 18641315 |
| LAT | float64 | 814 | 0.0 | 727 | 89.31 | 42.586487, 42.3115876, 42.5892341 |
| LON | float64 | 814 | 0.0 | 727 | 89.31 | -71.80521, -71.09800136347226, -71.10546522083789 |
| PHONE | object | 814 | 0.0 | 764 | 93.86 | 978-342-9781 Or 978-342-9781, 8576541550, 7818262393 |
| REVENUE | float64 | 814 | 0.0 | 1 | 0.12 | 0.0, 0.0, 0.0 |
| UTILIZATION | int64 | 814 | 0.0 | 339 | 41.65 | 1921, 89, 2 |

## patients

- **File:** `patients.csv`
- **Shape:** 1,135 rows × 28 columns
- **Primary key(s):** Id

### Columns

| Column | Dtype | Non-Null | Null % | Unique | Unique % | Sample Values |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Id | object | 1,135 | 0.0 | 1,135 | 100.0 | 7cfebcfc-e1cc-2993-d512-9c450d4457b8, bbf5f505-3df2-3cb7-c066-de2487fba44b, 0cebaa05-dec4-3d8d-c216-65923479dd5a |
| BIRTHDATE | object | 1,135 | 0.0 | 986 | 86.87 | 2023-12-18, 2020-11-08, 2016-01-06 |
| DEATHDATE | object | 135 | 88.11 | 135 | 100.0 | 1959-12-26, 2014-01-13, 2009-03-13 |
| SSN | object | 1,135 | 0.0 | 1,135 | 100.0 | 999-85-5286, 999-54-1879, 999-90-8669 |
| DRIVERS | object | 916 | 19.3 | 911 | 99.45 | S99967455, S99913223, S99966668 |
| PASSPORT | object | 856 | 24.58 | 856 | 100.0 | X84352191X, X52331751X, X81510220X |
| PREFIX | object | 887 | 21.85 | 3 | 0.34 | Mr., Mrs., Mr. |
| FIRST | object | 1,135 | 0.0 | 970 | 85.46 | Harlan808, Hilde556, Rickey821 |
| MIDDLE | object | 900 | 20.7 | 800 | 88.89 | Kory651, Curt84, Suzan149 |
| LAST | object | 1,135 | 0.0 | 484 | 42.64 | Upton904, Parker433, Hickle134 |
| SUFFIX | object | 10 | 99.12 | 2 | 20.0 | JD, MD, JD |
| MAIDEN | object | 311 | 72.6 | 242 | 77.81 | Graham902, Yundt842, Roob72 |
| MARITAL | object | 737 | 35.07 | 4 | 0.54 | M, M, M |
| RACE | object | 1,135 | 0.0 | 6 | 0.53 | white, white, white |
| ETHNICITY | object | 1,135 | 0.0 | 2 | 0.18 | nonhispanic, nonhispanic, nonhispanic |
| GENDER | object | 1,135 | 0.0 | 2 | 0.18 | M, F, M |
| BIRTHPLACE | object | 1,135 | 0.0 | 329 | 28.99 | Wenham  Massachusetts  US, Tewksbury  Massachusetts  US, Cambridge  Massachusetts  US |
| ADDRESS | object | 1,135 | 0.0 | 1,135 | 100.0 | 902 Block Camp, 634 Bashirian Stravenue, 465 Ferry Burg |
| CITY | object | 1,135 | 0.0 | 264 | 23.26 | Millis, Chelsea, Southbridge |
| STATE | object | 1,135 | 0.0 | 1 | 0.09 | Massachusetts, Massachusetts, Massachusetts |
| COUNTY | object | 1,135 | 0.0 | 14 | 1.23 | Norfolk County, Suffolk County, Worcester County |
| FIPS | float64 | 841 | 25.9 | 14 | 1.66 | 25017.0, 25027.0, 25005.0 |
| ZIP | int64 | 1,135 | 0.0 | 249 | 21.94 | 0, 2149, 1550 |
| LAT | float64 | 1,135 | 0.0 | 1,135 | 100.0 | 42.21887836645007, 42.447859152244014, 42.08139611517157 |
| LON | float64 | 1,135 | 0.0 | 1,135 | 100.0 | -71.40720288626291, -71.06310575731543, -72.01115119355954 |
| HEALTHCARE_EXPENSES | float64 | 1,135 | 0.0 | 1,131 | 99.65 | 7577.28, 10409.94, 16353.8 |
| HEALTHCARE_COVERAGE | float64 | 1,135 | 0.0 | 1,060 | 93.39 | 0.0, 18714.7, 12334.0 |
| INCOME | int64 | 1,135 | 0.0 | 997 | 87.84 | 128032, 46755, 135549 |

## payer_transitions

- **File:** `payer_transitions.csv`
- **Shape:** 41,168 rows × 8 columns
- **Primary key(s):** (composite - no single surrogate key)

### Columns

| Column | Dtype | Non-Null | Null % | Unique | Unique % | Sample Values |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| PATIENT | object | 41,168 | 0.0 | 1,127 | 2.74 | 7cfebcfc-e1cc-2993-d512-9c450d4457b8, 7cfebcfc-e1cc-2993-d512-9c450d4457b8, 7cfebcfc-e1cc-2993-d512-9c450d4457b8 |
| MEMBERID | object | 30,871 | 25.01 | 24,924 | 80.74 | 7cfebcfc-e1cc-2993-182c-0f1e485508d7, 7cfebcfc-e1cc-2993-182c-0f1e485508d7, 7cfebcfc-e1cc-2993-182c-0f1e485508d7 |
| START_DATE | object | 41,168 | 0.0 | 36,898 | 89.63 | 2023-12-18T13:31:25Z, 2024-12-23T13:31:25Z, 2025-12-22T13:31:25Z |
| END_DATE | object | 41,168 | 0.0 | 37,005 | 89.89 | 2024-12-23T13:31:25Z, 2025-12-22T13:31:25Z, 2026-12-18T13:31:25Z |
| PAYER | object | 41,168 | 0.0 | 10 | 0.02 | b046940f-1664-3047-bca7-dfa76be352a4, b046940f-1664-3047-bca7-dfa76be352a4, b046940f-1664-3047-bca7-dfa76be352a4 |
| SECONDARY_PAYER | object | 3,646 | 91.14 | 1 | 0.03 | b046940f-1664-3047-bca7-dfa76be352a4, b046940f-1664-3047-bca7-dfa76be352a4, b046940f-1664-3047-bca7-dfa76be352a4 |
| PLAN_OWNERSHIP | object | 30,871 | 25.01 | 3 | 0.01 | Guardian, Guardian, Guardian |
| OWNER_NAME | object | 30,871 | 25.01 | 2,192 | 7.1 | Dennise990 Predovic534, Dennise990 Predovic534, Dennise990 Predovic534 |

### Foreign Keys

- `PATIENT` → `patients.Id` (100.00% of 41,168 values matched)
- `PAYER` → `payers.Id` (100.00% of 41,168 values matched)
- `SECONDARY_PAYER` → `payers.Id` (100.00% of 3,646 values matched)

## payers

- **File:** `payers.csv`
- **Shape:** 10 rows × 22 columns
- **Primary key(s):** Id

### Columns

| Column | Dtype | Non-Null | Null % | Unique | Unique % | Sample Values |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Id | object | 10 | 0.0 | 10 | 100.0 | a735bf55-83e9-331a-899d-a82a60b9f60c, df166300-5a78-3502-a46a-832842197811, d18ef2e6-ef40-324c-be54-34a5ee865625 |
| NAME | object | 10 | 0.0 | 10 | 100.0 | Medicare, Medicaid, Dual Eligible |
| OWNERSHIP | object | 10 | 0.0 | 3 | 30.0 | GOVERNMENT, GOVERNMENT, GOVERNMENT |
| ADDRESS | float64 | 0 | 100.0 | 0 | 0.0 |  |
| CITY | float64 | 0 | 100.0 | 0 | 0.0 |  |
| STATE_HEADQUARTERED | float64 | 0 | 100.0 | 0 | 0.0 |  |
| ZIP | float64 | 0 | 100.0 | 0 | 0.0 |  |
| PHONE | float64 | 0 | 100.0 | 0 | 0.0 |  |
| AMOUNT_COVERED | float64 | 10 | 0.0 | 10 | 100.0 | 79896856.93, 131808583.34, 24264744.91 |
| AMOUNT_UNCOVERED | float64 | 10 | 0.0 | 10 | 100.0 | 3614239.89, 2964894.17, 375125.21 |
| REVENUE | float64 | 10 | 0.0 | 10 | 100.0 | 9841815.9, 1064280.0, 111020.0 |
| COVERED_ENCOUNTERS | int64 | 10 | 0.0 | 10 | 100.0 | 36318, 36348, 6582 |
| UNCOVERED_ENCOUNTERS | int64 | 10 | 0.0 | 2 | 20.0 | 0, 0, 0 |
| COVERED_MEDICATIONS | int64 | 10 | 0.0 | 10 | 100.0 | 39142, 14016, 8133 |
| UNCOVERED_MEDICATIONS | int64 | 10 | 0.0 | 2 | 20.0 | 0, 0, 0 |
| COVERED_PROCEDURES | int64 | 10 | 0.0 | 10 | 100.0 | 82273, 78568, 16835 |
| UNCOVERED_PROCEDURES | int64 | 10 | 0.0 | 2 | 20.0 | 0, 0, 0 |
| COVERED_IMMUNIZATIONS | int64 | 10 | 0.0 | 10 | 100.0 | 5749, 11820, 1196 |
| UNCOVERED_IMMUNIZATIONS | int64 | 10 | 0.0 | 2 | 20.0 | 0, 0, 0 |
| UNIQUE_CUSTOMERS | int64 | 10 | 0.0 | 10 | 100.0 | 338, 471, 95 |
| QOLS_AVG | float64 | 10 | 0.0 | 10 | 100.0 | 0.7367039500946896, 0.9200097823914009, 0.7449096375865372 |
| MEMBER_MONTHS | int64 | 10 | 0.0 | 10 | 100.0 | 59652, 109320, 11532 |

## procedures

- **File:** `procedures.csv`
- **Shape:** 181,797 rows × 10 columns
- **Primary key(s):** (composite - no single surrogate key)

### Columns

| Column | Dtype | Non-Null | Null % | Unique | Unique % | Sample Values |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| START | object | 181,797 | 0.0 | 154,300 | 84.87 | 2024-01-22T13:31:25Z, 2024-08-26T13:31:25Z, 2025-04-27T14:31:25Z |
| STOP | object | 181,797 | 0.0 | 166,082 | 91.36 | 2024-01-22T13:46:25Z, 2024-08-26T13:46:25Z, 2025-04-27T15:04:26Z |
| PATIENT | object | 181,797 | 0.0 | 1,130 | 0.62 | 7cfebcfc-e1cc-2993-d512-9c450d4457b8, 7cfebcfc-e1cc-2993-d512-9c450d4457b8, 7cfebcfc-e1cc-2993-d512-9c450d4457b8 |
| ENCOUNTER | object | 181,797 | 0.0 | 47,672 | 26.22 | 7cfebcfc-e1cc-2993-f4ac-81beb3739994, 7cfebcfc-e1cc-2993-1f87-ea5508293b26, 7cfebcfc-e1cc-2993-ba51-6882b240e26e |
| SYSTEM | object | 181,797 | 0.0 | 1 | 0.0 | http://snomed.info/sct, http://snomed.info/sct, http://snomed.info/sct |
| CODE | int64 | 181,797 | 0.0 | 360 | 0.2 | 430193006, 430193006, 395142003 |
| DESCRIPTION | object | 181,797 | 0.0 | 360 | 0.2 | Medication reconciliation (procedure), Medication reconciliation (procedure), Allergy screening test (procedure) |
| BASE_COST | float64 | 181,797 | 0.0 | 19,857 | 10.92 | 862.8, 355.59, 431.4 |
| REASONCODE | float64 | 86,897 | 52.2 | 97 | 0.11 | 33737001.0, 103697008.0, 103697008.0 |
| REASONDESCRIPTION | object | 86,897 | 52.2 | 97 | 0.11 | Fracture of rib (disorder), Patient referral for dental care (procedure), Patient referral for dental care (procedure) |

### Foreign Keys

- `ENCOUNTER` → `encounters.Id` (100.00% of 181,797 values matched)
- `PATIENT` → `patients.Id` (100.00% of 181,797 values matched)

## providers

- **File:** `providers.csv`
- **Shape:** 814 rows × 13 columns
- **Primary key(s):** Id

### Columns

| Column | Dtype | Non-Null | Null % | Unique | Unique % | Sample Values |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Id | object | 814 | 0.0 | 814 | 100.0 | 2ae50b62-aee1-3bfb-9b53-507dc466e5ce, e3898e67-ee3b-3a4e-9e5e-42cfc4dd13c7, 4a327e01-b57e-32be-a07b-d67d551e8b23 |
| ORGANIZATION | object | 814 | 0.0 | 814 | 100.0 | 74ab949d-17ac-3309-83a0-13b4405c66aa, 588f6ce6-b8db-3588-8189-29db2680a313, 324b4137-57a0-3ae0-89db-1c33f57ae0c1 |
| NAME | object | 814 | 0.0 | 814 | 100.0 | Ted955 Reilly981, Tiffaney302 Brakus656, Herma433 Satterfield305 |
| GENDER | object | 814 | 0.0 | 2 | 0.25 | M, F, F |
| SPECIALITY | object | 814 | 0.0 | 1 | 0.12 | GENERAL PRACTICE, GENERAL PRACTICE, GENERAL PRACTICE |
| ADDRESS | object | 814 | 0.0 | 768 | 94.35 | 881 Main Street, 461 WALNUT AVE, 134 NORTH ST |
| CITY | object | 814 | 0.0 | 250 | 30.71 | Fitchburg, JAMAICA PLAIN, NORTH READING |
| STATE | object | 814 | 0.0 | 1 | 0.12 | MA, MA, MA |
| ZIP | int64 | 814 | 0.0 | 758 | 93.12 | 1420, 21302331, 18641315 |
| LAT | float64 | 814 | 0.0 | 727 | 89.31 | 42.586487, 42.3115876, 42.5892341 |
| LON | float64 | 814 | 0.0 | 727 | 89.31 | -71.80521, -71.09800136347226, -71.10546522083789 |
| ENCOUNTERS | int64 | 814 | 0.0 | 339 | 41.65 | 1921, 89, 2 |
| PROCEDURES | int64 | 814 | 0.0 | 1 | 0.12 | 0, 0, 0 |

### Foreign Keys

- `ORGANIZATION` → `organizations.Id` (100.00% of 814 values matched)

## supplies

- **File:** `supplies.csv`
- **Shape:** 29,208 rows × 6 columns
- **Primary key(s):** (composite - no single surrogate key)

### Columns

| Column | Dtype | Non-Null | Null % | Unique | Unique % | Sample Values |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| DATE | object | 29,208 | 0.0 | 5,707 | 19.54 | 2024-04-21, 2024-04-21, 2024-04-21 |
| PATIENT | object | 29,208 | 0.0 | 1,065 | 3.65 | bbf5f505-3df2-3cb7-c066-de2487fba44b, bbf5f505-3df2-3cb7-c066-de2487fba44b, bbf5f505-3df2-3cb7-c066-de2487fba44b |
| ENCOUNTER | object | 29,208 | 0.0 | 11,087 | 37.96 | bbf5f505-3df2-3cb7-4f00-3dc07af2742f, bbf5f505-3df2-3cb7-4f00-3dc07af2742f, bbf5f505-3df2-3cb7-4f00-3dc07af2742f |
| CODE | int64 | 29,208 | 0.0 | 36 | 0.12 | 277183007, 1230220004, 469020004 |
| DESCRIPTION | object | 29,208 | 0.0 | 36 | 0.12 | Dental equipment (physical object), Conventional release periodontal gel (dose form), Dental floss (physical object) |
| QUANTITY | int64 | 29,208 | 0.0 | 12 | 0.04 | 1, 1, 1 |

### Foreign Keys

- `ENCOUNTER` → `encounters.Id` (100.00% of 29,208 values matched)
- `PATIENT` → `patients.Id` (100.00% of 29,208 values matched)
