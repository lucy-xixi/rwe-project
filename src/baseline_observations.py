"""Baseline laboratory and vital-sign extraction from Synthea observations.csv.

Provides pre-index HbA1c and BMI for Table 1 and propensity score covariates.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from cohort_definition import parse_datetime

logger = logging.getLogger(__name__)

# LOINC codes in Synthea observations.csv
HBA1C_LOINC = "4548-4"  # Hemoglobin A1c/Hemoglobin.total in Blood (%)
BMI_LOINC = "39156-5"  # Body mass index (BMI) [Ratio] (kg/m2)

DEFAULT_BASELINE_LOOKBACK_DAYS = 365


def _prepare_observations(observations: pd.DataFrame) -> pd.DataFrame:
    df = observations.copy()
    df["DATE"] = parse_datetime(df["DATE"])
    df["VALUE"] = pd.to_numeric(df["VALUE"], errors="coerce")
    return df


def latest_pre_index_value(
    observations: pd.DataFrame,
    patient_id: str,
    index_date: pd.Timestamp,
    loinc_code: str,
    lookback_days: int = DEFAULT_BASELINE_LOOKBACK_DAYS,
) -> float:
    """Most recent numeric observation on or before index_date.

    Prefers measurements within ``lookback_days`` before index; if none exist,
    falls back to the latest pre-index value of any age.
    """
    patient_obs = observations[
        (observations["PATIENT"] == patient_id)
        & (observations["CODE"] == loinc_code)
        & (observations["DATE"] <= index_date)
        & (observations["VALUE"].notna())
    ].sort_values("DATE")

    if patient_obs.empty:
        return np.nan

    if lookback_days > 0:
        window_start = index_date - pd.Timedelta(days=lookback_days)
        in_window = patient_obs[patient_obs["DATE"] >= window_start]
        if not in_window.empty:
            return float(in_window.iloc[-1]["VALUE"])

    return float(patient_obs.iloc[-1]["VALUE"])


def build_baseline_labs(
    study_population: pd.DataFrame,
    observations: pd.DataFrame,
    lookback_days: int = DEFAULT_BASELINE_LOOKBACK_DAYS,
) -> pd.DataFrame:
    """Patient-level baseline HbA1c (%) and BMI (kg/m2) at or before index_date."""
    obs = _prepare_observations(observations)
    rows: list[dict[str, object]] = []

    for row in study_population.itertuples(index=False):
        patient_id = row.patient_id
        index_date = row.index_date
        hba1c = latest_pre_index_value(obs, patient_id, index_date, HBA1C_LOINC, lookback_days)
        bmi = latest_pre_index_value(obs, patient_id, index_date, BMI_LOINC, lookback_days)
        rows.append(
            {
                "patient_id": patient_id,
                "baseline_hba1c": hba1c,
                "baseline_bmi": bmi,
            }
        )

    labs = pd.DataFrame(rows)
    n = len(labs)
    logger.info(
        "Baseline labs: HbA1c available %s/%s (%.0f%%), BMI available %s/%s (%.0f%%)",
        labs["baseline_hba1c"].notna().sum(),
        n,
        100 * labs["baseline_hba1c"].notna().mean(),
        labs["baseline_bmi"].notna().sum(),
        n,
        100 * labs["baseline_bmi"].notna().mean(),
    )
    return labs


def attach_baseline_labs(
    patient_df: pd.DataFrame,
    observations: pd.DataFrame,
    lookback_days: int = DEFAULT_BASELINE_LOOKBACK_DAYS,
) -> pd.DataFrame:
    """Merge baseline HbA1c and BMI onto a patient-level dataframe."""
    if "index_date" not in patient_df.columns:
        raise ValueError("patient_df must include index_date for baseline lab extraction")
    labs = build_baseline_labs(patient_df, observations, lookback_days)
    return patient_df.merge(labs, on="patient_id", how="left")


def impute_confounder_medians(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Median imputation for continuous confounders (used in PS / regression)."""
    out = df.copy()
    for col in columns:
        if col in out.columns and out[col].isna().any():
            out[col] = out[col].fillna(out[col].median())
    return out
