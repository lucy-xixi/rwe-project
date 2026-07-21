# Synthea CSV Data

This folder holds **Synthea** synthetic EHR CSV exports used by the RWE pipeline.

## GitHub clone note

Raw CSV files are **not committed** (~780 MB). After cloning the repository, place Synthea CSV files here before running Steps 1–8.

## How to obtain data

1. **Use your existing export** — copy all `*.csv` from your Synthea run into this directory.

2. **Generate with Synthea** — see [Synthea documentation](https://github.com/synthetichealth/synthea):

   ```bash
   git clone https://github.com/synthetichealth/synthea.git
   cd synthea
   ./run_synthea -p 1000
   ```

   Copy the generated CSV files from `output/csv/` into this folder.

## Required tables

At minimum, the pipeline uses:

- `patients.csv`
- `conditions.csv`
- `medications.csv`
- `encounters.csv`
- `observations.csv`

## Without raw data

You can still review pre-generated outputs in `reports/`:

- `RWE_Evidence_Report.pdf` / `.html`
- Step-specific HTML reports
- CSV summaries from completed pipeline runs (if committed)
