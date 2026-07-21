"""Baseline characteristics for the diabetes RWE study cohort.

Generates descriptive statistics used in observational study reporting (Table 1
precursors): demographic distributions, treatment arm sizes, and prevalent
comorbidities measured at or before the index date.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

from cohort_definition import (
    DEFAULT_DATA_DIR,
    DEFAULT_REPORT_DIR,
    load_study_data,
    parse_datetime,
)

# Comorbidity identification via condition DESCRIPTION (baseline window: on/before index).
COMORBIDITY_PATTERNS: dict[str, re.Pattern[str]] = {
    "hypertension": re.compile(r"(?i)hypertension"),
    "hyperlipidemia": re.compile(r"(?i)hyperlipidemia"),
    "obesity": re.compile(r"(?i)obesity|body mass index 30"),
    "ischemic_heart_disease": re.compile(r"(?i)ischemic heart disease"),
    "heart_failure": re.compile(r"(?i)heart failure"),
    "chronic_kidney_disease": re.compile(r"(?i)chronic kidney disease"),
    "diabetic_nephropathy": re.compile(r"(?i)kidney due to diabetes|diabetic nephropathy|albuminuria due to type 2"),
    "diabetic_neuropathy": re.compile(r"(?i)neuropathy due to type 2 diabetes"),
    "diabetic_retinopathy": re.compile(r"(?i)retinopathy due to type 2 diabetes|macular edema and retinopathy"),
    "depression": re.compile(r"(?i)depression"),
    "copd": re.compile(r"(?i)chronic obstructive pulmonary disease"),
}


def load_study_population(report_dir: Path) -> pd.DataFrame:
    path = report_dir / "study_population.csv"
    if not path.is_file():
        raise FileNotFoundError(
            f"Study population not found: {path}. Run cohort_definition.py first."
        )
    df = pd.read_csv(path)
    df["index_date"] = parse_datetime(df["index_date"])
    return df


def _patient_comorbidities_at_index(
    conditions: pd.DataFrame,
    patient_id: str,
    index_date: pd.Timestamp,
) -> dict[str, int]:
    """Flag comorbidities present at or before index date (baseline prevalence)."""
    patient_conds = conditions[
        (conditions["PATIENT"] == patient_id) & (conditions["START"] <= index_date)
    ]
    flags = {}
    for name, pattern in COMORBIDITY_PATTERNS.items():
        flags[name] = int(
            patient_conds["DESCRIPTION"].astype(str).str.contains(pattern, regex=True).any()
        )
    return flags


def generate_baseline_characteristics(
    study_population: pd.DataFrame,
    conditions: pd.DataFrame,
) -> pd.DataFrame:
    """Build long-format baseline characteristics table for reporting."""
    rows: list[dict[str, object]] = []

    n_total = len(study_population)
    rows.append(
        {
            "category": "Cohort size",
            "variable": "Total patients",
            "level": "All",
            "n": n_total,
            "percent": 100.0,
            "summary_stat": "count",
        }
    )

    # Treatment group sizes
    for group, count in study_population["treatment_group"].value_counts().items():
        rows.append(
            {
                "category": "Treatment group",
                "variable": "treatment_group",
                "level": group,
                "n": int(count),
                "percent": round(100 * count / n_total, 1),
                "summary_stat": "count",
            }
        )

    # Age distribution
    ages = study_population["age"].dropna()
    rows.extend(
        [
            {
                "category": "Age (years)",
                "variable": "age",
                "level": "mean",
                "n": n_total,
                "percent": np.nan,
                "summary_stat": round(float(ages.mean()), 1),
            },
            {
                "category": "Age (years)",
                "variable": "age",
                "level": "std",
                "n": n_total,
                "percent": np.nan,
                "summary_stat": round(float(ages.std()), 1),
            },
            {
                "category": "Age (years)",
                "variable": "age",
                "level": "median",
                "n": n_total,
                "percent": np.nan,
                "summary_stat": round(float(ages.median()), 1),
            },
            {
                "category": "Age (years)",
                "variable": "age",
                "level": "Q1",
                "n": n_total,
                "percent": np.nan,
                "summary_stat": round(float(ages.quantile(0.25)), 1),
            },
            {
                "category": "Age (years)",
                "variable": "age",
                "level": "Q3",
                "n": n_total,
                "percent": np.nan,
                "summary_stat": round(float(ages.quantile(0.75)), 1),
            },
            {
                "category": "Age (years)",
                "variable": "age",
                "level": "min",
                "n": n_total,
                "percent": np.nan,
                "summary_stat": round(float(ages.min()), 1),
            },
            {
                "category": "Age (years)",
                "variable": "age",
                "level": "max",
                "n": n_total,
                "percent": np.nan,
                "summary_stat": round(float(ages.max()), 1),
            },
        ]
    )

    # Gender distribution
    for gender, count in study_population["gender"].value_counts(dropna=False).items():
        rows.append(
            {
                "category": "Gender",
                "variable": "gender",
                "level": str(gender),
                "n": int(count),
                "percent": round(100 * count / n_total, 1),
                "summary_stat": "count",
            }
        )

    # Race distribution
    for race, count in study_population["race"].value_counts(dropna=False).items():
        rows.append(
            {
                "category": "Race",
                "variable": "race",
                "level": str(race),
                "n": int(count),
                "percent": round(100 * count / n_total, 1),
                "summary_stat": "count",
            }
        )

    # Comorbidities at index
    comorbidity_counts: dict[str, int] = {name: 0 for name in COMORBIDITY_PATTERNS}
    for row in study_population.itertuples(index=False):
        flags = _patient_comorbidities_at_index(
            conditions, row.patient_id, row.index_date
        )
        for name, value in flags.items():
            comorbidity_counts[name] += value

    for name, count in sorted(comorbidity_counts.items()):
        rows.append(
            {
                "category": "Comorbidity (baseline)",
                "variable": name,
                "level": "present",
                "n": count,
                "percent": round(100 * count / n_total, 1),
                "summary_stat": "count",
            }
        )

    return pd.DataFrame(rows)


def run_baseline_characteristics(
    data_dir: Path | None = None,
    report_dir: Path | None = None,
) -> pd.DataFrame:
    """Generate and save baseline characteristics report."""
    data_dir = (data_dir or DEFAULT_DATA_DIR).resolve()
    report_dir = (report_dir or DEFAULT_REPORT_DIR).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    study_population = load_study_population(report_dir)
    tables = load_study_data(data_dir)

    baseline = generate_baseline_characteristics(
        study_population, tables["conditions"]
    )

    output_path = report_dir / "baseline_characteristics.csv"
    baseline.to_csv(output_path, index=False)

    print("=" * 72)
    print("BASELINE CHARACTERISTICS")
    print("=" * 72)
    print(f"Cohort N = {len(study_population)}")
    print(baseline.to_string(index=False))
    print(f"\nReport written to: {output_path}")
    print("=" * 72)

    return baseline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate baseline characteristics for study cohort."
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_baseline_characteristics(args.data_dir, args.report_dir)


if __name__ == "__main__":
    main()
