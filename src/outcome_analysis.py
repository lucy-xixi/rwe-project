"""Step 5: Outcome analysis for RWE comparative effectiveness studies.

Ascertains clinical outcomes from Synthea EHR data, calculates event rates,
performs time-to-event and binary outcome analyses, and generates pharmaceutical
RWE-style reports. Results are unadjusted associations; confounding should be
addressed in subsequent causal inference steps.
"""

from __future__ import annotations

import argparse
import html
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import statsmodels.api as sm
from lifelines import KaplanMeierFitter
from lifelines.statistics import logrank_test

from cohort_definition import (
    DEFAULT_DATA_DIR,
    DEFAULT_REPORT_DIR,
    TREATMENT_GROUP_METFORMIN,
    TREATMENT_GROUP_OTHER,
    load_conditions,
    load_encounters,
    load_medications,
    load_observations,
    load_patients,
    parse_datetime,
)
from treatment_exposure import classify_medication_class

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RANDOM_SEED = 42

TREATMENT_A = TREATMENT_GROUP_METFORMIN
TREATMENT_B = TREATMENT_GROUP_OTHER

# ---------------------------------------------------------------------------
# Outcome definitions (conditions.csv DESCRIPTION patterns)
# ---------------------------------------------------------------------------
OUTCOME_PATTERNS: dict[str, re.Pattern[str]] = {
    "diabetes_complication": re.compile(
        r"(?i)due to type 2 diabetes|diabetic nephropathy|diabetic neuropathy|"
        r"diabetic retinopathy|kidney due to diabetes|albuminuria due to type 2|"
        r"proteinuria due to type 2|neuropathy due to type 2|retinopathy due to type 2"
    ),
    "cardiovascular_event": re.compile(
        r"(?i)ischemic heart disease|heart failure|myocardial infarction|"
        r"stroke|cerebrovascular|coronary heart disease|atrial fibrillation"
    ),
    "diabetic_nephropathy": re.compile(
        r"(?i)kidney due to diabetes|albuminuria due to type 2|proteinuria due to type 2"
    ),
    "diabetic_neuropathy": re.compile(r"(?i)neuropathy due to type 2 diabetes"),
    "diabetic_retinopathy": re.compile(
        r"(?i)retinopathy due to type 2 diabetes|macular edema and retinopathy"
    ),
}

ACUTE_ENCOUNTER_CLASSES = frozenset({"inpatient", "emergency"})


@dataclass
class OutcomeAnalysisResult:
    outcome_events: pd.DataFrame
    patient_followup: pd.DataFrame
    outcome_summary: pd.DataFrame
    survival_results: pd.DataFrame
    logistic_results: pd.DataFrame
    figure_paths: list[Path] = field(default_factory=list)
    report_path: Path | None = None


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_study_population(report_dir: Path) -> pd.DataFrame:
    path = report_dir / "study_population.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}. Run Step 2 cohort definition first.")
    df = pd.read_csv(path)
    df["index_date"] = parse_datetime(df["index_date"])
    return df


def load_treatment_exposure(report_dir: Path) -> pd.DataFrame:
    """Load Step 4 exposure data; fall back to cohort-level treatment_exposure.csv."""
    for name in ("exposure_dataset.csv", "treatment_exposure.csv"):
        path = report_dir / name
        if path.is_file():
            df = pd.read_csv(path)
            for col in ("treatment_start_date", "index_date", "followup_end_date"):
                if col in df.columns:
                    df[col] = parse_datetime(df[col])
            logger.info("Loaded treatment exposure from %s", path)
            return df
    raise FileNotFoundError("No treatment exposure file found in reports/")


def build_analysis_cohort(
    study_population: pd.DataFrame,
    exposure: pd.DataFrame,
) -> pd.DataFrame:
    """Merge study population with exposure windows; restrict to A vs B arms."""
    cohort = study_population.merge(
        exposure[["patient_id", "treatment_start_date", "followup_end_date"]]
        if "followup_end_date" in exposure.columns
        else exposure[["patient_id", "treatment_start_date"]],
        on="patient_id",
        how="left",
        suffixes=("", "_exp"),
    )

    if "treatment_start_date" not in cohort.columns:
        cohort["treatment_start_date"] = cohort["index_date"]
    else:
        cohort["treatment_start_date"] = cohort["treatment_start_date"].fillna(
            cohort["index_date"]
        )

    # Compare assigned treatment groups A vs B only
    cohort = cohort[
        cohort["treatment_group"].isin([TREATMENT_A, TREATMENT_B])
    ].copy()
    cohort["treatment_binary"] = (cohort["treatment_group"] == TREATMENT_B).astype(int)
    return cohort


def define_followup(
    cohort: pd.DataFrame,
    conditions: pd.DataFrame,
    encounters: pd.DataFrame,
    observations: pd.DataFrame,
    medications: pd.DataFrame,
    patients: pd.DataFrame,
) -> pd.DataFrame:
    """Define follow-up from index_date to latest available clinical record."""
    demo = patients.set_index("Id")
    rows: list[dict[str, object]] = []

    for row in cohort.itertuples(index=False):
        patient_id = row.patient_id
        index_date = row.index_date

        dates: list[pd.Timestamp] = []
        if hasattr(row, "followup_end_date") and pd.notna(getattr(row, "followup_end_date", pd.NaT)):
            dates.append(getattr(row, "followup_end_date"))

        for table, col, pid_col in [
            (conditions, "START", "PATIENT"),
            (encounters, "START", "PATIENT"),
            (observations, "DATE", "PATIENT"),
            (medications, "START", "PATIENT"),
        ]:
            recs = table[table[pid_col] == patient_id]
            if not recs.empty and col in recs.columns:
                dates.append(recs[col].max())

        if patient_id in demo.index and pd.notna(demo.loc[patient_id, "DEATHDATE"]):
            dates.append(demo.loc[patient_id, "DEATHDATE"])

        followup_end = max(dates) if dates else index_date + pd.Timedelta(days=730)
        followup_days = max((followup_end - index_date).days, 1)
        followup_months = followup_days / 30.4375
        followup_years = followup_days / 365.25

        rows.append(
            {
                "patient_id": patient_id,
                "treatment_group": row.treatment_group,
                "treatment_binary": row.treatment_binary,
                "index_date": index_date,
                "followup_end_date": followup_end,
                "followup_days": followup_days,
                "followup_months": round(followup_months, 1),
                "followup_years": round(followup_years, 3),
            }
        )

    return pd.DataFrame(rows)


def extract_condition_outcomes(
    conditions: pd.DataFrame,
    cohort: pd.DataFrame,
) -> pd.DataFrame:
    """Extract post-index condition-based outcomes (long format)."""
    cohort_ids = set(cohort["patient_id"])
    index_dates = cohort.set_index("patient_id")["index_date"]

    conds = conditions[conditions["PATIENT"].isin(cohort_ids)].copy()
    events: list[dict[str, object]] = []

    for outcome_type, pattern in OUTCOME_PATTERNS.items():
        matched = conds[conds["DESCRIPTION"].astype(str).str.contains(pattern, regex=True)]
        for rec in matched.itertuples(index=False):
            patient_id = rec.PATIENT
            index_date = index_dates.loc[patient_id]
            if rec.START <= index_date:
                continue
            events.append(
                {
                    "patient_id": patient_id,
                    "outcome_type": outcome_type,
                    "outcome_date": rec.START,
                    "outcome_source": "conditions",
                    "outcome_description": rec.DESCRIPTION,
                }
            )

    return pd.DataFrame(events)


def extract_hospitalization_outcomes(
    encounters: pd.DataFrame,
    cohort: pd.DataFrame,
) -> pd.DataFrame:
    """Extract post-index acute care hospitalization / ED events."""
    index_dates = cohort.set_index("patient_id")["index_date"]
    enc = encounters[
        encounters["PATIENT"].isin(index_dates.index)
        & encounters["ENCOUNTERCLASS"].isin(ACUTE_ENCOUNTER_CLASSES)
    ].copy()

    events = []
    for rec in enc.itertuples(index=False):
        if rec.START <= index_dates.loc[rec.PATIENT]:
            continue
        events.append(
            {
                "patient_id": rec.PATIENT,
                "outcome_type": "hospitalization_event",
                "outcome_date": rec.START,
                "outcome_source": "encounters",
                "outcome_description": rec.ENCOUNTERCLASS,
            }
        )
    return pd.DataFrame(events)


def extract_secondary_outcomes(
    cohort: pd.DataFrame,
    encounters: pd.DataFrame,
    medications: pd.DataFrame,
    conditions: pd.DataFrame,
) -> pd.DataFrame:
    """Secondary outcomes: encounter counts, medication changes, progression."""
    index_dates = cohort.set_index("patient_id")["index_date"]
    followup = cohort.set_index("patient_id")["followup_end_date"] if "followup_end_date" in cohort.columns else None

    rows = []
    for row in cohort.itertuples(index=False):
        patient_id = row.patient_id
        idx = row.index_date
        end = row.followup_end_date if hasattr(row, "followup_end_date") else idx + pd.Timedelta(days=730)

        post_enc = encounters[
            (encounters["PATIENT"] == patient_id)
            & (encounters["START"] > idx)
            & (encounters["START"] <= end)
        ]
        n_encounters = len(post_enc)

        post_meds = medications[
            (medications["PATIENT"] == patient_id)
            & (medications["START"] > idx)
            & (medications["START"] <= end)
        ].sort_values("START")
        med_classes = post_meds["DESCRIPTION"].apply(classify_medication_class).tolist()
        medication_change = int(len(set(med_classes)) > 1) if med_classes else 0

        # Disease progression: new diabetes complication after index not present at index
        pre_comp = conditions[
            (conditions["PATIENT"] == patient_id)
            & (conditions["START"] <= idx)
            & (conditions["DESCRIPTION"].astype(str).str.contains(
                OUTCOME_PATTERNS["diabetes_complication"], regex=True
            ))
        ]
        post_comp = conditions[
            (conditions["PATIENT"] == patient_id)
            & (conditions["START"] > idx)
            & (conditions["START"] <= end)
            & (conditions["DESCRIPTION"].astype(str).str.contains(
                OUTCOME_PATTERNS["diabetes_complication"], regex=True
            ))
        ]
        progression = int(len(post_comp) > len(pre_comp) or (post_comp.shape[0] > 0 and pre_comp.empty))

        rows.append(
            {
                "patient_id": patient_id,
                "n_encounters": n_encounters,
                "medication_change": medication_change,
                "disease_progression": progression,
            }
        )

    return pd.DataFrame(rows)


def build_primary_composite(outcome_events: pd.DataFrame) -> pd.DataFrame:
    """Primary outcome: first post-index diabetes complication, CVD, or hospitalization."""
    primary_types = {
        "diabetes_complication",
        "cardiovascular_event",
        "hospitalization_event",
    }
    primary = outcome_events[outcome_events["outcome_type"].isin(primary_types)].copy()
    if primary.empty:
        return primary
    first = (
        primary.sort_values("outcome_date")
        .groupby("patient_id", as_index=False)
        .first()
    )
    first["outcome_type"] = "primary_composite_event"
    return first


def calculate_event_rates(
    cohort: pd.DataFrame,
    followup: pd.DataFrame,
    outcome_events: pd.DataFrame,
    secondary: pd.DataFrame,
) -> pd.DataFrame:
    """Event rates by treatment group including events per 100 patient-years."""
    merged = followup.merge(secondary, on="patient_id", how="left")
    outcome_types = sorted(outcome_events["outcome_type"].unique()) + [
        "medication_change",
        "disease_progression",
        "high_encounter_utilization",
    ]

    rows = []
    for outcome_type in outcome_types:
        for group in [TREATMENT_A, TREATMENT_B, "Overall"]:
            if group == "Overall":
                patients = merged
            else:
                patients = merged[merged["treatment_group"] == group]

            n_patients = len(patients)
            person_years = patients["followup_years"].sum()

            if outcome_type == "medication_change":
                n_events = int(patients["medication_change"].fillna(0).sum())
            elif outcome_type == "disease_progression":
                n_events = int(patients["disease_progression"].fillna(0).sum())
            elif outcome_type == "high_encounter_utilization":
                n_events = int((patients["n_encounters"].fillna(0) >= 5).sum())
            else:
                event_patients = set(
                    outcome_events[outcome_events["outcome_type"] == outcome_type]["patient_id"]
                )
                n_events = int(patients["patient_id"].isin(event_patients).sum())

            rate_per_100_py = (
                (n_events / person_years * 100) if person_years > 0 else np.nan
            )
            rows.append(
                {
                    "outcome_type": outcome_type,
                    "treatment_group": group,
                    "n_patients": n_patients,
                    "n_events": n_events,
                    "event_percentage": round(100 * n_events / n_patients, 1) if n_patients else 0,
                    "person_years": round(person_years, 2),
                    "events_per_100_patient_years": round(rate_per_100_py, 2),
                }
            )

    return pd.DataFrame(rows)


def build_survival_dataset(
    followup: pd.DataFrame,
    primary_events: pd.DataFrame,
) -> pd.DataFrame:
    """Patient-level survival data for primary composite outcome."""
    surv = followup.copy()
    event_lookup = primary_events.set_index("patient_id")["outcome_date"]
    surv["event"] = surv["patient_id"].isin(event_lookup.index).astype(int)
    surv["event_date"] = surv["patient_id"].map(event_lookup)
    surv["duration_days"] = np.where(
        surv["event"] == 1,
        (surv["event_date"] - surv["index_date"]).dt.days,
        surv["followup_days"],
    )
    surv["duration_days"] = surv["duration_days"].clip(lower=1)
    return surv


def run_kaplan_meier_analysis(survival: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    """Kaplan-Meier curves and log-rank test (Treatment B vs A)."""
    results = []
    kmf = KaplanMeierFitter()

    median_times: dict[str, float] = {}
    for group in [TREATMENT_A, TREATMENT_B]:
        mask = survival["treatment_group"] == group
        kmf.fit(
            survival.loc[mask, "duration_days"],
            survival.loc[mask, "event"],
            label=group,
        )
        median = kmf.median_survival_time_
        median_times[group] = float(median) if pd.notna(median) else np.nan
        results.append(
            {
                "treatment_group": group,
                "n": int(mask.sum()),
                "n_events": int(survival.loc[mask, "event"].sum()),
                "median_event_free_days": median_times[group],
            }
        )

    group_a = survival[survival["treatment_group"] == TREATMENT_A]
    group_b = survival[survival["treatment_group"] == TREATMENT_B]
    lr = logrank_test(
        group_a["duration_days"],
        group_b["duration_days"],
        group_a["event"],
        group_b["event"],
    )

    km_summary = pd.DataFrame(results)
    km_stats = {
        "logrank_statistic": float(lr.test_statistic),
        "logrank_p_value": float(lr.p_value),
        "median_days_metformin": median_times.get(TREATMENT_A, np.nan),
        "median_days_other": median_times.get(TREATMENT_B, np.nan),
    }
    return km_summary, km_stats


def run_logistic_regression(
    followup: pd.DataFrame,
    outcome_events: pd.DataFrame,
    outcome_type: str,
) -> dict[str, float | str]:
    """Unadjusted logistic regression: outcome ~ treatment group (statsmodels GLM)."""
    event_patients = set(
        outcome_events[outcome_events["outcome_type"] == outcome_type]["patient_id"]
    )
    df = followup.copy()
    df["outcome"] = df["patient_id"].isin(event_patients).astype(int)

    if df["outcome"].nunique() < 2:
        return {
            "outcome_type": outcome_type,
            "odds_ratio": np.nan,
            "ci_lower": np.nan,
            "ci_upper": np.nan,
            "p_value": np.nan,
            "n": len(df),
            "n_events": int(df["outcome"].sum()),
            "model": "Insufficient events",
        }

    X = sm.add_constant(df["treatment_binary"])
    model = sm.GLM(df["outcome"], X, family=sm.families.Binomial())
    fit = model.fit(cov_type="HC1")
    or_est = float(np.exp(fit.params["treatment_binary"]))
    ci = fit.conf_int().loc["treatment_binary"]
    return {
        "outcome_type": outcome_type,
        "odds_ratio": round(or_est, 3),
        "ci_lower": round(float(np.exp(ci[0])), 3),
        "ci_upper": round(float(np.exp(ci[1])), 3),
        "p_value": round(float(fit.pvalues["treatment_binary"]), 4),
        "n": len(df),
        "n_events": int(df["outcome"].sum()),
        "model": "Logistic regression (unadjusted)",
    }


def create_figures(
    outcome_summary: pd.DataFrame,
    survival: pd.DataFrame,
    outcome_events: pd.DataFrame,
    figures_dir: Path,
) -> list[Path]:
    """Generate outcome analysis visualizations."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")
    paths: list[Path] = []

    # 1. Outcome incidence by treatment group (primary outcomes)
    primary_outcomes = [
        "primary_composite_event",
        "diabetes_complication",
        "cardiovascular_event",
        "hospitalization_event",
    ]
    plot_df = outcome_summary[
        (outcome_summary["outcome_type"].isin(primary_outcomes))
        & (outcome_summary["treatment_group"].isin([TREATMENT_A, TREATMENT_B]))
    ]
    if not plot_df.empty:
        fig, ax = plt.subplots(figsize=(10, 5))
        pivot = plot_df.pivot(index="outcome_type", columns="treatment_group", values="event_percentage")
        pivot.plot(kind="bar", ax=ax, color=["#2980b9", "#c0392b"], edgecolor="white")
        ax.set_ylabel("Event incidence (%)")
        ax.set_title("Outcome Incidence by Treatment Group")
        ax.legend(title="Treatment")
        plt.xticks(rotation=25, ha="right")
        p1 = figures_dir / "outcome_incidence_by_group.png"
        fig.tight_layout()
        fig.savefig(p1, dpi=150)
        plt.close(fig)
        paths.append(p1)

    # 2. Kaplan-Meier survival curve
    fig, ax = plt.subplots(figsize=(9, 5))
    for group, color in [(TREATMENT_A, "#2980b9"), (TREATMENT_B, "#c0392b")]:
        mask = survival["treatment_group"] == group
        kmf = KaplanMeierFitter()
        kmf.fit(
            survival.loc[mask, "duration_days"],
            survival.loc[mask, "event"],
            label=group,
        )
        kmf.plot_survival_function(ax=ax, color=color, ci_show=True)
    ax.set_xlabel("Days from index date")
    ax.set_ylabel("Event-free survival probability")
    ax.set_title("Kaplan-Meier Curve — Primary Composite Outcome")
    p2 = figures_dir / "kaplan_meier_primary_outcome.png"
    fig.tight_layout()
    fig.savefig(p2, dpi=150)
    plt.close(fig)
    paths.append(p2)

    # 3. Event timeline plot
    primary = outcome_events[
        outcome_events["outcome_type"].isin(
            ["primary_composite_event", "diabetes_complication", "cardiovascular_event", "hospitalization_event"]
        )
    ]
    if not primary.empty:
        fig, ax = plt.subplots(figsize=(10, 6))
        merged = primary.merge(
            survival[["patient_id", "treatment_group", "index_date"]], on="patient_id"
        )
        merged["days_from_index"] = (merged["outcome_date"] - merged["index_date"]).dt.days
        for group, color in [(TREATMENT_A, "#2980b9"), (TREATMENT_B, "#c0392b")]:
            sub = merged[merged["treatment_group"] == group]
            ax.scatter(
                sub["days_from_index"],
                np.random.default_rng(RANDOM_SEED).uniform(0.8, 1.2, len(sub)),
                alpha=0.6,
                s=40,
                label=group,
                color=color,
            )
        ax.set_xlabel("Days from index date")
        ax.set_yticks([])
        ax.set_title("Event Timeline — Primary and Component Outcomes")
        ax.legend()
        p3 = figures_dir / "event_timeline.png"
        fig.tight_layout()
        fig.savefig(p3, dpi=150)
        plt.close(fig)
        paths.append(p3)

    for p in paths:
        logger.info("Saved figure: %s", p)
    return paths


def write_html_report(
    cohort: pd.DataFrame,
    followup: pd.DataFrame,
    outcome_summary: pd.DataFrame,
    km_summary: pd.DataFrame,
    km_stats: dict[str, float],
    logistic_results: pd.DataFrame,
    figure_paths: list[Path],
    report_path: Path,
) -> None:
    """Generate RWE-style outcome analysis HTML report."""
    n = len(cohort)
    n_a = int((cohort["treatment_group"] == TREATMENT_A).sum())
    n_b = int((cohort["treatment_group"] == TREATMENT_B).sum())
    mean_fu = followup["followup_days"].mean()

    figure_html = ""
    for fp in figure_paths:
        figure_html += f'<figure><img src="figures/{html.escape(fp.name)}" alt="{html.escape(fp.name)}"><figcaption>{html.escape(fp.name)}</figcaption></figure>'

    interpretation = (
        "<p><strong>Interpretation:</strong> These results represent unadjusted associations. "
        "Potential confounding factors (e.g., age, comorbidity burden) should be addressed "
        "using causal inference methods such as propensity score weighting or doubly robust "
        "estimation in subsequent analysis.</p>"
    )

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Outcome Analysis Report — RWE Diabetes Study</title>
  <style>
    body {{ font-family: "Segoe UI", Tahoma, sans-serif; margin: 0; background: #f4f7fb; color: #1f2937; }}
    .container {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}
    header {{ background: linear-gradient(135deg, #1e3a8a, #2563eb); color: #fff; padding: 28px; border-radius: 12px; margin-bottom: 24px; }}
    section {{ background: #fff; border: 1px solid #dbe3ef; border-radius: 10px; padding: 20px; margin-bottom: 20px; }}
    h2 {{ color: #1d4ed8; margin-top: 0; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; }}
    th, td {{ border-bottom: 1px solid #dbe3ef; padding: 8px 10px; text-align: left; }}
    th {{ background: #eef2ff; }}
    figure {{ text-align: center; margin: 16px 0; }}
    img {{ max-width: 100%; border: 1px solid #dbe3ef; border-radius: 8px; }}
    .warning {{ background: #fff7ed; border-left: 4px solid #ea580c; padding: 12px; margin: 12px 0; }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Outcome Analysis Report</h1>
      <p>Step 5 — Synthetic RWE Diabetes Treatment Study</p>
      <p>Metformin users (n={n_a:,}) vs Other diabetes medication users (n={n_b:,})</p>
    </header>

    <section>
      <h2>1. Study Population</h2>
      <p>Adult T2DM patients from Step 2 cohort assigned to metformin or other diabetes
      medication at index date. Total analytic N = {n:,}.</p>
    </section>

    <section>
      <h2>2. Outcome Definitions</h2>
      <ul>
        <li><strong>Primary composite:</strong> First post-index diabetes complication,
        cardiovascular event, or hospitalization/ED visit</li>
        <li><strong>Diabetes complication:</strong> Nephropathy, neuropathy, retinopathy,
        or other T2DM sequelae (conditions.csv)</li>
        <li><strong>Cardiovascular event:</strong> IHD, heart failure, stroke (conditions.csv)</li>
        <li><strong>Hospitalization event:</strong> Inpatient or emergency encounter (encounters.csv)</li>
        <li><strong>Secondary:</strong> Encounter count, medication change, disease progression</li>
      </ul>
    </section>

    <section>
      <h2>3. Follow-Up Description</h2>
      <p>Follow-up begins at index_date (first diabetes medication) and ends at the latest
      available clinical record (conditions, encounters, observations, medications) or death.</p>
      <p>Mean follow-up: {mean_fu:.0f} days ({mean_fu/30.4375:.1f} months)</p>
    </section>

    <section>
      <h2>4. Event Rates</h2>
      {outcome_summary.to_html(index=False)}
    </section>

    <section>
      <h2>5. Time-to-Event Analysis (Kaplan-Meier)</h2>
      {km_summary.to_html(index=False)}
      <p>Log-rank test: statistic = {km_stats['logrank_statistic']:.3f},
      p = {km_stats['logrank_p_value']:.4f}</p>
      <p>Median event-free time — Metformin: {km_stats['median_days_metformin']:.0f} days;
      Other: {km_stats['median_days_other']:.0f} days</p>
    </section>

    <section>
      <h2>6. Binary Outcome Analysis (Logistic Regression)</h2>
      <p>Unadjusted model: Outcome ~ Treatment group (Other vs Metformin)</p>
      {logistic_results.to_html(index=False)}
      {interpretation}
    </section>

    <section>
      <h2>7. Visualizations</h2>
      {figure_html}
    </section>

    <section>
      <h2>8. Limitations</h2>
      <ul>
        <li>Unadjusted comparisons may reflect confounding by indication (sicker patients more likely to receive insulin).</li>
        <li>Synthea synthetic data has limited outcome diversity and follow-up patterns.</li>
        <li>Condition-based outcomes depend on diagnosis coding completeness.</li>
        <li>Hospitalization events include ED visits; severity is not stratified.</li>
        <li>Competing risks (death) not modeled in Kaplan-Meier framework.</li>
      </ul>
      <div class="warning">{interpretation}</div>
    </section>
  </div>
</body>
</html>
"""
    report_path.write_text(doc, encoding="utf-8")
    logger.info("HTML report written to: %s", report_path)


def run_outcome_analysis(
    data_dir: Path | None = None,
    report_dir: Path | None = None,
) -> OutcomeAnalysisResult:
    """Execute Step 5 outcome analysis pipeline."""
    np.random.seed(RANDOM_SEED)
    configure_logging()

    data_dir = (data_dir or DEFAULT_DATA_DIR).resolve()
    report_dir = (report_dir or DEFAULT_REPORT_DIR).resolve()
    figures_dir = report_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Starting outcome analysis")

    study_population = load_study_population(report_dir)
    exposure = load_treatment_exposure(report_dir)
    cohort = build_analysis_cohort(study_population, exposure)

    conditions = load_conditions(data_dir)
    encounters = load_encounters(data_dir)
    observations = load_observations(data_dir)
    medications = load_medications(data_dir)
    patients = load_patients(data_dir)

    followup = define_followup(
        cohort, conditions, encounters, observations, medications, patients
    )
    cohort = cohort.merge(
        followup[["patient_id", "followup_end_date", "followup_days", "followup_years"]],
        on="patient_id",
    )

    condition_events = extract_condition_outcomes(conditions, cohort)
    hospital_events = extract_hospitalization_outcomes(encounters, cohort)
    outcome_events = pd.concat([condition_events, hospital_events], ignore_index=True)
    primary_events = build_primary_composite(outcome_events)
    outcome_events = pd.concat([outcome_events, primary_events], ignore_index=True)

    secondary = extract_secondary_outcomes(cohort, encounters, medications, conditions)
    outcome_summary = calculate_event_rates(cohort, followup, outcome_events, secondary)

    survival = build_survival_dataset(followup, primary_events)
    km_summary, km_stats = run_kaplan_meier_analysis(survival)

    logistic_outcomes = [
        "primary_composite_event",
        "diabetes_complication",
        "cardiovascular_event",
        "hospitalization_event",
    ]
    logistic_rows = [
        run_logistic_regression(followup, outcome_events, ot) for ot in logistic_outcomes
    ]
    logistic_results = pd.DataFrame(logistic_rows)

    survival_results = km_summary.copy()
    survival_results["logrank_p_value"] = km_stats["logrank_p_value"]

    # Save outputs
    outcome_events.to_csv(report_dir / "outcome_events.csv", index=False)
    followup.to_csv(report_dir / "patient_followup.csv", index=False)
    outcome_summary.to_csv(report_dir / "outcome_summary.csv", index=False)
    logistic_results.to_csv(report_dir / "logistic_regression_results.csv", index=False)
    survival_results.to_csv(report_dir / "survival_analysis_results.csv", index=False)

    figure_paths = create_figures(outcome_summary, survival, outcome_events, figures_dir)
    report_path = report_dir / "outcome_analysis_report.html"
    write_html_report(
        cohort, followup, outcome_summary, km_summary, km_stats,
        logistic_results, figure_paths, report_path,
    )

    print("=" * 72)
    print("OUTCOME ANALYSIS — STEP 5")
    print("=" * 72)
    print(f"Analytic cohort N = {len(cohort)}")
    print(f"  {TREATMENT_A}: {(cohort['treatment_group'] == TREATMENT_A).sum()}")
    print(f"  {TREATMENT_B}: {(cohort['treatment_group'] == TREATMENT_B).sum()}")
    print(f"\nPrimary composite events: {len(primary_events)}")
    print(f"Log-rank p-value: {km_stats['logrank_p_value']:.4f}")
    print(f"\nOutcome summary: {report_dir / 'outcome_summary.csv'}")
    print(f"HTML report: {report_path}")
    print("=" * 72)

    return OutcomeAnalysisResult(
        outcome_events=outcome_events,
        patient_followup=followup,
        outcome_summary=outcome_summary,
        survival_results=survival_results,
        logistic_results=logistic_results,
        figure_paths=figure_paths,
        report_path=report_path,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Step 5 outcome analysis.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_outcome_analysis(args.data_dir, args.report_dir)


if __name__ == "__main__":
    main()
