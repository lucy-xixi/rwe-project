"""Step 7: Advanced causal inference for pharmaceutical RWE comparative effectiveness.

Extends Step 6 with regression adjustment, IPTW (ATE/ATT), doubly robust estimation,
bootstrap inference, DoWhy/econml integration, sensitivity analyses, and heterogeneous
treatment effects — following observational causal inference methodology.
"""

from __future__ import annotations

import argparse
import html
import logging
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import seaborn as sns
import statsmodels.api as sm
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor

from baseline_observations import impute_confounder_medians
from causal_inference import (
    CONFOUNDER_COLUMNS,
    RANDOM_SEED,
    SMD_THRESHOLD,
    TREATMENT_A,
    TREATMENT_B,
    attach_outcome,
    build_confounders,
    compute_balance_table,
    compute_iptw_weights,
    fit_propensity_score_model,
    load_outcome_data,
    load_study_population,
    propensity_score_match_1to1,
)
from cohort_definition import (
    DEFAULT_DATA_DIR,
    DEFAULT_REPORT_DIR,
    load_conditions,
    load_observations,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
N_BOOTSTRAP = 500
CAUSAL_CONCLUSION = (
    "Results estimate the causal effect under assumptions of no unmeasured confounding, "
    "correct model specification, and adequate overlap of treatment groups."
)

CAUSAL_ASSUMPTIONS = {
    "exchangeability": (
        "Conditional exchangeability: treatment assignment is independent of potential "
        "outcomes given measured baseline covariates (no unmeasured confounding given X)."
    ),
    "positivity": (
        "Positivity (overlap): each patient has non-zero probability of receiving either "
        "metformin or other diabetes medications within strata of measured confounders."
    ),
    "consistency": (
        "Consistency: observed outcome equals the potential outcome under the treatment "
        "actually received; no interference between patients."
    ),
}

COVARIATE_LABELS = {
    "age": "Age",
    "female": "Gender (female)",
    "baseline_hba1c": "HbA1c (%)",
    "baseline_bmi": "BMI (kg/m2)",
    "hypertension": "Hypertension",
    "cardiovascular_disease": "Cardiovascular disease",
    "obesity": "Obesity",
    "hyperlipidemia": "Hyperlipidemia",
    "chronic_kidney_disease": "Kidney disease",
}


@dataclass
class AdvancedCausalResult:
    analysis_data: pd.DataFrame
    matched_cohort: pd.DataFrame
    effect_estimates: pd.DataFrame
    subgroup_effects: pd.DataFrame
    sensitivity: pd.DataFrame
    balance: pd.DataFrame
    bootstrap: pd.DataFrame
    figure_paths: list[Path] = field(default_factory=list)
    report_path: Path | None = None


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_matched_cohort(report_dir: Path) -> pd.DataFrame:
    path = report_dir / "matched_cohort.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}. Run Step 6 propensity score analysis first.")
    return pd.read_csv(path)


def load_baseline_covariates(report_dir: Path, data_dir: Path) -> pd.DataFrame:
    """Load patient-level baseline covariates.

    Accepts ``baseline_covariates.csv`` when present; otherwise derives covariates
    from ``study_population.csv`` and pre-index conditions (same logic as Step 6).
    """
    for name in ("baseline_covariates.csv", "patient_baseline_covariates.csv"):
        path = report_dir / name
        if path.is_file():
            df = pd.read_csv(path)
            for col in ("baseline_hba1c", "baseline_bmi"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            logger.info("Loaded baseline covariates from %s", path)
            return df

    study = load_study_population(report_dir)
    conditions = load_conditions(data_dir)
    observations = load_observations(data_dir)
    df = build_confounders(study, conditions, observations)
    logger.info(
        "Built patient-level baseline covariates from study_population + conditions "
        "(baseline_covariates.csv not found)"
    )
    return df


def prepare_analysis_data(
    report_dir: Path,
    data_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Merge study population, baseline covariates, outcomes, and propensity scores."""
    baseline = load_baseline_covariates(report_dir, data_dir)
    outcomes = load_outcome_data(report_dir)
    followup_path = report_dir / "patient_followup.csv"
    followup = pd.read_csv(followup_path) if followup_path.is_file() else None

    analysis = attach_outcome(baseline, outcomes, followup)
    analysis = impute_confounder_medians(analysis, CONFOUNDER_COLUMNS)
    analysis["comorbidity_burden"] = analysis[
        ["hypertension", "cardiovascular_disease", "obesity", "hyperlipidemia", "chronic_kidney_disease"]
    ].sum(axis=1)
    analysis["age_group"] = np.where(analysis["age"] >= 65, "Age >= 65", "Age < 65")
    analysis["comorbidity_level"] = pd.cut(
        analysis["comorbidity_burden"],
        bins=[-0.1, 1, 3, 10],
        labels=["Low (0-1)", "Moderate (2-3)", "High (4+)"],
    ).astype(str)

    ps_scores, _ = fit_propensity_score_model(analysis)
    analysis = analysis.merge(
        ps_scores[["patient_id", "propensity_score", "logit_propensity_score"]],
        on="patient_id",
    )
    matched = load_matched_cohort(report_dir)
    return analysis, matched


def create_causal_dag(figures_dir: Path) -> Path:
    """Draw causal DAG with treatment, outcome, and confounders."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")

    nodes = {
        "Treatment": (5.0, 5.0, "#2563eb"),
        "Outcome": (8.5, 5.0, "#dc2626"),
        "Age": (1.5, 8.0, "#64748b"),
        "Gender": (1.5, 6.5, "#64748b"),
        "Disease severity": (1.5, 3.5, "#64748b"),
        "HbA1c / BMI": (3.2, 3.5, "#64748b"),
        "Comorbidities": (1.5, 1.5, "#64748b"),
    }

    def draw_node(name: str, xy: tuple[float, float, str]) -> None:
        x, y, color = xy
        box = mpatches.FancyBboxPatch(
            (x - 0.9, y - 0.35),
            1.8,
            0.7,
            boxstyle="round,pad=0.05",
            facecolor=color,
            edgecolor="white",
            alpha=0.9,
        )
        ax.add_patch(box)
        ax.text(x, y, name, ha="center", va="center", fontsize=10, color="white", fontweight="bold")

    for name, pos in nodes.items():
        draw_node(name, pos)

    edges = [
        ("Age", "Treatment"), ("Age", "Outcome"),
        ("Gender", "Treatment"), ("Gender", "Outcome"),
        ("Disease severity", "Treatment"), ("Disease severity", "Outcome"),
        ("HbA1c / BMI", "Treatment"), ("HbA1c / BMI", "Outcome"),
        ("Comorbidities", "Treatment"), ("Comorbidities", "Outcome"),
        ("Treatment", "Outcome"),
    ]
    positions = {k: (v[0], v[1]) for k, v in nodes.items()}

    for src, dst in edges:
        x1, y1 = positions[src]
        x2, y2 = positions[dst]
        ax.annotate(
            "",
            xy=(x2 - 0.85 if dst != "Outcome" else x2 - 0.95, y2),
            xytext=(x1 + 0.85 if src != "Treatment" else x1 + 0.95, y1),
            arrowprops=dict(arrowstyle="->", color="#334155", lw=1.5),
        )

    ax.set_title(
        "Causal DAG: Diabetes Treatment and Complication/Hospitalization Outcome",
        fontsize=13,
        fontweight="bold",
        pad=16,
    )
    ax.text(
        5, 0.4,
        "Dashed conceptual link: baseline HbA1c and BMI partially capture glycemic control and adiposity; "
        "residual severity (insulin resistance, adherence) may remain unmeasured.",
        ha="center",
        fontsize=9,
        color="#475569",
        style="italic",
    )

    out = figures_dir / "causal_dag.png"
    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved DAG: %s", out)
    return out


def regression_adjustment(data: pd.DataFrame) -> dict[str, object]:
    """Multivariable logistic regression: Outcome ~ Treatment + Covariates."""
    cols = ["treatment_metformin"] + CONFOUNDER_COLUMNS
    X = sm.add_constant(data[cols])
    fit = sm.GLM(data["outcome"], X, family=sm.families.Binomial()).fit(cov_type="HC1")
    coef = float(fit.params["treatment_metformin"])
    ci = fit.conf_int().loc["treatment_metformin"]
    or_other = float(np.exp(-coef))
    return {
        "method": "Multivariable logistic regression",
        "effect_measure": "Odds ratio (Other vs Metformin)",
        "estimate": round(or_other, 3),
        "ci_lower": round(float(np.exp(-ci[1])), 3),
        "ci_upper": round(float(np.exp(-ci[0])), 3),
        "p_value": round(float(fit.pvalues["treatment_metformin"]), 4),
        "n": len(data),
        "n_events": int(data["outcome"].sum()),
    }


def compute_att_weights(data: pd.DataFrame) -> pd.DataFrame:
    """ATT weights: treated weight=1; controls weighted by PS/(1-PS), stabilized."""
    df = data.copy()
    ps = np.clip(df["propensity_score"], 0.01, 0.99)
    p_treat = df["treatment_metformin"].mean()
    att = np.where(
        df["treatment_metformin"] == 1,
        1.0,
        ps / (1 - ps) * (1 - p_treat) / p_treat,
    )
    lo, hi = np.quantile(att, [0.01, 0.99])
    df["att_weight"] = np.clip(att, lo, hi)
    return df


def estimate_iptw_effects(data: pd.DataFrame) -> tuple[dict[str, object], dict[str, object], pd.DataFrame]:
    """IPTW ATE and ATT on risk-difference scale with balance diagnostics."""
    df_ate = compute_iptw_weights(data.copy())
    df_att = compute_att_weights(data.copy())

    ate = estimate_iptw_effects_weighted_rd(df_ate, "iptw_weight", "IPTW ATE (stabilized)")
    att = estimate_iptw_effects_weighted_rd(df_att, "att_weight", "IPTW ATT (stabilized)")

    balance_ate = compute_balance_table(df_ate, CONFOUNDER_COLUMNS, "After IPTW ATE")
    balance_att = compute_balance_table(df_att, CONFOUNDER_COLUMNS, "After IPTW ATT")
    balance = pd.concat([balance_ate, balance_att], ignore_index=True)
    return ate, att, balance


def estimate_iptw_effects_weighted_rd(
    frame: pd.DataFrame,
    weight_col: str,
    label: str,
) -> dict[str, object]:
    t = frame[frame["treatment_metformin"] == 1]
    c = frame[frame["treatment_metformin"] == 0]
    r_t = np.average(t["outcome"], weights=t[weight_col])
    r_c = np.average(c["outcome"], weights=c[weight_col])
    rd = r_t - r_c
    X = sm.add_constant(frame["treatment_metformin"])
    wls = sm.GLM(
        frame["outcome"],
        X,
        family=sm.families.Binomial(),
        freq_weights=frame[weight_col],
    ).fit(cov_type="HC1")
    or_other = float(np.exp(-wls.params["treatment_metformin"]))
    ci = wls.conf_int().loc["treatment_metformin"]
    return {
        "method": label,
        "effect_measure": "Risk difference (Metformin - Other)",
        "estimate": round(float(rd), 4),
        "ci_lower": np.nan,
        "ci_upper": np.nan,
        "p_value": round(float(wls.pvalues["treatment_metformin"]), 4),
        "odds_ratio_other_vs_metformin": round(or_other, 3),
        "or_ci_lower": round(float(np.exp(-ci[1])), 3),
        "or_ci_upper": round(float(np.exp(-ci[0])), 3),
        "risk_metformin": round(float(r_t), 4),
        "risk_other": round(float(r_c), 4),
        "n": len(frame),
    }


def doubly_robust_estimation(data: pd.DataFrame) -> dict[str, object]:
    """Augmented IPTW (AIPW) doubly robust risk difference and OR.

    Combines outcome regression (Outcome ~ Treatment + X) with IPTW weights.
    """
    df = compute_iptw_weights(data.copy())
    cols = ["treatment_metformin"] + CONFOUNDER_COLUMNS
    X = sm.add_constant(df[cols])
    outcome_fit = sm.GLM(
        df["outcome"], X, family=sm.families.Binomial(), freq_weights=df["iptw_weight"]
    ).fit(cov_type="HC1")

    ps = np.clip(df["propensity_score"], 0.01, 0.99)
    t = df["treatment_metformin"].to_numpy()
    y = df["outcome"].to_numpy()

    mu1 = outcome_fit.predict(X)
    X0 = X.copy()
    X0["treatment_metformin"] = 0
    mu0 = outcome_fit.predict(X0)
    X1 = X.copy()
    X1["treatment_metformin"] = 1
    mu1_treat = outcome_fit.predict(X1)

    aipw = (mu1_treat - mu0) + t * (y - mu1_treat) / ps - (1 - t) * (y - mu0) / (1 - ps)
    ate = float(np.mean(aipw))

    dr_fit = sm.GLM(
        df["outcome"],
        sm.add_constant(df[["treatment_metformin"] + CONFOUNDER_COLUMNS]),
        family=sm.families.Binomial(),
        freq_weights=df["iptw_weight"],
    ).fit(cov_type="HC1")
    coef = float(dr_fit.params["treatment_metformin"])
    ci = dr_fit.conf_int().loc["treatment_metformin"]

    return {
        "method": "Doubly robust AIPW + weighted outcome regression",
        "effect_measure": "Average treatment effect (risk difference)",
        "estimate": round(ate, 4),
        "ci_lower": np.nan,
        "ci_upper": np.nan,
        "p_value": round(float(dr_fit.pvalues["treatment_metformin"]), 4),
        "odds_ratio_other_vs_metformin": round(float(np.exp(-coef)), 3),
        "or_ci_lower": round(float(np.exp(-ci[1])), 3),
        "or_ci_upper": round(float(np.exp(-ci[0])), 3),
        "n": len(df),
        "n_events": int(df["outcome"].sum()),
    }


def _bootstrap_iptw_ate(sample: pd.DataFrame) -> float | None:
    """IPTW ATE on one bootstrap sample; returns None if estimation fails."""
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler

        y = sample["treatment_metformin"]
        X = sample[CONFOUNDER_COLUMNS].astype(float).fillna(sample[CONFOUNDER_COLUMNS].median())
        if y.nunique() < 2 or len(sample) < 10:
            return None

        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("logit", LogisticRegression(max_iter=1000, random_state=RANDOM_SEED)),
        ])
        pipe.fit(X, y)
        ps = np.clip(pipe.predict_proba(X)[:, 1], 0.05, 0.95)
        p_t = y.mean()
        weights = np.where(y == 1, p_t / ps, (1 - p_t) / (1 - ps))
        lo, hi = np.quantile(weights, [0.05, 0.95])
        weights = np.clip(weights, lo, hi)

        t_mask = y == 1
        r_t = np.average(sample.loc[t_mask, "outcome"], weights=weights[t_mask.to_numpy()])
        r_c = np.average(sample.loc[~t_mask, "outcome"], weights=weights[~t_mask.to_numpy()])
        return float(r_t - r_c)
    except Exception:
        return None


def bootstrap_treatment_effect(
    data: pd.DataFrame,
    n_boot: int = N_BOOTSTRAP,
    seed: int = RANDOM_SEED,
) -> pd.DataFrame:
    """Bootstrap 95% CI for IPTW ATE risk difference."""
    rng = np.random.default_rng(seed)
    estimates: list[float] = []

    for _ in range(n_boot):
        idx = rng.integers(0, len(data), size=len(data))
        sample = data.iloc[idx].reset_index(drop=True)
        rd = _bootstrap_iptw_ate(sample)
        if rd is not None and np.isfinite(rd):
            estimates.append(rd)

    if not estimates:
        return pd.DataFrame([{"metric": "IPTW ATE", "estimate": np.nan, "ci_lower": np.nan, "ci_upper": np.nan}])

    arr = np.array(estimates)
    return pd.DataFrame(
        [{
            "metric": "IPTW ATE risk difference (bootstrap)",
            "n_bootstrap": len(arr),
            "estimate": round(float(np.mean(arr)), 4),
            "ci_lower": round(float(np.percentile(arr, 2.5)), 4),
            "ci_upper": round(float(np.percentile(arr, 97.5)), 4),
        }]
    )


def dowhy_backdoor_estimate(data: pd.DataFrame) -> dict[str, object]:
    """DoWhy backdoor propensity-score weighting estimate."""
    try:
        import dowhy
        from dowhy import CausalModel
    except ImportError:
        return {"method": "DoWhy backdoor IPTW", "estimate": np.nan, "note": "dowhy not installed"}

    graph = """
    digraph {
        age -> treatment_metformin; age -> outcome;
        female -> treatment_metformin; female -> outcome;
        hypertension -> treatment_metformin; hypertension -> outcome;
        cardiovascular_disease -> treatment_metformin; cardiovascular_disease -> outcome;
        obesity -> treatment_metformin; obesity -> outcome;
        hyperlipidemia -> treatment_metformin; hyperlipidemia -> outcome;
        chronic_kidney_disease -> treatment_metformin; chronic_kidney_disease -> outcome;
        treatment_metformin -> outcome;
    }
    """
    model = CausalModel(
        data=data,
        treatment="treatment_metformin",
        outcome="outcome",
        common_causes=CONFOUNDER_COLUMNS,
        graph=graph,
    )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            estimand = model.identify_effect(proceed_when_unidentifiable=True)
            estimate = model.estimate_effect(
                estimand,
                method_name="backdoor.propensity_score_weighting",
                target_units="ate",
            )
        val = float(estimate.value)
        return {
            "method": "DoWhy backdoor propensity score weighting (ATE)",
            "effect_measure": "Average treatment effect (DoWhy value scale)",
            "estimate": round(val, 4),
            "ci_lower": np.nan,
            "ci_upper": np.nan,
            "p_value": np.nan,
            "n": len(data),
        }
    except Exception as exc:
        logger.warning("DoWhy estimation failed: %s", exc)
        return {
            "method": "DoWhy backdoor propensity score weighting (ATE)",
            "effect_measure": "Average treatment effect (DoWhy value scale)",
            "estimate": np.nan,
            "note": str(exc),
            "n": len(data),
        }


def econml_dml_estimate(data: pd.DataFrame) -> dict[str, object]:
    """EconML LinearDML average treatment effect with confidence interval."""
    try:
        from econml.dml import LinearDML
    except ImportError:
        return {"method": "EconML LinearDML", "estimate": np.nan, "note": "econml not installed"}

    Y = data["outcome"].astype(float).to_numpy()
    T = data["treatment_metformin"].to_numpy()
    X = data[CONFOUNDER_COLUMNS].astype(float).to_numpy()

    try:
        est = LinearDML(
            model_y=GradientBoostingRegressor(n_estimators=50, max_depth=2, random_state=RANDOM_SEED),
            model_t=GradientBoostingClassifier(n_estimators=50, max_depth=2, random_state=RANDOM_SEED),
            discrete_treatment=True,
            cv=3,
            random_state=RANDOM_SEED,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            est.fit(Y, T, X=X)

        ate = float(est.ate(X=X))
        ci = est.ate_interval(X=X, alpha=0.05)
        return {
            "method": "EconML LinearDML (ATE)",
            "effect_measure": "Average treatment effect (probability scale)",
            "estimate": round(ate, 4),
            "ci_lower": round(float(ci[0]), 4),
            "ci_upper": round(float(ci[1]), 4),
            "p_value": np.nan,
            "n": len(data),
        }
    except Exception as exc:
        logger.warning("EconML LinearDML failed: %s", exc)
        return {
            "method": "EconML LinearDML (ATE)",
            "effect_measure": "Average treatment effect (probability scale)",
            "estimate": np.nan,
            "note": str(exc),
            "n": len(data),
        }


def run_sensitivity_analyses(data: pd.DataFrame) -> pd.DataFrame:
    """Robustness: drop-one covariate, PS specifications, matching calipers."""
    rows: list[dict[str, object]] = []
    base_or = regression_adjustment(data)["estimate"]

    for drop in CONFOUNDER_COLUMNS:
        covs = [c for c in CONFOUNDER_COLUMNS if c != drop]
        ps, _ = fit_propensity_score_model(data, covariates=covs)
        merged = data.drop(columns=["propensity_score", "logit_propensity_score"], errors="ignore")
        merged = merged.merge(ps[["patient_id", "propensity_score", "logit_propensity_score"]], on="patient_id")
        cols = ["treatment_metformin"] + covs
        fit = sm.GLM(
            merged["outcome"],
            sm.add_constant(merged[cols]),
            family=sm.families.Binomial(),
        ).fit(cov_type="HC1")
        rows.append({
            "analysis_type": "Drop-one covariate",
            "specification": f"Exclude {COVARIATE_LABELS.get(drop, drop)}",
            "effect_estimate": round(float(np.exp(-fit.params["treatment_metformin"])), 3),
            "p_value": round(float(fit.pvalues["treatment_metformin"]), 4),
            "reference_or": base_or,
        })

    for spec, covs in [
        ("Demographics only PS", ["age", "female"]),
        (
            "Comorbidities + labs (no demographics)",
            [c for c in CONFOUNDER_COLUMNS if c not in ("age", "female")],
        ),
        (
            "Without baseline labs",
            [c for c in CONFOUNDER_COLUMNS if c not in ("baseline_hba1c", "baseline_bmi")],
        ),
        ("Full covariate PS", CONFOUNDER_COLUMNS),
    ]:
        ps, _ = fit_propensity_score_model(data, covariates=covs)
        merged = data.drop(columns=["propensity_score", "logit_propensity_score"], errors="ignore")
        merged = merged.merge(ps[["patient_id", "propensity_score", "logit_propensity_score"]], on="patient_id")
        weighted = compute_iptw_weights(merged)
        t = weighted[weighted["treatment_metformin"] == 1]
        c = weighted[weighted["treatment_metformin"] == 0]
        rd = np.average(t["outcome"], weights=t["iptw_weight"]) - np.average(
            c["outcome"], weights=c["iptw_weight"]
        )
        rows.append({
            "analysis_type": "Propensity model specification",
            "specification": spec,
            "effect_estimate": round(float(rd), 4),
            "p_value": np.nan,
            "reference_or": base_or,
        })

    for caliper in (0.1, 0.2, 0.3):
        matched = propensity_score_match_1to1(data, caliper_sd=caliper)
        if matched.empty:
            continue
        t = matched[matched["treatment_metformin"] == 1]
        c = matched[matched["treatment_metformin"] == 0]
        rd = t["outcome"].mean() - c["outcome"].mean()
        rows.append({
            "analysis_type": "Matching caliper",
            "specification": f"1:1 NN caliper {caliper} SD",
            "effect_estimate": round(float(rd), 4),
            "p_value": np.nan,
            "n_pairs": matched["pair_id"].nunique(),
            "reference_or": base_or,
        })

    return pd.DataFrame(rows)


def estimate_subgroup_effects(data: pd.DataFrame) -> pd.DataFrame:
    """Heterogeneous treatment effects by age, gender, and comorbidity burden."""
    rows: list[dict[str, object]] = []

    subgroups = [
        ("Age group", "age_group"),
        ("Gender", "gender"),
        ("Comorbidity burden", "comorbidity_level"),
    ]

    for label, col in subgroups:
        for level, sub in data.groupby(col, observed=True):
            if len(sub) < 8 or sub["outcome"].nunique() < 2:
                continue
            if sub["treatment_metformin"].nunique() < 2:
                continue
            try:
                effect = regression_adjustment(sub)
                t = sub[sub["treatment_metformin"] == 1]
                c = sub[sub["treatment_metformin"] == 0]
                rows.append({
                    "subgroup_variable": label,
                    "subgroup_level": str(level),
                    "n": len(sub),
                    "n_metformin": int((sub["treatment_metformin"] == 1).sum()),
                    "n_other": int((sub["treatment_metformin"] == 0).sum()),
                    "odds_ratio_other_vs_metformin": effect["estimate"],
                    "ci_lower": effect["ci_lower"],
                    "ci_upper": effect["ci_upper"],
                    "p_value": effect["p_value"],
                    "risk_metformin": round(float(t["outcome"].mean()), 3),
                    "risk_other": round(float(c["outcome"].mean()), 3),
                })
            except Exception:
                continue

    return pd.DataFrame(rows)


def create_figures(
    data: pd.DataFrame,
    matched: pd.DataFrame,
    effects: pd.DataFrame,
    subgroup: pd.DataFrame,
    balance: pd.DataFrame,
    dag_path: Path,
    figures_dir: Path,
) -> list[Path]:
    """Generate forest plot, subgroup plot, and balance plot."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")
    paths: list[Path] = [dag_path]

    # Forest plot — primary effect estimates
    plot_effects = effects[
        effects["effect_measure"].astype(str).str.contains("Odds ratio|risk difference|Average treatment", case=False, na=False)
    ].copy()
    if not plot_effects.empty:
        plot_effects = plot_effects.dropna(subset=["estimate"])
        fig, ax = plt.subplots(figsize=(10, max(4, 0.5 * len(plot_effects) + 1)))
        y_pos = np.arange(len(plot_effects))
        ax.errorbar(
            plot_effects["estimate"],
            y_pos,
            xerr=[
                np.abs(plot_effects["estimate"] - plot_effects["ci_lower"].fillna(plot_effects["estimate"])),
                np.abs(plot_effects["ci_upper"].fillna(plot_effects["estimate"]) - plot_effects["estimate"]),
            ],
            fmt="o",
            color="#2563eb",
            capsize=4,
        )
        ax.set_yticks(y_pos)
        ax.set_yticklabels(plot_effects["method"].str[:45])
        ax.axvline(0, color="#94a3b8", linestyle="--", linewidth=1)
        ax.axvline(1, color="#94a3b8", linestyle=":", linewidth=1, label="Null OR=1")
        ax.set_xlabel("Effect estimate")
        ax.set_title("Treatment Effect Estimates — Advanced Causal Inference")
        fig.tight_layout()
        p = figures_dir / "advanced_causal_forest_plot.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        paths.append(p)

    # Subgroup plot
    if not subgroup.empty and "odds_ratio_other_vs_metformin" in subgroup.columns:
        sub = subgroup.dropna(subset=["odds_ratio_other_vs_metformin"]).copy()
        sub["label"] = sub["subgroup_variable"] + ": " + sub["subgroup_level"]
        fig, ax = plt.subplots(figsize=(10, max(4, 0.45 * len(sub) + 1)))
        y = np.arange(len(sub))
        ax.errorbar(
            sub["odds_ratio_other_vs_metformin"],
            y,
            xerr=[
                sub["odds_ratio_other_vs_metformin"] - sub["ci_lower"],
                sub["ci_upper"] - sub["odds_ratio_other_vs_metformin"],
            ],
            fmt="s",
            color="#7c3aed",
            capsize=4,
        )
        ax.set_yticks(y)
        ax.set_yticklabels(sub["label"])
        ax.axvline(1, color="#94a3b8", linestyle="--")
        ax.set_xlabel("Odds ratio (Other vs Metformin)")
        ax.set_title("Heterogeneous Treatment Effects by Subgroup")
        fig.tight_layout()
        p = figures_dir / "subgroup_treatment_effects.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        paths.append(p)

    # Balance plot (Love plot)
    if not balance.empty:
        wide = balance.pivot(index="covariate", columns="analysis_stage", values="smd")
        fig, ax = plt.subplots(figsize=(9, max(4, 0.4 * len(wide) + 2)))
        stages = list(wide.columns)
        y = np.arange(len(wide))
        for i, stage in enumerate(stages):
            offset = (i - len(stages) / 2) * 0.15
            ax.scatter(wide[stage], y + offset, label=stage, s=60)
        ax.axvline(-SMD_THRESHOLD, color="#94a3b8", linestyle="--", linewidth=1)
        ax.axvline(SMD_THRESHOLD, color="#94a3b8", linestyle="--", linewidth=1)
        ax.axvline(0, color="#cbd5e1", linewidth=1)
        ax.set_yticks(y)
        ax.set_yticklabels([COVARIATE_LABELS.get(c, c) for c in wide.index])
        ax.set_xlabel("Standardized mean difference")
        ax.set_title("Covariate Balance After IPTW Weighting")
        ax.legend(loc="lower right", fontsize=8)
        fig.tight_layout()
        p = figures_dir / "advanced_causal_balance_plot.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        paths.append(p)

    return paths


def _df_to_html(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df.empty:
        return "<p><em>No results available.</em></p>"
    return df.head(max_rows).to_html(index=False, border=0, classes="table")


def write_html_report(
    data: pd.DataFrame,
    matched: pd.DataFrame,
    effects: pd.DataFrame,
    subgroup: pd.DataFrame,
    sensitivity: pd.DataFrame,
    balance: pd.DataFrame,
    bootstrap: pd.DataFrame,
    figure_paths: list[Path],
    report_path: Path,
) -> None:
    """Generate final advanced causal inference HTML report."""
    figure_html = ""
    for fp in figure_paths:
        if fp.is_file():
            rel = fp.name
            figure_html += f'<figure><img src="figures/{rel}" alt="{html.escape(fp.stem)}"><figcaption>{html.escape(fp.stem.replace("_", " "))}</figcaption></figure>\n'

    assumptions_html = "".join(
        f"<li><strong>{name.title()}:</strong> {text}</li>"
        for name, text in CAUSAL_ASSUMPTIONS.items()
    )
    confounder_list = ", ".join(COVARIATE_LABELS[c] for c in CONFOUNDER_COLUMNS)

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Advanced Causal Inference Report — RWE Diabetes Study</title>
  <style>
    body {{ font-family: "Segoe UI", Tahoma, sans-serif; margin: 0; background: #f4f7fb; color: #1f2937; }}
    .container {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}
    header {{ background: linear-gradient(135deg, #312e81, #4f46e5); color: #fff; padding: 28px; border-radius: 12px; margin-bottom: 24px; }}
    section {{ background: #fff; border: 1px solid #dbe3ef; border-radius: 10px; padding: 20px; margin-bottom: 20px; }}
    h2 {{ color: #4338ca; margin-top: 0; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; }}
    th, td {{ border-bottom: 1px solid #dbe3ef; padding: 8px 10px; text-align: left; }}
    th {{ background: #eef2ff; }}
    .warning {{ background: #fff7ed; border-left: 4px solid #ea580c; padding: 12px; margin: 12px 0; }}
    .conclusion {{ background: #ecfdf5; border-left: 4px solid #059669; padding: 12px; margin: 12px 0; }}
    figure {{ text-align: center; margin: 16px 0; }}
    img {{ max-width: 100%; border: 1px solid #dbe3ef; border-radius: 8px; }}
    pre {{ background: #f3f4f6; padding: 12px; overflow-x: auto; font-size: 0.85rem; white-space: pre-wrap; }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Advanced Causal Inference Report</h1>
      <p>Step 7 — Regression, IPTW, Doubly Robust, Bootstrap, and HTE Analysis</p>
      <p>{TREATMENT_A} vs {TREATMENT_B} | Full cohort N = {len(data)} | Matched N = {len(matched)}</p>
    </header>

    <section>
      <h2>1. Study Objective</h2>
      <p>Estimate the causal effect of diabetes pharmacotherapy (metformin vs other diabetes medications)
      on the composite outcome of diabetes-related complications or hospitalization using advanced
      observational causal inference methods appropriate for pharmaceutical real-world evidence.</p>
    </section>

    <section>
      <h2>2. Causal Question</h2>
      <p><strong>What is the causal effect of diabetes treatment on clinical outcomes?</strong></p>
      <pre>Treatment (Metformin vs Other) → Outcome (complication / hospitalization)
Adjusted for: {confounder_list}</pre>
    </section>

    <section>
      <h2>3. DAG and Causal Assumptions</h2>
      <p>The causal directed acyclic graph posits that age, gender, disease severity (partially unmeasured),
      and comorbidities confound the treatment–outcome relationship. Comorbidity burden proxies disease severity.</p>
      <ul>{assumptions_html}</ul>
    </section>

    <section>
      <h2>4. Confounder Adjustment Strategy</h2>
      <p>All baseline covariates were measured at or before treatment initiation (index date).
      Adjustment strategies include multivariable regression, propensity score IPTW (ATE and ATT),
      doubly robust AIPW, DoWhy backdoor identification, and EconML double machine learning.</p>
    </section>

    <section>
      <h2>5. Statistical Methods</h2>
      <ul>
        <li>Multivariable logistic regression: Outcome ~ Treatment + Covariates</li>
        <li>Stabilized IPTW for ATE; ATT weights for treated population</li>
        <li>Doubly robust augmented inverse-probability weighting (AIPW)</li>
        <li>Bootstrap resampling ({N_BOOTSTRAP} iterations) for IPTW ATE uncertainty</li>
        <li>DoWhy backdoor propensity score weighting</li>
        <li>EconML LinearDML with gradient boosting nuisance models</li>
        <li>Sensitivity: drop-one covariate, alternative PS models, matching calipers</li>
        <li>Subgroup analyses: age group, gender, comorbidity burden</li>
      </ul>
    </section>

    <section>
      <h2>6. Treatment Effect Estimates</h2>
      {_df_to_html(effects)}
      <h3>Bootstrap 95% CI</h3>
      {_df_to_html(bootstrap)}
      <h3>Subgroup (heterogeneous) effects</h3>
      {_df_to_html(subgroup)}
    </section>

    <section>
      <h2>7. Sensitivity Analysis</h2>
      <p>Results were re-estimated after sequentially omitting covariates, changing propensity score
      specifications, and varying 1:1 matching calipers. Estimates that remain directionally consistent
      support robustness; large shifts indicate sensitivity to modeling assumptions.</p>
      {_df_to_html(sensitivity)}
    </section>

    <section>
      <h2>8. Limitations</h2>
      <ul>
        <li>Small sample (N={len(data)}) limits precision and subgroup analyses.</li>
        <li>Disease severity is partially captured via baseline HbA1c, BMI, and comorbidity burden; insulin resistance and adherence remain unmeasured.</li>
        <li>Residual confounding from unmeasured clinical and behavioral factors may remain despite lab adjustment.</li>
        <li>Synthea synthetic data may not reflect real-world treatment pathways.</li>
        <li>Positivity violations in extreme PS strata can destabilize weighting.</li>
      </ul>
      <div class="conclusion"><strong>{CAUSAL_CONCLUSION}</strong></div>
    </section>

    <section>
      <h2>9. Figures</h2>
      {figure_html}
    </section>
  </div>
</body>
</html>
"""
    report_path.write_text(doc, encoding="utf-8")
    logger.info("Report written to: %s", report_path)


def run_advanced_causal_inference(
    data_dir: Path | None = None,
    report_dir: Path | None = None,
) -> AdvancedCausalResult:
    """Execute Step 7 advanced causal inference pipeline."""
    np.random.seed(RANDOM_SEED)
    configure_logging()

    data_dir = (data_dir or DEFAULT_DATA_DIR).resolve()
    report_dir = (report_dir or DEFAULT_REPORT_DIR).resolve()
    figures_dir = report_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    analysis, matched = prepare_analysis_data(report_dir, data_dir)

    effects: list[dict[str, object]] = []
    effects.append(regression_adjustment(analysis))
    ate, att, balance_iptw = estimate_iptw_effects(analysis)
    effects.append(ate)
    effects.append(att)
    effects.append(doubly_robust_estimation(analysis))
    effects.append(dowhy_backdoor_estimate(analysis))
    effects.append(econml_dml_estimate(analysis))

    effect_df = pd.DataFrame(effects)
    bootstrap_df = bootstrap_treatment_effect(analysis)
    sensitivity_df = run_sensitivity_analyses(analysis)
    subgroup_df = estimate_subgroup_effects(analysis)

    balance_before = compute_balance_table(analysis, CONFOUNDER_COLUMNS, "Before weighting")
    balance = pd.concat([balance_before, balance_iptw], ignore_index=True)

    dag_path = create_causal_dag(figures_dir)
    figure_paths = create_figures(
        analysis, matched, effect_df, subgroup_df, balance, dag_path, figures_dir
    )

    effect_df.to_csv(report_dir / "causal_effect_estimates.csv", index=False)
    subgroup_df.to_csv(report_dir / "subgroup_treatment_effects.csv", index=False)
    sensitivity_df.to_csv(report_dir / "advanced_causal_sensitivity.csv", index=False)
    balance.to_csv(report_dir / "advanced_balance_diagnostics.csv", index=False)
    bootstrap_df.to_csv(report_dir / "bootstrap_treatment_effects.csv", index=False)

    report_path = report_dir / "causal_inference_report.html"
    write_html_report(
        analysis, matched, effect_df, subgroup_df, sensitivity_df,
        balance, bootstrap_df, figure_paths, report_path,
    )

    print("=" * 72)
    print("ADVANCED CAUSAL INFERENCE — STEP 7")
    print("=" * 72)
    print(f"Full cohort N = {len(analysis)} | Matched N = {len(matched)}")
    print("\nPrimary effect estimates:")
    cols = ["method", "effect_measure", "estimate", "ci_lower", "ci_upper", "p_value"]
    print(effect_df[cols].to_string(index=False))
    if not bootstrap_df.empty:
        print(f"\nBootstrap 95% CI: {bootstrap_df.iloc[0]['ci_lower']} to {bootstrap_df.iloc[0]['ci_upper']}")
    print(f"\nReport: {report_path}")
    print("=" * 72)

    return AdvancedCausalResult(
        analysis_data=analysis,
        matched_cohort=matched,
        effect_estimates=effect_df,
        subgroup_effects=subgroup_df,
        sensitivity=sensitivity_df,
        balance=balance,
        bootstrap=bootstrap_df,
        figure_paths=figure_paths,
        report_path=report_path,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Step 7 advanced causal inference analysis.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_advanced_causal_inference(args.data_dir, args.report_dir)


if __name__ == "__main__":
    main()
