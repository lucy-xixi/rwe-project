"""Step 6: Propensity score and causal inference for RWE comparative effectiveness.

Estimates adjusted treatment effects of metformin vs other diabetes medications
using propensity score matching, balance diagnostics, logistic regression on
matched cohorts, risk differences, and IPTW — following pharmaceutical
observational causal inference methodology.
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
from lifelines import CoxPHFitter
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from baseline_analysis import standardized_mean_difference
from baseline_observations import attach_baseline_labs
from cohort_definition import (
    DEFAULT_DATA_DIR,
    DEFAULT_REPORT_DIR,
    TREATMENT_GROUP_METFORMIN,
    TREATMENT_GROUP_OTHER,
    load_conditions,
    load_observations,
    parse_datetime,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RANDOM_SEED = 42
SMD_THRESHOLD = 0.1
DEFAULT_CALIPER_SD = 0.2

TREATMENT_A = TREATMENT_GROUP_METFORMIN
TREATMENT_B = TREATMENT_GROUP_OTHER

# Confounders measured at or before index_date (pre-treatment initiation)
CONFOUNDER_PATTERNS: dict[str, re.Pattern[str]] = {
    "hypertension": re.compile(r"(?i)hypertension"),
    "cardiovascular_disease": re.compile(
        r"(?i)ischemic heart disease|heart failure|coronary|cardiovascular disease|stroke"
    ),
    "obesity": re.compile(r"(?i)obesity|body mass index 30"),
    "hyperlipidemia": re.compile(r"(?i)hyperlipidemia"),
    "chronic_kidney_disease": re.compile(r"(?i)chronic kidney disease|kidney due to diabetes"),
}

CONFOUNDER_COLUMNS = [
    "age",
    "female",
    "baseline_hba1c",
    "baseline_bmi",
    "hypertension",
    "cardiovascular_disease",
    "obesity",
    "hyperlipidemia",
    "chronic_kidney_disease",
]


@dataclass
class CausalInferenceResult:
    analysis_data: pd.DataFrame
    propensity_scores: pd.DataFrame
    matched_cohort: pd.DataFrame
    balance: pd.DataFrame
    treatment_effects: pd.DataFrame
    sensitivity: pd.DataFrame
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
        raise FileNotFoundError(f"Missing {path}. Run Step 2 first.")
    df = pd.read_csv(path)
    df["index_date"] = parse_datetime(df["index_date"])
    return df


def load_outcome_data(report_dir: Path) -> pd.DataFrame:
    """Load outcome records; accepts outcome_dataset.csv or outcome_events.csv."""
    for name in ("outcome_dataset.csv", "outcome_events.csv"):
        path = report_dir / name
        if path.is_file():
            df = pd.read_csv(path)
            if "outcome_date" in df.columns:
                df["outcome_date"] = parse_datetime(df["outcome_date"])
            logger.info("Loaded outcomes from %s", path)
            return df
    raise FileNotFoundError("No outcome file found. Run Step 5 outcome analysis first.")


def load_treatment_exposure(report_dir: Path) -> pd.DataFrame:
    for name in ("treatment_exposure.csv", "exposure_dataset.csv", "treatment_initiation.csv"):
        path = report_dir / name
        if path.is_file():
            df = pd.read_csv(path)
            for col in ("treatment_start_date", "index_date"):
                if col in df.columns:
                    df[col] = parse_datetime(df[col])
            return df
    raise FileNotFoundError("No treatment exposure file found. Run Step 4 first.")


def build_confounders(
    study_population: pd.DataFrame,
    conditions: pd.DataFrame,
    observations: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Assemble pre-treatment confounders for propensity score modeling."""
    rows: list[dict[str, object]] = []

    for row in study_population.itertuples(index=False):
        if row.treatment_group not in (TREATMENT_A, TREATMENT_B):
            continue

        patient_id = row.patient_id
        index_date = row.index_date
        patient_conds = conditions[
            (conditions["PATIENT"] == patient_id) & (conditions["START"] <= index_date)
        ]

        record: dict[str, object] = {
            "patient_id": patient_id,
            "age": row.age,
            "female": int(row.gender == "F"),
            "gender": row.gender,
            "treatment_group": row.treatment_group,
            "treatment_metformin": int(row.treatment_group == TREATMENT_A),
            "index_date": index_date,
        }

        for name, pattern in CONFOUNDER_PATTERNS.items():
            record[name] = int(
                patient_conds["DESCRIPTION"].astype(str).str.contains(pattern, regex=True).any()
            )
        rows.append(record)

    df = pd.DataFrame(rows)
    if observations is not None and not observations.empty:
        df = attach_baseline_labs(df, observations)
    else:
        df["baseline_hba1c"] = np.nan
        df["baseline_bmi"] = np.nan
    return df


def attach_outcome(
    confounders: pd.DataFrame,
    outcome_events: pd.DataFrame,
    followup: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Attach primary outcome: diabetes complication or hospitalization."""
    df = confounders.copy()

    # Primary outcome definition aligned with Step 5
    primary_types = {
        "primary_composite_event",
        "diabetes_complication",
        "hospitalization_event",
    }
    primary = outcome_events[outcome_events["outcome_type"].isin(primary_types)].copy()

    if "primary_composite_event" in outcome_events["outcome_type"].values:
        event_patients = set(
            outcome_events[outcome_events["outcome_type"] == "primary_composite_event"]["patient_id"]
        )
    else:
        event_patients = set(primary["patient_id"].unique())

    df["outcome"] = df["patient_id"].isin(event_patients).astype(int)

    if followup is not None and "followup_days" in followup.columns:
        df = df.merge(
            followup[["patient_id", "followup_days", "followup_years"]],
            on="patient_id",
            how="left",
        )
        df["duration_days"] = df["followup_days"].fillna(730).clip(lower=1)
    else:
        df["duration_days"] = 730

    return df


def fit_propensity_score_model(
    data: pd.DataFrame,
    covariates: list[str] | None = None,
) -> tuple[pd.DataFrame, str]:
    """Estimate P(Treatment = Metformin | Covariates) via logistic regression.

    Primary estimation uses statsmodels GLM (Binomial, logit) for inference-ready
    output. scikit-learn logistic regression provides cross-validation diagnostics.
    """
    covariates = covariates or CONFOUNDER_COLUMNS
    y = data["treatment_metformin"]
    X = data[covariates].copy()

    for col in X.columns:
        if X[col].isna().any():
            X[col] = X[col].fillna(X[col].median())

    X_const = sm.add_constant(X, has_constant="add")
    glm = sm.GLM(y, X_const, family=sm.families.Binomial())
    fit = glm.fit(cov_type="HC1")
    ps = np.clip(fit.predict(X_const), 0.01, 0.99)

    scores = data[["patient_id", "treatment_metformin", "treatment_group", "outcome"]].copy()
    scores["propensity_score"] = ps
    scores["logit_propensity_score"] = np.log(ps / (1 - ps))

    # sklearn cross-validated discrimination (pharmaceutical PS diagnostic)
    sk_pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("logit", LogisticRegression(max_iter=2000, C=1.0, random_state=RANDOM_SEED)),
    ])
    sk_pipe.fit(X, y)
    scores["sklearn_propensity_score"] = np.clip(sk_pipe.predict_proba(X)[:, 1], 0.01, 0.99)

    return scores, fit.summary().as_text()


def compute_balance_table(
    data: pd.DataFrame,
    covariates: list[str],
    label: str,
) -> pd.DataFrame:
    """SMD for Metformin vs Other (positive SMD = higher in Metformin group)."""
    treated = data[data["treatment_metformin"] == 1]
    control = data[data["treatment_metformin"] == 0]
    rows = []

    for col in covariates:
        x_t = treated[col].astype(float).to_numpy()
        x_c = control[col].astype(float).to_numpy()

        if label.endswith("IPTW") and "iptw_weight" in data.columns:
            wt = treated["iptw_weight"]
            wc = control["iptw_weight"]
            m_t = np.average(x_t, weights=wt)
            m_c = np.average(x_c, weights=wc)
            v_t = np.average((x_t - m_t) ** 2, weights=wt)
            v_c = np.average((x_c - m_c) ** 2, weights=wc)
            pooled = np.sqrt((v_t + v_c) / 2)
            smd = float((m_t - m_c) / pooled) if pooled else 0.0
        else:
            smd = standardized_mean_difference(x_t, x_c)

        rows.append(
            {
                "covariate": col,
                "analysis_stage": label,
                "smd": round(float(smd), 3),
                "balanced": abs(smd) < SMD_THRESHOLD,
            }
        )

    return pd.DataFrame(rows)


def propensity_score_match_1to1(
    data: pd.DataFrame,
    caliper_sd: float = DEFAULT_CALIPER_SD,
) -> pd.DataFrame:
    """1:1 nearest-neighbor PS matching without replacement (sklearn).

    Each Other medication user is matched to the nearest Metformin user on the
    logit propensity score scale within caliper_sd × SD(logit PS).
    """
    df = data.copy()
    logit_ps = df["logit_propensity_score"].to_numpy()
    caliper = caliper_sd * np.std(logit_ps)
    if caliper == 0:
        caliper = 0.1

    treated = df[df["treatment_metformin"] == 1].reset_index(drop=True)
    control = df[df["treatment_metformin"] == 0].reset_index(drop=True)

    if treated.empty or control.empty:
        return pd.DataFrame()

    nn = NearestNeighbors(n_neighbors=1, algorithm="ball_tree")
    nn.fit(treated[["logit_propensity_score"]])
    distances, indices = nn.kneighbors(control[["logit_propensity_score"]])

    candidates: list[tuple[float, pd.Series, pd.Series]] = []
    for i in range(len(control)):
        dist = float(distances[i][0])
        trt_row = treated.iloc[int(indices[i][0])]
        if dist <= caliper:
            candidates.append((dist, control.iloc[i], trt_row))

    candidates.sort(key=lambda x: x[0])

    pairs: list[dict[str, object]] = []
    used_treated: set[str] = set()
    pair_id = 0

    for dist, ctrl_row, trt_row in candidates:
        if trt_row["patient_id"] in used_treated:
            continue
        used_treated.add(trt_row["patient_id"])
        pair_id += 1
        for patient_id, matched_id, role in [
            (ctrl_row["patient_id"], trt_row["patient_id"], "control"),
            (trt_row["patient_id"], ctrl_row["patient_id"], "treated"),
        ]:
            pairs.append(
                {
                    "patient_id": patient_id,
                    "matched_patient_id": matched_id,
                    "match_distance_logit_ps": dist,
                    "pair_id": pair_id,
                    "role": role,
                }
            )

    if not pairs:
        return pd.DataFrame()

    match_index = pd.DataFrame(pairs)
    matched_ids = set(match_index["patient_id"])
    matched = df[df["patient_id"].isin(matched_ids)].merge(
        match_index[["patient_id", "pair_id", "match_distance_logit_ps", "role"]],
        on="patient_id",
    )
    logger.info("Matched pairs: %s (caliper=%.3f SD)", pair_id, caliper_sd)
    return matched


def compute_iptw_weights(data: pd.DataFrame) -> pd.DataFrame:
    """Stabilized inverse probability of treatment weights."""
    df = data.copy()
    p_metformin = df["treatment_metformin"].mean()
    ps = df["propensity_score"]
    stabilized = np.where(
        df["treatment_metformin"] == 1,
        p_metformin / ps,
        (1 - p_metformin) / (1 - ps),
    )
    lo, hi = np.quantile(stabilized, [0.01, 0.99])
    df["iptw_weight"] = np.clip(stabilized, lo, hi)
    return df


def estimate_matched_logistic_effect(matched: pd.DataFrame) -> dict[str, object]:
    """Logistic regression on matched cohort: Outcome ~ Treatment (Metformin)."""
    if matched.empty or matched["outcome"].nunique() < 2:
        return {"method": "PSM logistic regression (matched cohort)", "estimate": np.nan, "note": "Insufficient data"}

    treated = matched[matched["treatment_metformin"] == 1]
    control = matched[matched["treatment_metformin"] == 0]
    if treated.empty or control.empty:
        return {"method": "PSM logistic regression (matched cohort)", "estimate": np.nan, "note": "Insufficient data"}

    def haldane_anscombe_or() -> tuple[float, float, float, float]:
        """Continuity-corrected OR (Other vs Metformin) for sparse matched tables."""
        a = float(treated["outcome"].sum())
        b = float(len(treated) - a)
        c = float(control["outcome"].sum())
        d = float(len(control) - c)
        or_est = ((c + 0.5) * (b + 0.5)) / ((a + 0.5) * (d + 0.5))
        log_or = np.log(or_est)
        se = np.sqrt(1 / (a + 0.5) + 1 / (b + 0.5) + 1 / (c + 0.5) + 1 / (d + 0.5))
        ci_lo = float(np.exp(log_or - 1.96 * se))
        ci_hi = float(np.exp(log_or + 1.96 * se))
        z = log_or / se if se else 0.0
        from scipy import stats

        p_val = float(2 * stats.norm.sf(abs(z)))
        return or_est, ci_lo, ci_hi, p_val

    try:
        X = sm.add_constant(matched["treatment_metformin"])
        fit = sm.GLM(matched["outcome"], X, family=sm.families.Binomial()).fit(cov_type="HC1")
        coef = float(fit.params["treatment_metformin"])
        if not np.isfinite(coef) or abs(coef) > 20:
            raise ValueError("Separation or unstable coefficient")
        or_est = float(np.exp(-coef))
        ci = fit.conf_int().loc["treatment_metformin"]
        ci_lo = float(np.exp(-ci[1]))
        ci_hi = float(np.exp(-ci[0]))
        p_val = float(fit.pvalues["treatment_metformin"])
    except (ValueError, np.linalg.LinAlgError, FloatingPointError):
        or_est, ci_lo, ci_hi, p_val = haldane_anscombe_or()

    return {
        "method": "PSM logistic regression (matched cohort)",
        "effect_measure": "Odds ratio (Other vs Metformin)",
        "estimate": round(or_est, 3),
        "ci_lower": round(ci_lo, 3),
        "ci_upper": round(ci_hi, 3),
        "p_value": round(p_val, 4),
        "n": len(matched),
        "n_pairs": matched["pair_id"].nunique() if "pair_id" in matched.columns else np.nan,
    }


def estimate_risk_difference(data: pd.DataFrame, label: str) -> dict[str, object]:
    """Absolute risk difference: P(outcome|Metformin) - P(outcome|Other)."""
    t = data[data["treatment_metformin"] == 1]
    c = data[data["treatment_metformin"] == 0]
    r_t = t["outcome"].mean()
    r_c = c["outcome"].mean()
    rd = r_t - r_c

    # Normal-approximation SE for risk difference
    se = np.sqrt(r_t * (1 - r_t) / len(t) + r_c * (1 - r_c) / len(c)) if len(t) and len(c) else np.nan
    z = 1.96
    return {
        "method": f"Risk difference ({label})",
        "effect_measure": "Risk difference (Metformin - Other)",
        "estimate": round(float(rd), 4),
        "ci_lower": round(float(rd - z * se), 4) if not np.isnan(se) else np.nan,
        "ci_upper": round(float(rd + z * se), 4) if not np.isnan(se) else np.nan,
        "p_value": np.nan,
        "n": len(data),
        "risk_metformin": round(float(r_t), 4),
        "risk_other": round(float(r_c), 4),
    }


def estimate_iptw_ate(data: pd.DataFrame) -> dict[str, object]:
    """IPTW average treatment effect on the outcome (risk difference scale)."""
    df = compute_iptw_weights(data)
    t = df[df["treatment_metformin"] == 1]
    c = df[df["treatment_metformin"] == 0]

    r_t = np.average(t["outcome"], weights=t["iptw_weight"])
    r_c = np.average(c["outcome"], weights=c["iptw_weight"])
    ate = r_t - r_c

    X = sm.add_constant(df["treatment_metformin"])
    wls = sm.GLM(
        df["outcome"], X, family=sm.families.Binomial(), freq_weights=df["iptw_weight"]
    ).fit(cov_type="HC1")
    or_other = float(np.exp(-wls.params["treatment_metformin"]))
    ci = wls.conf_int().loc["treatment_metformin"]

    iptw_row = {
        "method": "IPTW (stabilized weights)",
        "effect_measure": "Average treatment effect (risk difference)",
        "estimate": round(float(ate), 4),
        "ci_lower": np.nan,
        "ci_upper": np.nan,
        "p_value": round(float(wls.pvalues["treatment_metformin"]), 4),
        "n": len(df),
        "iptw_or_other_vs_metformin": round(or_other, 3),
        "iptw_or_ci_lower": round(float(np.exp(-ci[1])), 3),
        "iptw_or_ci_upper": round(float(np.exp(-ci[0])), 3),
        "risk_metformin_weighted": round(float(r_t), 4),
        "risk_other_weighted": round(float(r_c), 4),
    }
    return iptw_row


def estimate_iptw_cox(data: pd.DataFrame) -> dict[str, object]:
    """IPTW-weighted Cox model for time-to-outcome (lifelines)."""
    df = compute_iptw_weights(data.copy())
    if df["outcome"].sum() < 5:
        return {"method": "IPTW Cox PH", "estimate": np.nan, "note": "Insufficient events"}

    cox_df = df[["duration_days", "outcome", "treatment_metformin", "iptw_weight"]].copy()
    cph = CoxPHFitter()
    cph.fit(
        cox_df,
        duration_col="duration_days",
        event_col="outcome",
        weights_col="iptw_weight",
        robust=True,
        show_progress=False,
    )
    hr = float(np.exp(cph.params_["treatment_metformin"]))
    ci = cph.confidence_intervals_.loc["treatment_metformin"]
    return {
        "method": "IPTW Cox proportional hazards (lifelines)",
        "effect_measure": "Hazard ratio (Other vs Metformin)",
        "estimate": round(float(np.exp(-cph.params_["treatment_metformin"])), 3),
        "ci_lower": round(float(np.exp(-ci["95% upper-bound"])), 3),
        "ci_upper": round(float(np.exp(-ci["95% lower-bound"])), 3),
        "p_value": round(float(cph.summary.loc["treatment_metformin", "p"]), 4),
        "n": len(df),
        "n_events": int(df["outcome"].sum()),
    }


def run_sensitivity_analyses(
    data: pd.DataFrame,
    ps_scores: pd.DataFrame,
) -> pd.DataFrame:
    """Alternative calipers and reduced covariate PS models."""
    ps_cols = ["propensity_score", "logit_propensity_score", "sklearn_propensity_score"]
    base = data.drop(columns=ps_cols, errors="ignore")
    merged = base.merge(
        ps_scores[["patient_id", "propensity_score", "logit_propensity_score"]],
        on="patient_id",
    )
    rows = []

    for caliper in (0.1, 0.2, 0.3):
        matched = propensity_score_match_1to1(merged, caliper_sd=caliper)
        if matched.empty:
            continue
        effect = estimate_matched_logistic_effect(matched)
        balance = compute_balance_table(matched, CONFOUNDER_COLUMNS, f"PSM caliper={caliper}")
        pct_balanced = balance["balanced"].mean() * 100
        rows.append(
            {
                "analysis": f"PSM caliper {caliper} SD",
                "n_matched_pairs": matched["pair_id"].nunique(),
                "odds_ratio": effect.get("estimate"),
                "p_value": effect.get("p_value"),
                "pct_balanced": round(pct_balanced, 1),
            }
        )

    # Reduced covariate model (demographics only)
    reduced_cov = ["age", "female"]
    reduced_ps, _ = fit_propensity_score_model(merged, covariates=reduced_cov)
    reduced_merged = merged.drop(columns=ps_cols, errors="ignore").merge(
        reduced_ps[["patient_id", "propensity_score", "logit_propensity_score"]],
        on="patient_id",
    )
    matched_reduced = propensity_score_match_1to1(reduced_merged)
    if not matched_reduced.empty:
        effect = estimate_matched_logistic_effect(matched_reduced)
        rows.append(
            {
                "analysis": "PSM reduced covariate model (age, gender only)",
                "n_matched_pairs": matched_reduced["pair_id"].nunique(),
                "odds_ratio": effect.get("estimate"),
                "p_value": effect.get("p_value"),
                "pct_balanced": np.nan,
            }
        )

    return pd.DataFrame(rows)


def create_figures(
    data: pd.DataFrame,
    matched: pd.DataFrame,
    balance: pd.DataFrame,
    treatment_effects: pd.DataFrame,
    figures_dir: Path,
) -> list[Path]:
    """Generate causal inference visualizations."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")
    paths: list[Path] = []

    # 1. PS distribution before matching
    fig, ax = plt.subplots(figsize=(9, 5))
    for grp, color in [(1, "#2980b9"), (0, "#c0392b")]:
        label = TREATMENT_A if grp == 1 else TREATMENT_B
        sns.kdeplot(
            data[data["treatment_metformin"] == grp]["propensity_score"],
            ax=ax, fill=True, alpha=0.35, color=color, label=label,
        )
    ax.set_xlabel("Propensity score P(Metformin | X)")
    ax.set_title("Propensity Score Distribution — Before Matching")
    ax.legend()
    p1 = figures_dir / "ps_distribution_before_matching.png"
    fig.tight_layout()
    fig.savefig(p1, dpi=150)
    plt.close(fig)
    paths.append(p1)

    # 2. PS distribution after matching
    if not matched.empty:
        fig, ax = plt.subplots(figsize=(9, 5))
        for grp, color in [(1, "#2980b9"), (0, "#c0392b")]:
            label = TREATMENT_A if grp == 1 else TREATMENT_B
            sns.kdeplot(
                matched[matched["treatment_metformin"] == grp]["propensity_score"],
                ax=ax, fill=True, alpha=0.35, color=color, label=label,
            )
        ax.set_xlabel("Propensity score P(Metformin | X)")
        ax.set_title("Propensity Score Distribution — After Matching")
        ax.legend()
        p2 = figures_dir / "ps_distribution_after_matching.png"
        fig.tight_layout()
        fig.savefig(p2, dpi=150)
        plt.close(fig)
        paths.append(p2)

    # 3. Love plot
    love = balance.pivot(index="covariate", columns="analysis_stage", values="smd")
    if not love.empty:
        fig, ax = plt.subplots(figsize=(10, max(5, len(love) * 0.4)))
        for col in love.columns:
            ax.scatter(love[col], love.index, label=col, s=60)
        ax.axvline(SMD_THRESHOLD, color="gray", linestyle="--")
        ax.axvline(-SMD_THRESHOLD, color="gray", linestyle="--")
        ax.axvline(0, color="black", linewidth=0.8)
        ax.set_xlabel("Standardized Mean Difference")
        ax.set_title("Covariate Balance — Love Plot")
        ax.legend()
        p3 = figures_dir / "causal_inference_love_plot.png"
        fig.tight_layout()
        fig.savefig(p3, dpi=150)
        plt.close(fig)
        paths.append(p3)

    # 4. Treatment effect visualization
    plot_effects = treatment_effects[
        treatment_effects["effect_measure"].str.contains("Odds ratio|Hazard ratio", na=False)
    ].copy()
    if not plot_effects.empty:
        fig, ax = plt.subplots(figsize=(9, max(4, len(plot_effects) * 0.5)))
        y_pos = range(len(plot_effects))
        estimates = plot_effects["estimate"].astype(float)
        ax.errorbar(
            estimates, y_pos,
            xerr=[
                estimates - plot_effects["ci_lower"].astype(float),
                plot_effects["ci_upper"].astype(float) - estimates,
            ],
            fmt="o", color="#1d4ed8", capsize=4,
        )
        ax.axvline(1.0, color="gray", linestyle="--")
        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(plot_effects["method"])
        ax.set_xlabel("Effect estimate (OR/HR; reference Metformin)")
        ax.set_title("Adjusted Treatment Effect Estimates")
        p4 = figures_dir / "treatment_effect_estimates.png"
        fig.tight_layout()
        fig.savefig(p4, dpi=150)
        plt.close(fig)
        paths.append(p4)

    for p in paths:
        logger.info("Saved figure: %s", p)
    return paths


def write_html_report(
    data: pd.DataFrame,
    matched: pd.DataFrame,
    balance: pd.DataFrame,
    treatment_effects: pd.DataFrame,
    sensitivity: pd.DataFrame,
    ps_summary: str,
    figure_paths: list[Path],
    report_path: Path,
) -> None:
    """Generate RWE causal inference HTML report."""
    n = len(data)
    n_pairs = matched["pair_id"].nunique() if not matched.empty and "pair_id" in matched.columns else 0
    pct_bal = balance[balance["analysis_stage"].str.contains("After")]["balanced"].mean() * 100

    figure_html = "".join(
        f'<figure><img src="figures/{html.escape(p.name)}" alt="{html.escape(p.name)}">'
        f'<figcaption>{html.escape(p.name)}</figcaption></figure>'
        for p in figure_paths
    )

    causal_statement = (
        "Because this is an observational study, causal interpretation relies on assumptions "
        "including no unmeasured confounding and correct model specification."
    )

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Causal Inference Report — RWE Diabetes Study</title>
  <style>
    body {{ font-family: "Segoe UI", Tahoma, sans-serif; margin: 0; background: #f4f7fb; color: #1f2937; }}
    .container {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}
    header {{ background: linear-gradient(135deg, #1e3a8a, #2563eb); color: #fff; padding: 28px; border-radius: 12px; margin-bottom: 24px; }}
    section {{ background: #fff; border: 1px solid #dbe3ef; border-radius: 10px; padding: 20px; margin-bottom: 20px; }}
    h2 {{ color: #1d4ed8; margin-top: 0; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; }}
    th, td {{ border-bottom: 1px solid #dbe3ef; padding: 8px 10px; text-align: left; }}
    th {{ background: #eef2ff; }}
    .warning {{ background: #fff7ed; border-left: 4px solid #ea580c; padding: 12px; margin: 12px 0; }}
    pre {{ background: #f3f4f6; padding: 12px; overflow-x: auto; font-size: 0.85rem; }}
    figure {{ text-align: center; margin: 16px 0; }}
    img {{ max-width: 100%; border: 1px solid #dbe3ef; border-radius: 8px; }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Causal Inference Analysis Report</h1>
      <p>Step 6 — Propensity Score &amp; Treatment Effect Estimation</p>
      <p>Metformin users vs Other diabetes medication users | N = {n:,}</p>
    </header>

    <section>
      <h2>1. Study Design</h2>
      <p>Observational comparative effectiveness study using propensity score methods to
      estimate the causal effect of metformin vs other diabetes medications on the composite
      outcome of diabetes-related complications or hospitalization.</p>
    </section>

    <section>
      <h2>2. Confounder Selection Rationale</h2>
      <p>Baseline covariates measured at or before index_date (treatment initiation):</p>
      <ul>
        <li>Demographics: age, gender (female indicator)</li>
        <li>Clinical measurements: baseline HbA1c (%), BMI (kg/m²) from pre-index observations</li>
        <li>Comorbidities: hypertension, cardiovascular disease, obesity, hyperlipidemia, chronic kidney disease</li>
      </ul>
      <p>Continuous labs use the most recent pre-index value; missing HbA1c/BMI are median-imputed in the PS model.
      These variables are established confounders of diabetes treatment selection and complication risk.</p>
    </section>

    <section>
      <h2>3. Propensity Score Methodology</h2>
      <p>Model: P(Treatment = Metformin | Covariates) via multivariable logistic regression
      (statsmodels GLM, robust SE). Matching: 1:1 nearest neighbor on logit PS with caliper
      {DEFAULT_CALIPER_SD} × SD(logit PS).</p>
      <pre>{html.escape(ps_summary[:3000])}</pre>
    </section>

    <section>
      <h2>4. Matching Results</h2>
      <p>Matched pairs: {n_pairs:,} ({n_pairs * 2:,} patients in matched cohort)</p>
    </section>

    <section>
      <h2>5. Balance Assessment</h2>
      <p>|SMD| &lt; {SMD_THRESHOLD} indicates acceptable balance.
      Post-matching balanced covariates: {pct_bal:.1f}%</p>
      {balance.to_html(index=False)}
    </section>

    <section>
      <h2>6. Treatment Effect Estimation</h2>
      {treatment_effects.to_html(index=False)}
    </section>

    <section>
      <h2>7. Sensitivity Analyses</h2>
      {sensitivity.to_html(index=False) if not sensitivity.empty else "<p>See module output.</p>"}
    </section>

    <section>
      <h2>8. Visualizations</h2>
      {figure_html}
    </section>

    <section>
      <h2>9. Limitations</h2>
      <ul>
        <li>Small sample size limits matching and IPTW precision.</li>
        <li>Residual unmeasured confounding (insulin resistance, medication adherence, lifestyle) may persist despite HbA1c/BMI adjustment.</li>
        <li>Propensity score model assumes correct specification and positivity.</li>
        <li>Synthea synthetic data may not reflect real-world treatment pathways.</li>
        <li>Matching discards unmatched patients, reducing generalizability.</li>
      </ul>
      <div class="warning"><strong>{causal_statement}</strong></div>
    </section>
  </div>
</body>
</html>
"""
    report_path.write_text(doc, encoding="utf-8")
    logger.info("Report written to: %s", report_path)


def run_causal_inference(
    data_dir: Path | None = None,
    report_dir: Path | None = None,
) -> CausalInferenceResult:
    """Execute Step 6 causal inference pipeline."""
    np.random.seed(RANDOM_SEED)
    configure_logging()

    data_dir = (data_dir or DEFAULT_DATA_DIR).resolve()
    report_dir = (report_dir or DEFAULT_REPORT_DIR).resolve()
    figures_dir = report_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    study_population = load_study_population(report_dir)
    outcome_events = load_outcome_data(report_dir)
    load_treatment_exposure(report_dir)  # validate Step 4 outputs exist

    followup_path = report_dir / "patient_followup.csv"
    followup = pd.read_csv(followup_path) if followup_path.is_file() else None

    conditions = load_conditions(data_dir)
    observations = load_observations(data_dir)
    confounders = build_confounders(study_population, conditions, observations)
    analysis_data = attach_outcome(confounders, outcome_events, followup)

    confounders.to_csv(report_dir / "baseline_covariates.csv", index=False)

    ps_scores, ps_summary = fit_propensity_score_model(analysis_data)
    analysis_data = analysis_data.merge(
        ps_scores[["patient_id", "propensity_score", "logit_propensity_score"]],
        on="patient_id",
    )

    balance_before = compute_balance_table(analysis_data, CONFOUNDER_COLUMNS, "Before matching")
    matched = propensity_score_match_1to1(analysis_data, caliper_sd=DEFAULT_CALIPER_SD)
    balance_after = compute_balance_table(matched, CONFOUNDER_COLUMNS, "After matching") if not matched.empty else pd.DataFrame()

    analysis_data_iptw = compute_iptw_weights(analysis_data)
    balance_iptw = compute_balance_table(
        analysis_data_iptw, CONFOUNDER_COLUMNS, "After IPTW"
    )
    balance = pd.concat([balance_before, balance_after, balance_iptw], ignore_index=True)

    effects: list[dict[str, object]] = []
    effects.append(estimate_matched_logistic_effect(matched))
    effects.append(estimate_risk_difference(matched, "matched cohort"))
    effects.append(estimate_risk_difference(analysis_data, "unadjusted"))
    effects.append(estimate_iptw_ate(analysis_data))
    effects.append(estimate_iptw_cox(analysis_data))

    treatment_effects = pd.DataFrame(effects)
    sensitivity = run_sensitivity_analyses(analysis_data, ps_scores)

    # Save outputs
    ps_scores.to_csv(report_dir / "propensity_scores.csv", index=False)
    matched.to_csv(report_dir / "matched_cohort.csv", index=False)
    balance.to_csv(report_dir / "balance_diagnostics.csv", index=False)
    treatment_effects.to_csv(report_dir / "treatment_effect_results.csv", index=False)
    sensitivity.to_csv(report_dir / "causal_sensitivity_analysis.csv", index=False)

    figure_paths = create_figures(
        analysis_data, matched, balance, treatment_effects, figures_dir
    )
    report_path = report_dir / "causal_analysis_report.html"
    write_html_report(
        analysis_data, matched, balance, treatment_effects,
        sensitivity, ps_summary, figure_paths, report_path,
    )

    print("=" * 72)
    print("CAUSAL INFERENCE ANALYSIS — STEP 6")
    print("=" * 72)
    print(f"Analytic cohort N = {len(analysis_data)}")
    print(f"Matched pairs = {matched['pair_id'].nunique() if not matched.empty else 0}")
    print("\nTreatment effect results:")
    cols = ["method", "effect_measure", "estimate", "p_value"]
    print(treatment_effects[cols].to_string(index=False))
    print(f"\nReport: {report_path}")
    print("=" * 72)

    return CausalInferenceResult(
        analysis_data=analysis_data,
        propensity_scores=ps_scores,
        matched_cohort=matched,
        balance=balance,
        treatment_effects=treatment_effects,
        sensitivity=sensitivity,
        figure_paths=figure_paths,
        report_path=report_path,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Step 6 causal inference analysis.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_causal_inference(args.data_dir, args.report_dir)


if __name__ == "__main__":
    main()
