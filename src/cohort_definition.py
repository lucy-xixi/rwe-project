"""Step 2: Cohort definition for diabetes comparative effectiveness RWE study.

Defines the analytic study population from Synthea synthetic EHR CSV exports using
pharmaceutical observational study conventions: confirmed Type 2 Diabetes Mellitus,
adult age restriction, evidence of healthcare utilization, and post-diagnosis
medication exposure with an index date anchored to first diabetes pharmacotherapy.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "synthea_csv"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "reports"

MIN_AGE_YEARS = 18

# Primary T2DM diagnosis — description-based identification (conditions.csv).
# Complication codes (e.g., "Neuropathy due to type 2 diabetes mellitus") are
# excluded so the index diagnosis reflects incident T2DM, not downstream sequelae.
PRIMARY_T2DM_DESCRIPTION = "Diabetes mellitus type 2 (disorder)"
T2DM_DESCRIPTION_PATTERN = re.compile(
    r"(?i)^diabetes mellitus type 2 \(disorder\)$"
)

# Diabetes pharmacotherapy keywords for medications.csv DESCRIPTION field.
METFORMIN_PATTERN = re.compile(r"(?i)metformin")
DIABETES_MEDICATION_PATTERN = re.compile(
    r"(?i)metformin|insulin|liraglutide|glipizide|glyburide|glimepiride|"
    r"sitagliptin|empagliflozin|semaglutide|dapagliflozin|pioglitazone|"
    r"repaglinide|nateglinide|canagliflozin|exenatide|dulaglutide"
)

TREATMENT_GROUP_METFORMIN = "Metformin users"
TREATMENT_GROUP_OTHER = "Other diabetes medication users"

STUDY_TABLES = (
    "patients",
    "conditions",
    "medications",
    "encounters",
    "observations",
)


@dataclass
class CohortFlow:
    """Track patient counts at each inclusion/exclusion step for CONSORT-style reporting."""

    steps: list[dict[str, object]] = field(default_factory=list)

    def record(self, step: str, n: int, description: str = "") -> None:
        self.steps.append({"step": step, "n": n, "description": description})

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.steps)


@dataclass
class CohortDefinitionResult:
    diabetes_cohort: pd.DataFrame
    treatment_exposure: pd.DataFrame
    study_population: pd.DataFrame
    cohort_flow: CohortFlow
    tables: dict[str, pd.DataFrame]


def parse_datetime(series: pd.Series) -> pd.Series:
    """Parse Synthea date/datetime strings to timezone-aware timestamps."""
    return pd.to_datetime(series, utc=True, errors="coerce", format="mixed")


def load_patients(data_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(data_dir / "patients.csv", low_memory=False)
    df["BIRTHDATE"] = parse_datetime(df["BIRTHDATE"])
    df["DEATHDATE"] = parse_datetime(df["DEATHDATE"])
    return df


def load_conditions(data_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(data_dir / "conditions.csv", low_memory=False)
    df["START"] = parse_datetime(df["START"])
    df["STOP"] = parse_datetime(df["STOP"])
    return df


def load_medications(data_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(data_dir / "medications.csv", low_memory=False)
    df["START"] = parse_datetime(df["START"])
    df["STOP"] = parse_datetime(df["STOP"])
    return df


def load_encounters(data_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(data_dir / "encounters.csv", low_memory=False)
    df["START"] = parse_datetime(df["START"])
    df["STOP"] = parse_datetime(df["STOP"])
    return df


def load_observations(data_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(data_dir / "observations.csv", low_memory=False)
    df["DATE"] = parse_datetime(df["DATE"])
    return df


def load_study_data(data_dir: Path) -> dict[str, pd.DataFrame]:
    """Load all tables required for cohort definition."""
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    loaders = {
        "patients": load_patients,
        "conditions": load_conditions,
        "medications": load_medications,
        "encounters": load_encounters,
        "observations": load_observations,
    }
    tables = {name: loader(data_dir) for name, loader in loaders.items()}
    return tables


def compute_age_years(birthdate: pd.Timestamp, reference: pd.Timestamp) -> float:
    """Age in completed years at reference date (standard epidemiologic definition)."""
    delta = relativedelta(reference, birthdate)
    return delta.years + delta.months / 12.0 + delta.days / 365.25


def identify_diabetes_cohort(conditions: pd.DataFrame) -> pd.DataFrame:
    """Identify Type 2 Diabetes patients from condition descriptions.

    Uses the primary T2DM disorder description to avoid misclassifying
    complication records as incident diabetes diagnoses.
    """
    t2dm = conditions[
        conditions["DESCRIPTION"].astype(str).str.match(T2DM_DESCRIPTION_PATTERN)
    ].copy()

    if t2dm.empty:
        # Fallback: exact string match if regex behavior differs across pandas versions
        t2dm = conditions[conditions["DESCRIPTION"] == PRIMARY_T2DM_DESCRIPTION].copy()

    diabetes_cohort = (
        t2dm.groupby("PATIENT", as_index=False)["START"]
        .min()
        .rename(columns={"PATIENT": "patient_id", "START": "diabetes_diagnosis_date"})
        .sort_values("diabetes_diagnosis_date")
    )
    return diabetes_cohort


def is_diabetes_medication(description: str) -> bool:
    return bool(DIABETES_MEDICATION_PATTERN.search(str(description)))


def is_metformin(description: str) -> bool:
    return bool(METFORMIN_PATTERN.search(str(description)))


def define_treatment_exposure(
    medications: pd.DataFrame,
    diabetes_cohort: pd.DataFrame,
) -> pd.DataFrame:
    """Assign treatment groups based on first post-diagnosis diabetes medication.

    Group A (Metformin users): index therapy description contains metformin.
    Group B (Other diabetes medication users): index therapy is a non-metformin
    antihyperglycemic agent (e.g., insulin, GLP-1 agonist).
    """
    diag_dates = diabetes_cohort.set_index("patient_id")["diabetes_diagnosis_date"]

    dm_meds = medications[
        medications["DESCRIPTION"].apply(is_diabetes_medication)
    ].copy()
    dm_meds = dm_meds[dm_meds["PATIENT"].isin(diag_dates.index)]

    # Restrict to prescriptions on or after T2DM diagnosis (treatment after diagnosis).
    dm_meds["diabetes_diagnosis_date"] = dm_meds["PATIENT"].map(diag_dates)
    dm_meds = dm_meds[dm_meds["START"] >= dm_meds["diabetes_diagnosis_date"]]

    if dm_meds.empty:
        return pd.DataFrame(
            columns=["patient_id", "treatment_group", "treatment_start_date", "index_medication"]
        )

    first_med = (
        dm_meds.sort_values("START")
        .groupby("PATIENT", as_index=False)
        .first()
    )

    exposure = pd.DataFrame(
        {
            "patient_id": first_med["PATIENT"],
            "treatment_start_date": first_med["START"],
            "index_medication": first_med["DESCRIPTION"],
            "treatment_group": np.where(
                first_med["DESCRIPTION"].apply(is_metformin),
                TREATMENT_GROUP_METFORMIN,
                TREATMENT_GROUP_OTHER,
            ),
        }
    )
    return exposure


def apply_inclusion_criteria(
    diabetes_cohort: pd.DataFrame,
    treatment_exposure: pd.DataFrame,
    patients: pd.DataFrame,
    encounters: pd.DataFrame,
    flow: CohortFlow,
) -> pd.DataFrame:
    """Apply study inclusion criteria and return the final study population."""
    flow.record(
        "1_all_patients",
        len(patients),
        "All patients in patients.csv",
    )
    flow.record(
        "2_t2dm_diagnosis",
        len(diabetes_cohort),
        "Patients with Type 2 Diabetes Mellitus (description-based)",
    )

    # Merge diagnosis with medication exposure (must have post-diagnosis pharmacotherapy).
    cohort = diabetes_cohort.merge(treatment_exposure, on="patient_id", how="inner")
    flow.record(
        "3_post_diagnosis_medication",
        len(cohort),
        "T2DM patients with diabetes medication exposure after diagnosis",
    )

    # At least one healthcare encounter (proves contact with healthcare system).
    patients_with_encounters = set(encounters["PATIENT"].dropna().unique())
    cohort = cohort[cohort["patient_id"].isin(patients_with_encounters)]
    flow.record(
        "4_has_encounter",
        len(cohort),
        "Patients with at least one healthcare encounter",
    )

    demo = patients.set_index("Id")
    ages: list[float] = []
    genders: list[str] = []
    races: list[str] = []
    keep_rows: list[bool] = []

    for row in cohort.itertuples(index=False):
        patient = row.patient_id
        index_date = row.treatment_start_date

        if patient not in demo.index:
            keep_rows.append(False)
            ages.append(np.nan)
            genders.append(np.nan)
            races.append(np.nan)
            continue

        birthdate = demo.loc[patient, "BIRTHDATE"]
        age = compute_age_years(birthdate, index_date)
        ages.append(age)
        genders.append(demo.loc[patient, "GENDER"])
        races.append(demo.loc[patient, "RACE"])
        keep_rows.append(age >= MIN_AGE_YEARS)

    cohort = cohort.copy()
    cohort["age"] = ages
    cohort["gender"] = genders
    cohort["race"] = races

    cohort = cohort[keep_rows]
    flow.record(
        "5_adult_at_index",
        len(cohort),
        f"Adult patients (age >= {MIN_AGE_YEARS}) at index date",
    )

    # Final study population: index date = first diabetes medication exposure date.
    study_population = cohort.rename(columns={"treatment_start_date": "index_date"})[
        ["patient_id", "age", "gender", "race", "index_date", "treatment_group"]
    ].sort_values("index_date")

    flow.record(
        "6_final_study_population",
        len(study_population),
        "Final analytic cohort",
    )

    return study_population


def build_study_population(
    tables: dict[str, pd.DataFrame],
    flow: CohortFlow | None = None,
) -> CohortDefinitionResult:
    """Execute full cohort definition pipeline."""
    flow = flow or CohortFlow()

    diabetes_cohort = identify_diabetes_cohort(tables["conditions"])
    treatment_exposure = define_treatment_exposure(
        tables["medications"], diabetes_cohort
    )
    study_population = apply_inclusion_criteria(
        diabetes_cohort,
        treatment_exposure,
        tables["patients"],
        tables["encounters"],
        flow,
    )

    return CohortDefinitionResult(
        diabetes_cohort=diabetes_cohort,
        treatment_exposure=treatment_exposure,
        study_population=study_population,
        cohort_flow=flow,
        tables=tables,
    )


def run_cohort_definition(
    data_dir: Path | None = None,
    report_dir: Path | None = None,
) -> CohortDefinitionResult:
    """Load data, define cohort, and write study_population.csv."""
    data_dir = (data_dir or DEFAULT_DATA_DIR).resolve()
    report_dir = (report_dir or DEFAULT_REPORT_DIR).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("RWE COHORT DEFINITION — TYPE 2 DIABETES")
    print("=" * 72)
    print(f"Data source: {data_dir}")

    tables = load_study_data(data_dir)
    result = build_study_population(tables)

    output_path = report_dir / "study_population.csv"
    result.study_population.to_csv(output_path, index=False)

    flow_path = report_dir / "cohort_flow.csv"
    result.cohort_flow.to_dataframe().to_csv(flow_path, index=False)

    result.diabetes_cohort.to_csv(report_dir / "diabetes_cohort.csv", index=False)
    result.treatment_exposure.to_csv(report_dir / "treatment_exposure.csv", index=False)

    print("\nCohort flow:")
    print(result.cohort_flow.to_dataframe().to_string(index=False))
    print(f"\nFinal study population: N = {len(result.study_population)}")
    print(
        result.study_population["treatment_group"]
        .value_counts()
        .to_string()
    )
    print(f"\nStudy population written to: {output_path}")
    print("=" * 72)

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Define T2DM study cohort from Synthea CSV data."
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_cohort_definition(args.data_dir, args.report_dir)


if __name__ == "__main__":
    main()
