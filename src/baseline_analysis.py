"""Step 3: Baseline characteristics analysis for RWE comparative effectiveness studies.

Generates Table 1-style baseline comparisons between treatment groups with
statistical tests, standardized mean differences (SMD), visualizations, and
an HTML report — following pharmaceutical observational study conventions.
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
from scipy import stats
from statsmodels.stats.weightstats import ttest_ind

from cohort_definition import (
    DEFAULT_DATA_DIR,
    DEFAULT_REPORT_DIR,
    TREATMENT_GROUP_METFORMIN,
    TREATMENT_GROUP_OTHER,
    load_conditions,
    load_observations,
    parse_datetime,
)
from baseline_observations import attach_baseline_labs

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RANDOM_SEED = 42
SMD_BALANCE_THRESHOLD = 0.1

# Treatment arm labels for Table 1 column headers
TREATMENT_A = TREATMENT_GROUP_METFORMIN
TREATMENT_B = TREATMENT_GROUP_OTHER

# Baseline comorbidities identified from conditions.csv DESCRIPTION at/before index_date
COMORBIDITY_PATTERNS: dict[str, re.Pattern[str]] = {
    "Hypertension": re.compile(r"(?i)hypertension"),
    "Hyperlipidemia": re.compile(r"(?i)hyperlipidemia"),
    "Obesity": re.compile(r"(?i)obesity|body mass index 30"),
    "Cardiovascular disease": re.compile(
        r"(?i)ischemic heart disease|heart failure|coronary|cardiovascular disease"
    ),
    "Chronic kidney disease": re.compile(r"(?i)chronic kidney disease"),
    "Diabetic nephropathy": re.compile(
        r"(?i)kidney due to diabetes|albuminuria due to type 2|proteinuria due to type 2"
    ),
    "Diabetic neuropathy": re.compile(r"(?i)neuropathy due to type 2 diabetes"),
    "Diabetic retinopathy": re.compile(
        r"(?i)retinopathy due to type 2 diabetes|macular edema and retinopathy"
    ),
}


@dataclass
class BaselineAnalysisResult:
    patient_data: pd.DataFrame
    table1: pd.DataFrame
    figure_paths: list[Path] = field(default_factory=list)
    report_path: Path | None = None


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_study_cohort(report_dir: Path) -> pd.DataFrame:
    """Load Step 2 study population."""
    path = report_dir / "study_population.csv"
    if not path.is_file():
        raise FileNotFoundError(
            f"Study population not found: {path}. Run cohort_definition.py (Step 2) first."
        )
    df = pd.read_csv(path)
    df["index_date"] = parse_datetime(df["index_date"])
    logger.info("Loaded study cohort: N=%s from %s", len(df), path)
    return df


def standardized_mean_difference(x_a: np.ndarray, x_b: np.ndarray) -> float:
    """Cohen-like SMD: difference in means divided by pooled standard deviation.

    Used in pharmacoepidemiology to assess baseline covariate balance before
    propensity score weighting. |SMD| < 0.1 indicates negligible imbalance.
    """
    x_a = np.asarray(x_a, dtype=float)
    x_b = np.asarray(x_b, dtype=float)
    x_a = x_a[~np.isnan(x_a)]
    x_b = x_b[~np.isnan(x_b)]
    if len(x_a) == 0 or len(x_b) == 0:
        return np.nan
    m_a, m_b = np.mean(x_a), np.mean(x_b)
    v_a = np.var(x_a, ddof=1) if len(x_a) > 1 else np.var(x_a, ddof=0)
    v_b = np.var(x_b, ddof=1) if len(x_b) > 1 else np.var(x_b, ddof=0)
    pooled = np.sqrt((v_a + v_b) / 2)
    if pooled == 0:
        return 0.0
    return float((m_a - m_b) / pooled)


def significance_label(p_value: float) -> str:
    """Map p-value to conventional significance stars for Table 1 footnotes."""
    if np.isnan(p_value):
        return ""
    if p_value < 0.001:
        return "***"
    if p_value < 0.01:
        return "**"
    if p_value < 0.05:
        return "*"
    return "NS"


def is_approximately_normal(values: np.ndarray, alpha: float = 0.05) -> bool:
    """Shapiro-Wilk normality check; used to select t-test vs Mann-Whitney."""
    values = values[~np.isnan(values)]
    if len(values) < 3:
        return False
    if len(values) > 5000:
        values = np.random.default_rng(RANDOM_SEED).choice(values, size=5000, replace=False)
    stat, p = stats.shapiro(values)
    return p >= alpha


def compare_continuous(
    values_a: np.ndarray,
    values_b: np.ndarray,
) -> dict[str, float | str]:
    """Two-sample comparison for continuous baseline variables."""
    values_a = values_a[~np.isnan(values_a)]
    values_b = values_b[~np.isnan(values_b)]

    t_stat, t_p = stats.ttest_ind(values_a, values_b, equal_var=False)
    u_stat, u_p = stats.mannwhitneyu(values_a, values_b, alternative="two-sided")

    # statsmodels Welch t-test (reproducible cross-check for continuous comparisons)
    sm_t, sm_p, _ = ttest_ind(values_a, values_b, usevar="unequal")

    normal_a = is_approximately_normal(values_a)
    normal_b = is_approximately_normal(values_b)
    use_mwu = not (normal_a and normal_b)
    primary_test = "Mann-Whitney U" if use_mwu else "Welch t-test"
    primary_p = float(u_p if use_mwu else t_p)

    return {
        "t_statistic": float(t_stat),
        "t_p_value": float(t_p),
        "statsmodels_t_p_value": float(sm_p),
        "mwu_statistic": float(u_stat),
        "mwu_p_value": float(u_p),
        "primary_test": primary_test,
        "p_value": primary_p,
        "significance": significance_label(primary_p),
    }


def compare_categorical(
    counts_a: pd.Series,
    counts_b: pd.Series,
) -> dict[str, float | str]:
    """Chi-square test of independence for categorical baseline variables."""
    table = pd.DataFrame({"A": counts_a, "B": counts_b}).fillna(0).astype(int)
    if table.shape[0] < 2 or table.shape[1] < 2:
        return {
            "chi2_statistic": np.nan,
            "p_value": np.nan,
            "primary_test": "Chi-square",
            "significance": "",
        }

    chi2, p, dof, _ = stats.chi2_contingency(table.T.values)
    if table.shape == (2, 2) and np.any(stats.chi2_contingency(table.T.values)[3] < 5):
        _, p = stats.fisher_exact(table.T.values)

    return {
        "chi2_statistic": float(chi2),
        "p_value": float(p),
        "primary_test": "Chi-square",
        "significance": significance_label(float(p)),
    }


def _format_mean_sd(values: pd.Series) -> str:
    values = values.dropna()
    if values.empty:
        return "—"
    return f"{values.mean():.1f} ({values.std():.1f})"


def _format_median_iqr(values: pd.Series) -> str:
    values = values.dropna()
    if values.empty:
        return "—"
    q1, med, q3 = values.quantile([0.25, 0.5, 0.75])
    return f"{med:.1f} ({q1:.1f}–{q3:.1f})"


def _format_n_pct(n: int, total: int) -> str:
    if total == 0:
        return "0 (0.0%)"
    return f"{n:,} ({100 * n / total:.1f}%)"


def flag_comorbidities(
    conditions: pd.DataFrame,
    study_population: pd.DataFrame,
) -> pd.DataFrame:
    """Patient-level binary comorbidity flags at or before index_date."""
    rows: list[dict[str, object]] = []

    for row in study_population.itertuples(index=False):
        patient_id = row.patient_id
        index_date = row.index_date
        patient_conds = conditions[
            (conditions["PATIENT"] == patient_id) & (conditions["START"] <= index_date)
        ]

        record: dict[str, object] = {
            "patient_id": patient_id,
            "treatment_group": row.treatment_group,
            "age": row.age,
            "gender": row.gender,
            "race": row.race,
            "index_date": index_date,
        }

        for name, pattern in COMORBIDITY_PATTERNS.items():
            record[name] = int(
                patient_conds["DESCRIPTION"]
                .astype(str)
                .str.contains(pattern, regex=True)
                .any()
            )
        rows.append(record)

    return pd.DataFrame(rows)


def build_table1(patient_data: pd.DataFrame) -> pd.DataFrame:
    """Construct publication-style Table 1 with tests and SMD."""
    df_a = patient_data[patient_data["treatment_group"] == TREATMENT_A]
    df_b = patient_data[patient_data["treatment_group"] == TREATMENT_B]
    df_all = patient_data

    n_a, n_b, n_all = len(df_a), len(df_b), len(df_all)
    rows: list[dict[str, object]] = []

    def add_row(
        characteristic: str,
        section: str,
        value_a: str,
        value_b: str,
        value_overall: str,
        smd: float,
        p_value: float,
        primary_test: str,
        significance: str,
        variable_type: str,
        t_p: float = np.nan,
        mwu_p: float = np.nan,
        chi2: float = np.nan,
    ) -> None:
        rows.append(
            {
                "section": section,
                "characteristic": characteristic,
                "treatment_a": value_a,
                "treatment_b": value_b,
                "overall": value_overall,
                "smd": round(smd, 3) if not np.isnan(smd) else np.nan,
                "balanced": abs(smd) < SMD_BALANCE_THRESHOLD if not np.isnan(smd) else np.nan,
                "primary_test": primary_test,
                "p_value": round(p_value, 4) if not np.isnan(p_value) else np.nan,
                "t_p_value": round(t_p, 4) if not np.isnan(t_p) else np.nan,
                "mwu_p_value": round(mwu_p, 4) if not np.isnan(mwu_p) else np.nan,
                "chi2_statistic": round(chi2, 3) if not np.isnan(chi2) else np.nan,
                "significance": significance,
                "variable_type": variable_type,
            }
        )

    # --- Demographics ---
    add_row(
        "N",
        "Demographics",
        f"{n_a:,}",
        f"{n_b:,}",
        f"{n_all:,}",
        0.0,
        np.nan,
        "—",
        "",
        "count",
    )

    age_cmp = compare_continuous(df_a["age"].to_numpy(), df_b["age"].to_numpy())
    add_row(
        "Age, years — mean (SD)",
        "Demographics",
        _format_mean_sd(df_a["age"]),
        _format_mean_sd(df_b["age"]),
        _format_mean_sd(df_all["age"]),
        standardized_mean_difference(df_a["age"].to_numpy(), df_b["age"].to_numpy()),
        age_cmp["p_value"],
        str(age_cmp["primary_test"]),
        str(age_cmp["significance"]),
        "continuous",
        t_p=float(age_cmp["t_p_value"]),
        mwu_p=float(age_cmp["mwu_p_value"]),
    )

    add_row(
        "Age, years — median (IQR)",
        "Demographics",
        _format_median_iqr(df_a["age"]),
        _format_median_iqr(df_b["age"]),
        _format_median_iqr(df_all["age"]),
        np.nan,
        np.nan,
        "—",
        "",
        "continuous",
    )

    add_row(
        "Age, years — min / max",
        "Demographics",
        f"{df_a['age'].min():.1f} / {df_a['age'].max():.1f}",
        f"{df_b['age'].min():.1f} / {df_b['age'].max():.1f}",
        f"{df_all['age'].min():.1f} / {df_all['age'].max():.1f}",
        np.nan,
        np.nan,
        "—",
        "",
        "continuous",
    )

    def add_continuous_lab(col: str, label: str, section: str = "Clinical measurements") -> None:
        if col not in patient_data.columns:
            return
        cmp = compare_continuous(df_a[col].to_numpy(), df_b[col].to_numpy())
        n_miss_a = int(df_a[col].isna().sum())
        n_miss_b = int(df_b[col].isna().sum())
        add_row(
            f"{label} — mean (SD)",
            section,
            _format_mean_sd(df_a[col]),
            _format_mean_sd(df_b[col]),
            _format_mean_sd(df_all[col]),
            standardized_mean_difference(df_a[col].to_numpy(), df_b[col].to_numpy()),
            cmp["p_value"],
            str(cmp["primary_test"]),
            str(cmp["significance"]),
            "continuous",
            t_p=float(cmp["t_p_value"]),
            mwu_p=float(cmp["mwu_p_value"]),
        )
        add_row(
            f"{label} — median (IQR)",
            section,
            _format_median_iqr(df_a[col]),
            _format_median_iqr(df_b[col]),
            _format_median_iqr(df_all[col]),
            np.nan,
            np.nan,
            "—",
            "",
            "continuous",
        )
        add_row(
            f"{label} — missing, n",
            section,
            str(n_miss_a),
            str(n_miss_b),
            str(int(df_all[col].isna().sum())),
            np.nan,
            np.nan,
            "—",
            "",
            "count",
        )

    add_continuous_lab("baseline_hba1c", "HbA1c (%)")
    add_continuous_lab("baseline_bmi", "BMI (kg/m2)")

    # Gender
    gender_levels = sorted(patient_data["gender"].dropna().unique())
    gender_table_a = df_a["gender"].value_counts()
    gender_table_b = df_b["gender"].value_counts()
    gender_cmp = compare_categorical(
        df_a["gender"].value_counts(),
        df_b["gender"].value_counts(),
    )
    for i, level in enumerate(gender_levels):
        n_level_a = int(gender_table_a.get(level, 0))
        n_level_b = int(gender_table_b.get(level, 0))
        n_level_all = int((patient_data["gender"] == level).sum())
        binary_a = (df_a["gender"] == level).astype(int).to_numpy()
        binary_b = (df_b["gender"] == level).astype(int).to_numpy()
        add_row(
            f"  Gender: {level}",
            "Demographics",
            _format_n_pct(n_level_a, n_a),
            _format_n_pct(n_level_b, n_b),
            _format_n_pct(n_level_all, n_all),
            standardized_mean_difference(binary_a, binary_b),
            gender_cmp["p_value"] if i == 0 else np.nan,
            gender_cmp["primary_test"] if i == 0 else "—",
            gender_cmp["significance"] if i == 0 else "",
            "categorical",
            chi2=float(gender_cmp["chi2_statistic"]) if i == 0 else np.nan,
        )

    # Race
    race_levels = sorted(patient_data["race"].dropna().unique())
    race_cmp = compare_categorical(
        df_a["race"].value_counts(),
        df_b["race"].value_counts(),
    )
    for i, level in enumerate(race_levels):
        n_level_a = int((df_a["race"] == level).sum())
        n_level_b = int((df_b["race"] == level).sum())
        n_level_all = int((patient_data["race"] == level).sum())
        binary_a = (df_a["race"] == level).astype(int).to_numpy()
        binary_b = (df_b["race"] == level).astype(int).to_numpy()
        add_row(
            f"  Race: {level}",
            "Demographics",
            _format_n_pct(n_level_a, n_a),
            _format_n_pct(n_level_b, n_b),
            _format_n_pct(n_level_all, n_all),
            standardized_mean_difference(binary_a, binary_b),
            race_cmp["p_value"] if i == 0 else np.nan,
            race_cmp["primary_test"] if i == 0 else "—",
            race_cmp["significance"] if i == 0 else "",
            "categorical",
            chi2=float(race_cmp["chi2_statistic"]) if i == 0 else np.nan,
        )

    # --- Clinical comorbidities ---
    for comorbidity in COMORBIDITY_PATTERNS:
        col_a = df_a[comorbidity].to_numpy()
        col_b = df_b[comorbidity].to_numpy()
        n_com_a = int(col_a.sum())
        n_com_b = int(col_b.sum())
        n_com_all = int(patient_data[comorbidity].sum())

        # 2x2 chi-square for binary comorbidity
        table = np.array(
            [
                [n_com_a, n_a - n_com_a],
                [n_com_b, n_b - n_com_b],
            ]
        )
        chi2, p, _, expected = stats.chi2_contingency(table)
        if table.shape == (2, 2) and np.any(expected < 5):
            _, p = stats.fisher_exact(table)

        add_row(
            comorbidity,
            "Clinical characteristics",
            _format_n_pct(n_com_a, n_a),
            _format_n_pct(n_com_b, n_b),
            _format_n_pct(n_com_all, n_all),
            standardized_mean_difference(col_a, col_b),
            float(p),
            "Chi-square / Fisher",
            significance_label(float(p)),
            "binary",
            chi2=float(chi2),
        )

    table1 = pd.DataFrame(rows)
    table1.rename(
        columns={
            "treatment_a": TREATMENT_A,
            "treatment_b": TREATMENT_B,
        },
        inplace=True,
    )
    return table1


def create_figures(
    patient_data: pd.DataFrame,
    table1: pd.DataFrame,
    figures_dir: Path,
) -> list[Path]:
    """Generate baseline visualizations for the HTML report."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")
    paths: list[Path] = []

    # 1. Age distribution
    fig, ax = plt.subplots(figsize=(10, 5))
    for group, color in [(TREATMENT_A, "#2980b9"), (TREATMENT_B, "#c0392b")]:
        subset = patient_data[patient_data["treatment_group"] == group]["age"]
        sns.kdeplot(subset, ax=ax, label=group, fill=True, alpha=0.35, color=color)
    ax.set_xlabel("Age (years)")
    ax.set_ylabel("Density")
    ax.set_title("Age Distribution by Treatment Group")
    ax.legend()
    age_path = figures_dir / "age_distribution.png"
    fig.tight_layout()
    fig.savefig(age_path, dpi=150)
    plt.close(fig)
    paths.append(age_path)
    logger.info("Saved figure: %s", age_path)

    # 2. Treatment group size
    fig, ax = plt.subplots(figsize=(7, 5))
    counts = patient_data["treatment_group"].value_counts()
    colors = ["#2980b9", "#c0392b"]
    bars = ax.bar(counts.index, counts.values, color=colors, edgecolor="white")
    ax.set_ylabel("Number of patients")
    ax.set_title("Study Population by Treatment Group")
    for bar, val in zip(bars, counts.values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5,
            f"{val:,}",
            ha="center",
            va="bottom",
            fontweight="bold",
        )
    plt.xticks(rotation=15, ha="right")
    size_path = figures_dir / "treatment_group_size.png"
    fig.tight_layout()
    fig.savefig(size_path, dpi=150)
    plt.close(fig)
    paths.append(size_path)
    logger.info("Saved figure: %s", size_path)

    # 3. Love plot (SMD)
    smd_df = table1.dropna(subset=["smd"]).copy()
    smd_df = smd_df[smd_df["characteristic"].str.strip() != "N"]
    if not smd_df.empty:
        smd_df = smd_df.sort_values("smd")
        fig, ax = plt.subplots(figsize=(10, max(6, len(smd_df) * 0.35)))
        colors = ["#27ae60" if abs(v) < SMD_BALANCE_THRESHOLD else "#e74c3c" for v in smd_df["smd"]]
        ax.barh(smd_df["characteristic"], smd_df["smd"], color=colors, edgecolor="white")
        ax.axvline(SMD_BALANCE_THRESHOLD, color="gray", linestyle="--", linewidth=1)
        ax.axvline(-SMD_BALANCE_THRESHOLD, color="gray", linestyle="--", linewidth=1)
        ax.axvline(0, color="black", linewidth=0.8)
        ax.set_xlabel("Standardized Mean Difference (Treatment A − Treatment B)")
        ax.set_title("Baseline Covariate Balance — Love Plot")
        smd_path = figures_dir / "baseline_smd_love_plot.png"
        fig.tight_layout()
        fig.savefig(smd_path, dpi=150)
        plt.close(fig)
        paths.append(smd_path)
        logger.info("Saved figure: %s", smd_path)

    return paths


def _table_html(df: pd.DataFrame, columns: list[str]) -> str:
    header = "".join(f"<th>{html.escape(str(c))}</th>" for c in columns)
    body_rows = []
    for _, row in df.iterrows():
        cells = "".join(f"<td>{html.escape(str(row[c]))}</td>" for c in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def write_html_report(
    patient_data: pd.DataFrame,
    table1: pd.DataFrame,
    figure_paths: list[Path],
    report_path: Path,
) -> None:
    """Generate baseline characteristics HTML report."""
    n = len(patient_data)
    n_a = int((patient_data["treatment_group"] == TREATMENT_A).sum())
    n_b = int((patient_data["treatment_group"] == TREATMENT_B).sum())

    demo_table = table1[table1["section"] == "Demographics"]
    labs_table = table1[table1["section"] == "Clinical measurements"]
    clinical_table = table1[table1["section"] == "Clinical characteristics"]

    display_cols = [
        "characteristic",
        TREATMENT_A,
        TREATMENT_B,
        "overall",
        "smd",
        "p_value",
        "significance",
        "primary_test",
    ]

    smd_balanced = table1["balanced"].sum()
    smd_total = table1["balanced"].notna().sum()
    imbalanced = table1[table1["balanced"] == False]  # noqa: E712

    figure_html = ""
    for fig_path in figure_paths:
        rel = fig_path.name
        figure_html += f'<figure><img src="figures/{html.escape(rel)}" alt="{html.escape(rel)}"><figcaption>{html.escape(rel)}</figcaption></figure>\n'

    interpretation = f"""
    <p>The analytic cohort comprised <strong>{n:,}</strong> adult patients with Type 2 Diabetes
    initiating pharmacotherapy after diagnosis. Treatment Group A (Metformin users, n={n_a:,})
    and Treatment Group B (Other diabetes medication users, n={n_b:,}) were compared on baseline
    demographics and clinical characteristics prior to outcome analysis.</p>
    <p>Continuous variables are summarized as mean (SD) and median (IQR). Categorical variables
    are reported as n (%). Between-group comparisons used Welch's t-test or Mann-Whitney U test
    (when normality assumptions were not met) for continuous variables, and chi-square or Fisher's
    exact test for categorical variables.</p>
    <p>Standardized mean differences (SMD) quantify baseline imbalance. Of {smd_total} evaluated
    variables, {int(smd_balanced)} had |SMD| &lt; {SMD_BALANCE_THRESHOLD} indicating acceptable balance.
    Variables with |SMD| ≥ {SMD_BALANCE_THRESHOLD} suggest residual confounding that should be
    addressed in propensity score modeling (Step 4).</p>
    """

    if not imbalanced.empty:
        vars_list = ", ".join(imbalanced["characteristic"].tolist()[:8])
        interpretation += f"<p><strong>Imbalanced variables (|SMD| ≥ {SMD_BALANCE_THRESHOLD}):</strong> {html.escape(vars_list)}.</p>"

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Baseline Characteristics Report — RWE Diabetes Study</title>
  <style>
    body {{ font-family: "Segoe UI", Tahoma, sans-serif; margin: 0; background: #f4f7fb; color: #1f2937; }}
    .container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
    header {{ background: linear-gradient(135deg, #1e3a8a, #2563eb); color: #fff; padding: 28px; border-radius: 12px; margin-bottom: 24px; }}
    section {{ background: #fff; border: 1px solid #dbe3ef; border-radius: 10px; padding: 20px; margin-bottom: 20px; }}
    h2 {{ color: #1d4ed8; margin-top: 0; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; }}
    th, td {{ border-bottom: 1px solid #dbe3ef; padding: 8px 10px; text-align: left; }}
    th {{ background: #eef2ff; }}
    figure {{ margin: 16px 0; text-align: center; }}
    img {{ max-width: 100%; border: 1px solid #dbe3ef; border-radius: 8px; }}
    figcaption {{ color: #6b7280; font-size: 0.85rem; margin-top: 6px; }}
    .note {{ color: #6b7280; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Baseline Characteristics Report</h1>
      <p>Step 3 — Real-World Evidence Pipeline | Metformin vs Other Diabetes Medications</p>
      <p>Study population: Synthea synthetic EHR | N = {n:,}</p>
    </header>

    <section>
      <h2>Study Population Description</h2>
      {interpretation}
    </section>

    <section>
      <h2>Table 1 — Demographic Characteristics</h2>
      <p class="note">Treatment A: {html.escape(TREATMENT_A)} | Treatment B: {html.escape(TREATMENT_B)}</p>
      <p class="note">Significance: * p&lt;0.05, ** p&lt;0.01, *** p&lt;0.001, NS = not significant</p>
      {_table_html(demo_table, display_cols)}
    </section>

    <section>
      <h2>Table 1 — Clinical Measurements (Pre-Index Labs)</h2>
      <p class="note">HbA1c and BMI extracted from Synthea observations.csv (LOINC 4548-4, 39156-5):
      most recent value on or before index_date (365-day lookback when available). Missing values
      reported separately; median imputation applied in propensity score models (Steps 6–7).</p>
      {_table_html(labs_table, display_cols) if not labs_table.empty else "<p>No laboratory data available.</p>"}
    </section>

    <section>
      <h2>Table 1 — Clinical Characteristics (Baseline Comorbidities)</h2>
      <p class="note">Comorbidities ascertained from conditions recorded at or before index_date.</p>
      {_table_html(clinical_table, display_cols)}
    </section>

    <section>
      <h2>Visualizations</h2>
      {figure_html}
    </section>

    <section>
      <h2>SMD Balance Assessment</h2>
      <p>|SMD| &lt; {SMD_BALANCE_THRESHOLD} indicates good balance per pharmacoepidemiologic convention.
      See Love plot for graphical assessment.</p>
    </section>
  </div>
</body>
</html>
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(doc, encoding="utf-8")
    logger.info("HTML report written to: %s", report_path)


def run_baseline_analysis(
    data_dir: Path | None = None,
    report_dir: Path | None = None,
) -> BaselineAnalysisResult:
    """Execute Step 3 baseline characteristics analysis."""
    np.random.seed(RANDOM_SEED)
    configure_logging()

    data_dir = (data_dir or DEFAULT_DATA_DIR).resolve()
    report_dir = (report_dir or DEFAULT_REPORT_DIR).resolve()
    figures_dir = report_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Starting baseline characteristics analysis")
    logger.info("Data directory: %s", data_dir)
    logger.info("Report directory: %s", report_dir)

    study_population = load_study_cohort(report_dir)
    conditions = load_conditions(data_dir)
    observations = load_observations(data_dir)
    patient_data = flag_comorbidities(conditions, study_population)
    patient_data = attach_baseline_labs(patient_data, observations)

    table1 = build_table1(patient_data)
    table_path = report_dir / "baseline_characteristics_table.csv"
    table1.to_csv(table_path, index=False)
    logger.info("Table 1 saved to: %s", table_path)

    figure_paths = create_figures(patient_data, table1, figures_dir)

    report_path = report_dir / "baseline_characteristics_report.html"
    write_html_report(patient_data, table1, figure_paths, report_path)

    print("=" * 72)
    print("BASELINE CHARACTERISTICS ANALYSIS — STEP 3")
    print("=" * 72)
    print(f"Cohort N = {len(patient_data)}")
    print(f"  {TREATMENT_A}: {(patient_data['treatment_group'] == TREATMENT_A).sum()}")
    print(f"  {TREATMENT_B}: {(patient_data['treatment_group'] == TREATMENT_B).sum()}")
    print(f"\nTable 1: {table_path}")
    print(f"HTML report: {report_path}")
    print(f"Figures: {figures_dir}")
    print("=" * 72)

    return BaselineAnalysisResult(
        patient_data=patient_data,
        table1=table1,
        figure_paths=figure_paths,
        report_path=report_path,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Step 3 baseline characteristics analysis."
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_baseline_analysis(args.data_dir, args.report_dir)


if __name__ == "__main__":
    main()
