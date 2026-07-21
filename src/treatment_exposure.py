"""Step 4: Treatment exposure definition for RWE comparative effectiveness studies.

Defines treatment groups, exposure windows, treatment switching patterns, and
summary statistics for an observational diabetes pharmacotherapy study using
Synthea synthetic EHR medication records.
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

from cohort_definition import (
    DEFAULT_DATA_DIR,
    DEFAULT_REPORT_DIR,
    TREATMENT_GROUP_METFORMIN,
    TREATMENT_GROUP_OTHER,
    load_medications,
    load_patients,
    parse_datetime,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Exposure window parameters (pharmaceutical RWE convention)
BASELINE_LOOKBACK_DAYS = 365
FOLLOWUP_DAYS = 730
PERSISTENCE_GAP_DAYS = 90  # gap beyond which a refill is considered discontinuation

# ---------------------------------------------------------------------------
# Medication classification rules (documented for protocol / SAP appendix)
# ---------------------------------------------------------------------------
# Each diabetes medication record is classified by DESCRIPTION keyword matching.
# Group A (study arm): Metformin — biguanide first-line therapy.
# Group B (study arm): All other glucose-lowering agents in the analytic cohort.
#
# Detailed medication_class supports descriptive reporting and switching analysis.
MEDICATION_CLASS_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("Metformin", re.compile(r"(?i)metformin")),
    ("Insulin", re.compile(r"(?i)insulin")),
    ("GLP-1 receptor agonist", re.compile(r"(?i)liraglutide|semaglutide|exenatide|dulaglutide")),
    ("SGLT2 inhibitor", re.compile(r"(?i)empagliflozin|dapagliflozin|canagliflozin")),
    ("DPP-4 inhibitor", re.compile(r"(?i)sitagliptin|saxagliptin|linagliptin")),
    ("Sulfonylurea", re.compile(r"(?i)glipizide|glyburide|glimepiride|glipizide")),
    ("Thiazolidinedione", re.compile(r"(?i)pioglitazone|rosiglitazone")),
    ("Other antidiabetic", re.compile(r"(?i)repaglinide|nateglinide")),
]

DIABETES_MEDICATION_PATTERN = re.compile(
    r"(?i)metformin|insulin|liraglutide|glipizide|glyburide|glimepiride|"
    r"sitagliptin|empagliflozin|semaglutide|dapagliflozin|pioglitazone|"
    r"repaglinide|nateglinide|canagliflozin|exenatide|dulaglutide"
)

TREATMENT_GROUP_MULTIPLE = "Multiple medication users"


@dataclass
class TreatmentExposureResult:
    initiation: pd.DataFrame
    exposure_dataset: pd.DataFrame
    treatment_patterns: pd.DataFrame
    group_summary: pd.DataFrame
    medication_class_summary: pd.DataFrame
    figure_paths: list[Path] = field(default_factory=list)
    report_path: Path | None = None


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_study_population(report_dir: Path) -> pd.DataFrame:
    """Load Step 2 analytic cohort."""
    path = report_dir / "study_population.csv"
    if not path.is_file():
        raise FileNotFoundError(
            f"Study population not found: {path}. Run cohort_definition.py (Step 2) first."
        )
    df = pd.read_csv(path)
    df["index_date"] = parse_datetime(df["index_date"])
    logger.info("Loaded study population: N=%s", len(df))
    return df


def load_medication_records(data_dir: Path) -> pd.DataFrame:
    """Load and standardize medications.csv for exposure analysis."""
    meds = load_medications(data_dir)
    meds = meds.rename(
        columns={
            "PATIENT": "patient_id",
            "START": "medication_start_date",
            "STOP": "medication_end_date",
            "DESCRIPTION": "medication_name",
        }
    )
    meds = meds[meds["medication_name"].apply(lambda d: bool(DIABETES_MEDICATION_PATTERN.search(str(d))))]
    logger.info("Loaded %s diabetes medication records for %s patients", len(meds), meds["patient_id"].nunique())
    return meds


def classify_medication_class(description: str) -> str:
    """Map medication DESCRIPTION to a detailed antidiabetic drug class."""
    text = str(description)
    for class_name, pattern in MEDICATION_CLASS_RULES:
        if pattern.search(text):
            return class_name
    if DIABETES_MEDICATION_PATTERN.search(text):
        return "Other antidiabetic"
    return "Non-diabetes medication"


def classify_study_treatment_group(medication_class: str) -> str:
    """Map detailed class to study treatment arm (A = Metformin, B = Other)."""
    if medication_class == "Metformin":
        return TREATMENT_GROUP_METFORMIN
    return TREATMENT_GROUP_OTHER


def define_treatment_initiation(
    study_population: pd.DataFrame,
    medications: pd.DataFrame,
) -> pd.DataFrame:
    """Define index treatment date and group for each study patient.

    Index treatment date = first diabetes medication exposure on/after cohort
    index_date (which equals first post-diagnosis pharmacotherapy from Step 2).
    """
    cohort_ids = set(study_population["patient_id"])
    meds = medications[medications["patient_id"].isin(cohort_ids)].copy()
    meds["medication_class"] = meds["medication_name"].apply(classify_medication_class)

    index_lookup = study_population.set_index("patient_id")["index_date"]

    rows: list[dict[str, object]] = []
    for patient_id in study_population["patient_id"]:
        patient_meds = meds[meds["patient_id"] == patient_id].sort_values("medication_start_date")
        index_date = index_lookup.loc[patient_id]

        # Post-index diabetes medication records (exposure ascertainment window)
        post_index = patient_meds[patient_meds["medication_start_date"] >= index_date]
        if post_index.empty:
            continue

        first = post_index.iloc[0]
        rows.append(
            {
                "patient_id": patient_id,
                "treatment_group": study_population.loc[
                    study_population["patient_id"] == patient_id, "treatment_group"
                ].iloc[0],
                "treatment_start_date": first["medication_start_date"],
                "index_medication_name": first["medication_name"],
                "index_medication_class": first["medication_class"],
            }
        )

    initiation = pd.DataFrame(rows)
    logger.info("Treatment initiation records: N=%s", len(initiation))
    return initiation


def define_exposure_windows(
    initiation: pd.DataFrame,
    study_population: pd.DataFrame,
    patients: pd.DataFrame,
    medications: pd.DataFrame,
) -> pd.DataFrame:
    """Define baseline and follow-up exposure periods relative to treatment initiation.

    Baseline period: [baseline_start_date, treatment_start_date)
    Follow-up period: [treatment_start_date, followup_end_date]
    """
    demo = patients.set_index("Id")
    rows: list[dict[str, object]] = []

    for row in initiation.itertuples(index=False):
        patient_id = row.patient_id
        treatment_start = row.treatment_start_date
        baseline_start = treatment_start - pd.Timedelta(days=BASELINE_LOOKBACK_DAYS)

        # Administrative follow-up censoring at 2 years or death / last observed med
        followup_end = treatment_start + pd.Timedelta(days=FOLLOWUP_DAYS)
        if patient_id in demo.index and pd.notna(demo.loc[patient_id, "DEATHDATE"]):
            followup_end = min(followup_end, demo.loc[patient_id, "DEATHDATE"])

        patient_meds = medications[medications["patient_id"] == patient_id]
        last_med = patient_meds["medication_start_date"].max()
        if pd.notna(last_med):
            followup_end = min(followup_end, last_med + pd.Timedelta(days=365))

        # Multiple medication exposure flag during follow-up
        post_meds = patient_meds[
            (patient_meds["medication_start_date"] >= treatment_start)
            & (patient_meds["medication_start_date"] <= followup_end)
        ]
        classes = post_meds["medication_name"].apply(classify_medication_class).unique()
        has_metformin = any(c == "Metformin" for c in classes)
        has_other = any(c != "Metformin" for c in classes)
        multiple_meds = int(has_metformin and has_other)

        exposure_group = row.treatment_group
        if multiple_meds:
            exposure_group = TREATMENT_GROUP_MULTIPLE

        rows.append(
            {
                "patient_id": patient_id,
                "treatment_group": row.treatment_group,
                "exposure_category": exposure_group,
                "treatment_start_date": treatment_start,
                "baseline_start_date": baseline_start,
                "followup_end_date": followup_end,
                "baseline_days": BASELINE_LOOKBACK_DAYS,
                "followup_days": (followup_end - treatment_start).days,
                "multiple_medication_user": multiple_meds,
                "distinct_medication_classes": len(classes),
            }
        )

    return pd.DataFrame(rows)


def assess_treatment_patterns(
    initiation: pd.DataFrame,
    medications: pd.DataFrame,
) -> pd.DataFrame:
    """Identify treatment switching, discontinuation, and polypharmacy patterns."""
    rows: list[dict[str, object]] = []

    for row in initiation.itertuples(index=False):
        patient_id = row.patient_id
        treatment_start = row.treatment_start_date
        initial_class = row.index_medication_class
        initial_name = row.index_medication_name

        patient_meds = medications[
            (medications["patient_id"] == patient_id)
            & (medications["medication_start_date"] >= treatment_start)
        ].sort_values("medication_start_date")

        patient_meds = patient_meds.copy()
        patient_meds["medication_class"] = patient_meds["medication_name"].apply(
            classify_medication_class
        )

        subsequent = patient_meds.iloc[1:] if len(patient_meds) > 1 else patient_meds.iloc[0:0]
        subsequent_classes = subsequent["medication_class"].unique().tolist()
        subsequent_names = subsequent["medication_name"].unique().tolist()

        # Switch = any post-index fill of a different medication class
        switched = int(any(c != initial_class for c in subsequent_classes))
        switch_date = pd.NaT
        if switched and not subsequent.empty:
            switch_rows = subsequent[subsequent["medication_class"] != initial_class]
            switch_date = switch_rows.iloc[0]["medication_start_date"]

        # Discontinuation proxy: no refill within PERSISTENCE_GAP_DAYS of prior STOP
        discontinued = 0
        if not patient_meds.empty:
            last = patient_meds.iloc[-1]
            end = last["medication_end_date"]
            if pd.isna(end):
                discontinued = 0
            else:
                later = patient_meds[
                    patient_meds["medication_start_date"] > end + pd.Timedelta(days=PERSISTENCE_GAP_DAYS)
                ]
                discontinued = int(len(later) == 0 and len(patient_meds) == 1)

        multiple_classes = len(patient_meds["medication_class"].unique())
        multiple_meds = int(multiple_classes > 1)

        rows.append(
            {
                "patient_id": patient_id,
                "initial_treatment": initial_name,
                "initial_medication_class": initial_class,
                "initial_treatment_group": row.treatment_group,
                "subsequent_treatment": "; ".join(subsequent_names) if subsequent_names else "",
                "subsequent_medication_classes": "; ".join(subsequent_classes) if subsequent_classes else "",
                "switch_indicator": switched,
                "switch_date": switch_date,
                "discontinuation_indicator": discontinued,
                "multiple_medication_indicator": multiple_meds,
                "n_diabetes_medication_fills": len(patient_meds),
                "n_distinct_medication_classes": multiple_classes,
            }
        )

    return pd.DataFrame(rows)


def summarize_treatment_groups(
    exposure_dataset: pd.DataFrame,
) -> pd.DataFrame:
    """Treatment group summary table with multiple-medication category."""
    n = len(exposure_dataset)
    counts = exposure_dataset["exposure_category"].value_counts()

    summary_rows = []
    for group in [
        TREATMENT_GROUP_METFORMIN,
        TREATMENT_GROUP_OTHER,
        TREATMENT_GROUP_MULTIPLE,
    ]:
        count = int(counts.get(group, 0))
        summary_rows.append(
            {
                "treatment_group": group,
                "n_patients": count,
                "percentage": round(100 * count / n, 1) if n else 0.0,
            }
        )

    # Assigned-at-index groups (from Step 2) for reference
    assigned = exposure_dataset["treatment_group"].value_counts()
    for group in [TREATMENT_GROUP_METFORMIN, TREATMENT_GROUP_OTHER]:
        count = int(assigned.get(group, 0))
        summary_rows.append(
            {
                "treatment_group": f"{group} (assigned at index)",
                "n_patients": count,
                "percentage": round(100 * count / n, 1) if n else 0.0,
            }
        )

    return pd.DataFrame(summary_rows)


def summarize_medication_classes(medications: pd.DataFrame, study_population: pd.DataFrame) -> pd.DataFrame:
    """Distribution of detailed medication classes at index initiation."""
    cohort_ids = set(study_population["patient_id"])
    meds = medications[medications["patient_id"].isin(cohort_ids)].copy()
    meds["medication_class"] = meds["medication_name"].apply(classify_medication_class)

    index_dates = study_population.set_index("patient_id")["index_date"]
    first_records = []
    for patient_id, idx_date in index_dates.items():
        patient_meds = meds[
            (meds["patient_id"] == patient_id) & (meds["medication_start_date"] >= idx_date)
        ].sort_values("medication_start_date")
        if not patient_meds.empty:
            first_records.append(patient_meds.iloc[0])

    if not first_records:
        return pd.DataFrame(columns=["medication_class", "n_patients", "percentage"])

    first_df = pd.DataFrame(first_records)
    n = len(first_df)
    summary = (
        first_df.groupby("medication_class")
        .size()
        .reset_index(name="n_patients")
    )
    summary["percentage"] = (summary["n_patients"] / n * 100).round(1)
    return summary.sort_values("n_patients", ascending=False)


def create_figures(
    exposure_dataset: pd.DataFrame,
    initiation: pd.DataFrame,
    medication_class_summary: pd.DataFrame,
    figures_dir: Path,
) -> list[Path]:
    """Generate treatment exposure visualizations."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")
    paths: list[Path] = []

    # 1. Treatment group distribution
    fig, ax = plt.subplots(figsize=(8, 5))
    plot_data = exposure_dataset["exposure_category"].value_counts()
    colors = ["#2980b9", "#c0392b", "#8e44ad"]
    bars = ax.bar(plot_data.index, plot_data.values, color=colors[: len(plot_data)], edgecolor="white")
    ax.set_ylabel("Number of patients")
    ax.set_title("Treatment Group Distribution")
    for bar, val in zip(bars, plot_data.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3, str(val), ha="center", fontweight="bold")
    plt.xticks(rotation=15, ha="right")
    p1 = figures_dir / "treatment_group_distribution.png"
    fig.tight_layout()
    fig.savefig(p1, dpi=150)
    plt.close(fig)
    paths.append(p1)

    # 2. Medication class distribution
    if not medication_class_summary.empty:
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.barh(
            medication_class_summary["medication_class"],
            medication_class_summary["n_patients"],
            color="#1d4ed8",
            edgecolor="white",
        )
        ax.set_xlabel("Number of patients (index medication)")
        ax.set_title("Index Medication Class Distribution")
        ax.invert_yaxis()
        p2 = figures_dir / "medication_class_distribution.png"
        fig.tight_layout()
        fig.savefig(p2, dpi=150)
        plt.close(fig)
        paths.append(p2)

    # 3. Treatment initiation timeline
    fig, ax = plt.subplots(figsize=(10, 5))
    timeline = initiation.copy()
    timeline["year"] = timeline["treatment_start_date"].dt.year
    for group, color in [
        (TREATMENT_GROUP_METFORMIN, "#2980b9"),
        (TREATMENT_GROUP_OTHER, "#c0392b"),
    ]:
        subset = timeline[timeline["treatment_group"] == group]["year"].value_counts().sort_index()
        ax.plot(subset.index, subset.values, marker="o", label=group, color=color, linewidth=2)
    ax.set_xlabel("Year of treatment initiation")
    ax.set_ylabel("Number of patients")
    ax.set_title("Treatment Initiation Timeline")
    ax.legend()
    p3 = figures_dir / "treatment_initiation_timeline.png"
    fig.tight_layout()
    fig.savefig(p3, dpi=150)
    plt.close(fig)
    paths.append(p3)

    for p in paths:
        logger.info("Saved figure: %s", p)
    return paths


def write_html_report(
    group_summary: pd.DataFrame,
    medication_class_summary: pd.DataFrame,
    treatment_patterns: pd.DataFrame,
    figure_paths: list[Path],
    report_path: Path,
) -> None:
    """Generate treatment exposure documentation report."""
    n = int(treatment_patterns.shape[0])
    n_switch = int(treatment_patterns["switch_indicator"].sum())
    n_multiple = int(treatment_patterns["multiple_medication_indicator"].sum())
    switch_pct = round(100 * n_switch / n, 1) if n else 0
    multiple_pct = round(100 * n_multiple / n, 1) if n else 0

    rules_html = "<ul>" + "".join(
        f"<li><strong>{name}</strong>: pattern <code>{pat.pattern}</code></li>"
        for name, pat in MEDICATION_CLASS_RULES
    ) + "</ul>"

    figure_html = ""
    for fig_path in figure_paths:
        figure_html += f'<figure><img src="figures/{html.escape(fig_path.name)}" alt="{html.escape(fig_path.name)}"><figcaption>{html.escape(fig_path.name)}</figcaption></figure>'

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Treatment Exposure Report — RWE Diabetes Study</title>
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
    code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 4px; }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Treatment Exposure Definition Report</h1>
      <p>Step 4 — Synthetic RWE Diabetes Treatment Study</p>
      <p>Study population N = {n:,}</p>
    </header>

    <section>
      <h2>Treatment Definition Rules</h2>
      <p><strong>Group A (Metformin users):</strong> Index diabetes medication class = Metformin.</p>
      <p><strong>Group B (Other diabetes medication users):</strong> Index medication is any other
      glucose-lowering agent (insulin, GLP-1, sulfonylurea, etc.).</p>
      <p><strong>Multiple medication users:</strong> Received both metformin and a non-metformin
      diabetes medication during follow-up (descriptive category for exposure complexity).</p>
      <p><strong>Index treatment date:</strong> First diabetes medication exposure date after T2DM
      diagnosis (aligned with Step 2 index_date).</p>
    </section>

    <section>
      <h2>Medication Classification Logic</h2>
      {rules_html}
      <p>Classification is applied to the <code>DESCRIPTION</code> field in medications.csv using
      case-insensitive regular expression matching.</p>
    </section>

    <section>
      <h2>Exposure Period Definition</h2>
      <ul>
        <li><strong>Baseline period:</strong> {BASELINE_LOOKBACK_DAYS} days before treatment initiation
        (baseline_start_date to treatment_start_date)</li>
        <li><strong>Follow-up period:</strong> From treatment_start_date through followup_end_date
        (minimum {FOLLOWUP_DAYS} days administratively, censored at death or last observed medication)</li>
      </ul>
    </section>

    <section>
      <h2>Treatment Group Summary</h2>
      {group_summary.to_html(index=False)}
    </section>

    <section>
      <h2>Index Medication Class Summary</h2>
      {medication_class_summary.to_html(index=False)}
    </section>

    <section>
      <h2>Treatment Switching and Polypharmacy</h2>
      <p>Patients with treatment switch: {n_switch:,} ({switch_pct}%)</p>
      <p>Patients with multiple medication classes: {n_multiple:,} ({multiple_pct}%)</p>
    </section>

    <section>
      <h2>Visualizations</h2>
      {figure_html}
    </section>

    <section>
      <h2>Exposure Limitations</h2>
      <ul>
        <li>Synthea synthetic data contains limited antidiabetic drug classes (primarily metformin and insulin).</li>
        <li>Medication end dates (STOP) may be missing for ongoing prescriptions, affecting discontinuation detection.</li>
        <li>Treatment switching is inferred from prescription records, not confirmed clinical decisions.</li>
        <li>Over-the-counter glucose-lowering products are not captured in EHR medication tables.</li>
        <li>Exposure definitions should be replicated when applying this pipeline to real-world claims/EHR data with NDC/RxNorm mapping.</li>
      </ul>
    </section>
  </div>
</body>
</html>
"""
    report_path.write_text(doc, encoding="utf-8")
    logger.info("HTML report written to: %s", report_path)


def run_treatment_exposure(
    data_dir: Path | None = None,
    report_dir: Path | None = None,
) -> TreatmentExposureResult:
    """Execute Step 4 treatment exposure definition pipeline."""
    configure_logging()
    data_dir = (data_dir or DEFAULT_DATA_DIR).resolve()
    report_dir = (report_dir or DEFAULT_REPORT_DIR).resolve()
    figures_dir = report_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Starting treatment exposure definition")
    study_population = load_study_population(report_dir)
    medications = load_medication_records(data_dir)
    medications["medication_class"] = medications["medication_name"].apply(classify_medication_class)
    patients = load_patients(data_dir)

    initiation = define_treatment_initiation(study_population, medications)
    exposure_dataset = define_exposure_windows(
        initiation, study_population, patients, medications
    )
    treatment_patterns = assess_treatment_patterns(initiation, medications)
    group_summary = summarize_treatment_groups(exposure_dataset)
    medication_class_summary = summarize_medication_classes(medications, study_population)

    # Persist outputs
    exposure_dataset.to_csv(report_dir / "exposure_dataset.csv", index=False)
    treatment_patterns.to_csv(report_dir / "treatment_pattern_summary.csv", index=False)
    group_summary.to_csv(report_dir / "treatment_exposure_summary.csv", index=False)
    initiation.to_csv(report_dir / "treatment_initiation.csv", index=False)
    medication_class_summary.to_csv(report_dir / "medication_class_summary.csv", index=False)

    figure_paths = create_figures(
        exposure_dataset, initiation, medication_class_summary, figures_dir
    )
    report_path = report_dir / "treatment_exposure_report.html"
    write_html_report(
        group_summary,
        medication_class_summary,
        treatment_patterns,
        figure_paths,
        report_path,
    )

    print("=" * 72)
    print("TREATMENT EXPOSURE DEFINITION — STEP 4")
    print("=" * 72)
    print(f"Study population N = {len(study_population)}")
    print("\nTreatment group summary:")
    print(group_summary.to_string(index=False))
    print(f"\nTreatment switching: {int(treatment_patterns['switch_indicator'].sum())} patients")
    print(f"Multiple medications: {int(treatment_patterns['multiple_medication_indicator'].sum())} patients")
    print(f"\nOutputs written to: {report_dir}")
    print("=" * 72)

    return TreatmentExposureResult(
        initiation=initiation,
        exposure_dataset=exposure_dataset,
        treatment_patterns=treatment_patterns,
        group_summary=group_summary,
        medication_class_summary=medication_class_summary,
        figure_paths=figure_paths,
        report_path=report_path,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Define treatment exposure for RWE study.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_treatment_exposure(args.data_dir, args.report_dir)


if __name__ == "__main__":
    main()
