"""Real-World Data Quality Assessment for Synthea CSV exports.

Evaluates pharmaceutical RWE data-quality dimensions (completeness, uniqueness,
validity, referential integrity) and writes CSV and HTML reports.
"""

from __future__ import annotations

import argparse
import html
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "synthea_csv"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "reports"

# Core clinical tables for targeted validity and referential-integrity checks.
CORE_TABLES = ("patients", "encounters", "conditions", "medications")

DATE_COLUMNS = frozenset(
    {
        "START",
        "STOP",
        "DATE",
        "BIRTHDATE",
        "DEATHDATE",
        "START_DATE",
        "END_DATE",
    }
)

# Synthea / OMOP-aligned categorical domains for validity checks.
CATEGORICAL_DOMAINS: dict[tuple[str, str], set[str]] = {
    ("patients", "GENDER"): {"M", "F"},
    ("patients", "RACE"): {"asian", "black", "hawaiian", "native", "other", "white"},
    ("patients", "ETHNICITY"): {"hispanic", "nonhispanic"},
    ("patients", "MARITAL"): {"D", "M", "S", "W"},
    (
        "encounters",
        "ENCOUNTERCLASS",
    ): {
        "ambulatory",
        "emergency",
        "home",
        "hospice",
        "inpatient",
        "outpatient",
        "snf",
        "urgentcare",
        "virtual",
        "wellness",
    },
    ("allergies", "CATEGORY"): {"environment", "food", "medication"},
    ("allergies", "TYPE"): {"allergy", "intolerance"},
    ("observations", "CATEGORY"): {
        "exam",
        "laboratory",
        "procedure",
        "social-history",
        "survey",
        "therapy",
        "vital-signs",
        "imaging",
    },
}

REFERENTIAL_CHECKS: list[dict[str, str]] = [
    {
        "name": "encounters_to_patients",
        "child_table": "encounters",
        "child_column": "PATIENT",
        "parent_table": "patients",
        "parent_column": "Id",
    },
    {
        "name": "conditions_to_patients",
        "child_table": "conditions",
        "child_column": "PATIENT",
        "parent_table": "patients",
        "parent_column": "Id",
    },
    {
        "name": "medications_to_patients",
        "child_table": "medications",
        "child_column": "PATIENT",
        "parent_table": "patients",
        "parent_column": "Id",
    },
]

# Pharmaceutical RWE typical acceptance thresholds (percentage of failing records).
THRESHOLDS = {
    "completeness_critical": 0.0,
    "completeness_required": 5.0,
    "completeness_expected": 20.0,
    "uniqueness": 0.0,
    "validity": 0.0,
    "referential_integrity": 0.0,
}

CRITICAL_FIELDS: set[tuple[str, str]] = {
    ("patients", "Id"),
    ("patients", "BIRTHDATE"),
    ("patients", "GENDER"),
    ("encounters", "Id"),
    ("encounters", "PATIENT"),
    ("encounters", "START"),
    ("conditions", "PATIENT"),
    ("conditions", "CODE"),
    ("medications", "PATIENT"),
    ("medications", "CODE"),
}


@dataclass
class QualityFinding:
    dimension: str
    table: str
    field: str
    check_name: str
    total_records: int
    issue_count: int
    issue_rate_pct: float
    threshold_pct: float
    status: str
    severity: str
    details: str = ""


@dataclass
class QualityReport:
    generated_at: str
    data_dir: Path
    findings: list[QualityFinding] = field(default_factory=list)

    def add(self, finding: QualityFinding) -> None:
        self.findings.append(finding)

    def to_dataframe(self) -> pd.DataFrame:
        rows = [
            {
                "dimension": f.dimension,
                "table": f.table,
                "field": f.field,
                "check_name": f.check_name,
                "total_records": f.total_records,
                "issue_count": f.issue_count,
                "issue_rate_pct": f.issue_rate_pct,
                "threshold_pct": f.threshold_pct,
                "status": f.status,
                "severity": f.severity,
                "details": f.details,
            }
            for f in self.findings
        ]
        return pd.DataFrame(rows)


def load_csv_tables(data_dir: Path) -> dict[str, pd.DataFrame]:
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    tables: dict[str, pd.DataFrame] = {}
    for csv_path in sorted(data_dir.glob("*.csv")):
        tables[csv_path.stem] = pd.read_csv(csv_path, low_memory=False)
    if not tables:
        raise FileNotFoundError(f"No CSV files found in: {data_dir}")
    return tables


def _status_for_rate(
    issue_rate_pct: float,
    threshold_pct: float,
    *,
    warn_buffer: float = 0.0,
) -> str:
    if issue_rate_pct <= threshold_pct:
        return "PASS"
    if issue_rate_pct <= threshold_pct + warn_buffer:
        return "WARN"
    return "FAIL"


def _completeness_severity(table: str, field: str) -> tuple[str, float]:
    if (table, field) in CRITICAL_FIELDS:
        return "Critical", THRESHOLDS["completeness_critical"]
    return "Informational", THRESHOLDS["completeness_expected"]


def check_completeness(tables: dict[str, pd.DataFrame], report: QualityReport) -> None:
    for table_name, df in sorted(tables.items()):
        row_count = len(df)
        for column in df.columns:
            null_count = int(df[column].isna().sum())
            null_pct = (null_count / row_count * 100) if row_count else 0.0
            severity, threshold = _completeness_severity(table_name, column)
            if (table_name, column) in CRITICAL_FIELDS:
                status = _status_for_rate(null_pct, threshold)
            else:
                # Document missingness for all fields; enforce thresholds on critical fields only.
                status = "PASS"

            report.add(
                QualityFinding(
                    dimension="Completeness",
                    table=table_name,
                    field=column,
                    check_name="missing_values",
                    total_records=row_count,
                    issue_count=null_count,
                    issue_rate_pct=round(null_pct, 4),
                    threshold_pct=threshold,
                    status=status,
                    severity=severity,
                    details=f"{null_count:,} missing of {row_count:,} records ({null_pct:.2f}%)",
                )
            )


def check_uniqueness(tables: dict[str, pd.DataFrame], report: QualityReport) -> None:
    patients = tables["patients"]
    row_count = len(patients)
    duplicate_count = int(patients["Id"].duplicated(keep=False).sum())
    duplicate_ids = int(patients["Id"].duplicated().sum())
    dup_rate = (duplicate_count / row_count * 100) if row_count else 0.0

    report.add(
        QualityFinding(
            dimension="Uniqueness",
            table="patients",
            field="Id",
            check_name="duplicate_patient_ids",
            total_records=row_count,
            issue_count=duplicate_count,
            issue_rate_pct=round(dup_rate, 4),
            threshold_pct=THRESHOLDS["uniqueness"],
            status=_status_for_rate(dup_rate, THRESHOLDS["uniqueness"]),
            severity="Critical",
            details=(
                f"{duplicate_ids:,} duplicated key value(s); "
                f"{duplicate_count:,} rows involved in duplication"
            ),
        )
    )


def _is_date_column(column: str) -> bool:
    return column.upper() in DATE_COLUMNS


def _invalid_date_mask(series: pd.Series) -> pd.Series:
    non_null = series.dropna().astype(str).str.strip()
    non_null = non_null[non_null != ""]
    if non_null.empty:
        return pd.Series(False, index=series.index)

    parsed = pd.to_datetime(non_null, errors="coerce", utc=True, format="mixed")
    invalid_idx = parsed[parsed.isna()].index
    mask = pd.Series(False, index=series.index)
    mask.loc[invalid_idx] = True
    return mask


def check_validity(tables: dict[str, pd.DataFrame], report: QualityReport) -> None:
    for table_name in CORE_TABLES:
        df = tables[table_name]
        row_count = len(df)

        for column in df.columns:
            if not _is_date_column(column):
                continue

            invalid_mask = _invalid_date_mask(df[column])
            invalid_count = int(invalid_mask.sum())
            invalid_rate = (invalid_count / row_count * 100) if row_count else 0.0
            sample = (
                df.loc[invalid_mask, column].astype(str).head(3).tolist() if invalid_count else []
            )

            report.add(
                QualityFinding(
                    dimension="Validity",
                    table=table_name,
                    field=column,
                    check_name="invalid_dates",
                    total_records=row_count,
                    issue_count=invalid_count,
                    issue_rate_pct=round(invalid_rate, 4),
                    threshold_pct=THRESHOLDS["validity"],
                    status=_status_for_rate(invalid_rate, THRESHOLDS["validity"]),
                    severity="Critical" if (table_name, column) in CRITICAL_FIELDS else "High",
                    details=(
                        f"Non-null values that fail ISO date/datetime parsing"
                        + (f"; examples: {', '.join(sample)}" if sample else "")
                    ),
                )
            )

    for (table_name, column), allowed in sorted(CATEGORICAL_DOMAINS.items()):
        if table_name not in tables or column not in tables[table_name].columns:
            continue

        series = tables[table_name][column]
        non_null = series.dropna().astype(str).str.strip()
        invalid_mask = ~non_null.isin(allowed) & (non_null != "")
        invalid_count = int(invalid_mask.sum())
        row_count = len(series)
        invalid_rate = (invalid_count / row_count * 100) if row_count else 0.0
        invalid_values = sorted(non_null[invalid_mask].unique().tolist())[:5]

        report.add(
            QualityFinding(
                dimension="Validity",
                table=table_name,
                field=column,
                check_name="invalid_categorical_values",
                total_records=row_count,
                issue_count=invalid_count,
                issue_rate_pct=round(invalid_rate, 4),
                threshold_pct=THRESHOLDS["validity"],
                status=_status_for_rate(invalid_rate, THRESHOLDS["validity"]),
                severity="Critical" if (table_name, column) in CRITICAL_FIELDS else "High",
                details=(
                    f"Allowed domain: {sorted(allowed)}"
                    + (f"; invalid values found: {invalid_values}" if invalid_values else "")
                ),
            )
        )


def check_referential_integrity(tables: dict[str, pd.DataFrame], report: QualityReport) -> None:
    for spec in REFERENTIAL_CHECKS:
        child = tables[spec["child_table"]]
        parent = tables[spec["parent_table"]]
        parent_values = set(parent[spec["parent_column"]].dropna().unique())

        fk_series = child[spec["child_column"]]
        non_null = fk_series.dropna()
        checked = len(non_null)
        orphans = int((~non_null.isin(parent_values)).sum())
        orphan_rate = (orphans / checked * 100) if checked else 0.0
        null_count = int(fk_series.isna().sum())

        report.add(
            QualityFinding(
                dimension="Referential Integrity",
                table=spec["child_table"],
                field=spec["child_column"],
                check_name=spec["name"],
                total_records=len(child),
                issue_count=orphans,
                issue_rate_pct=round(orphan_rate, 4),
                threshold_pct=THRESHOLDS["referential_integrity"],
                status=_status_for_rate(orphan_rate, THRESHOLDS["referential_integrity"]),
                severity="Critical",
                details=(
                    f"{orphans:,} orphan record(s) of {checked:,} non-null FK values "
                    f"not found in {spec['parent_table']}.{spec['parent_column']}; "
                    f"{null_count:,} null FK value(s)"
                ),
            )
        )


def run_assessment(data_dir: Path) -> QualityReport:
    tables = load_csv_tables(data_dir)
    report = QualityReport(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        data_dir=data_dir,
    )

    check_completeness(tables, report)
    check_uniqueness(tables, report)
    check_validity(tables, report)
    check_referential_integrity(tables, report)
    return report


def write_csv_report(report: QualityReport, report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    df = report.to_dataframe()
    df.to_csv(report_path, index=False)


def _summary_counts(findings: list[QualityFinding]) -> dict[str, Any]:
    by_dimension: dict[str, dict[str, int]] = {}
    for finding in findings:
        bucket = by_dimension.setdefault(
            finding.dimension,
            {"PASS": 0, "WARN": 0, "FAIL": 0, "total": 0},
        )
        bucket[finding.status] = bucket.get(finding.status, 0) + 1
        bucket["total"] += 1

    overall = {"PASS": 0, "WARN": 0, "FAIL": 0, "total": len(findings)}
    for finding in findings:
        overall[finding.status] = overall.get(finding.status, 0) + 1

    return {"by_dimension": by_dimension, "overall": overall}


def write_html_report(report: QualityReport, report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    df = report.to_dataframe()
    summary = _summary_counts(report.findings)

    dimension_sections: list[str] = []
    for dimension in ("Completeness", "Uniqueness", "Validity", "Referential Integrity"):
        subset = df[df["dimension"] == dimension]
        if subset.empty:
            continue

        rows_html = []
        for _, row in subset.iterrows():
            status = row["status"]
            status_class = status.lower()
            rows_html.append(
                "<tr>"
                f"<td>{html.escape(str(row['table']))}</td>"
                f"<td>{html.escape(str(row['field']))}</td>"
                f"<td>{html.escape(str(row['check_name']))}</td>"
                f"<td>{int(row['total_records']):,}</td>"
                f"<td>{int(row['issue_count']):,}</td>"
                f"<td>{row['issue_rate_pct']:.2f}%</td>"
                f"<td>{row['threshold_pct']:.2f}%</td>"
                f"<td><span class=\"status {status_class}\">{html.escape(status)}</span></td>"
                f"<td>{html.escape(str(row['severity']))}</td>"
                f"<td>{html.escape(str(row['details']))}</td>"
                "</tr>"
            )

        dim_summary = summary["by_dimension"].get(dimension, {})
        dimension_sections.append(
            f"""
            <section class="dimension">
              <h2>{html.escape(dimension)}</h2>
              <p class="dim-summary">
                Checks: {dim_summary.get('total', 0)} |
                Pass: {dim_summary.get('PASS', 0)} |
                Warn: {dim_summary.get('WARN', 0)} |
                Fail: {dim_summary.get('FAIL', 0)}
              </p>
              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Table</th>
                      <th>Field</th>
                      <th>Check</th>
                      <th>Total Records</th>
                      <th>Issue Count</th>
                      <th>Issue Rate</th>
                      <th>Threshold</th>
                      <th>Status</th>
                      <th>Severity</th>
                      <th>Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {''.join(rows_html)}
                  </tbody>
                </table>
              </div>
            </section>
            """
        )

    overall = summary["overall"]
    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RWE Data Quality Assessment Report</title>
  <style>
    :root {{
      --bg: #f4f7fb;
      --card: #ffffff;
      --text: #1f2937;
      --muted: #6b7280;
      --border: #dbe3ef;
      --pass: #047857;
      --warn: #b45309;
      --fail: #b91c1c;
      --accent: #1d4ed8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Tahoma, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }}
    .container {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 24px;
    }}
    header {{
      background: linear-gradient(135deg, #1e3a8a, #2563eb);
      color: #fff;
      padding: 28px 24px;
      border-radius: 12px;
      margin-bottom: 24px;
    }}
    header h1 {{
      margin: 0 0 8px;
      font-size: 1.8rem;
    }}
    header p {{
      margin: 4px 0;
      opacity: 0.95;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 16px;
    }}
    .card .label {{
      color: var(--muted);
      font-size: 0.85rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .card .value {{
      font-size: 1.6rem;
      font-weight: 700;
      margin-top: 4px;
    }}
    .dimension {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 20px;
      margin-bottom: 20px;
    }}
    .dimension h2 {{
      margin: 0 0 8px;
      color: var(--accent);
    }}
    .dim-summary {{
      color: var(--muted);
      margin: 0 0 16px;
    }}
    .table-wrap {{
      overflow-x: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.92rem;
    }}
    th, td {{
      border-bottom: 1px solid var(--border);
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #eef2ff;
      position: sticky;
      top: 0;
    }}
    tr:nth-child(even) td {{
      background: #fafbff;
    }}
    .status {{
      display: inline-block;
      padding: 2px 10px;
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: 0.03em;
    }}
    .status.pass {{ background: #d1fae5; color: var(--pass); }}
    .status.warn {{ background: #fef3c7; color: var(--warn); }}
    .status.fail {{ background: #fee2e2; color: var(--fail); }}
    footer {{
      color: var(--muted);
      font-size: 0.85rem;
      margin-top: 12px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Real-World Data Quality Assessment</h1>
      <p>Synthea synthetic claims and clinical dataset</p>
      <p>Generated: {html.escape(report.generated_at)}</p>
      <p>Source: {html.escape(str(report.data_dir))}</p>
    </header>

    <div class="cards">
      <div class="card">
        <div class="label">Total Checks</div>
        <div class="value">{overall['total']}</div>
      </div>
      <div class="card">
        <div class="label">Pass</div>
        <div class="value">{overall.get('PASS', 0)}</div>
      </div>
      <div class="card">
        <div class="label">Warn</div>
        <div class="value">{overall.get('WARN', 0)}</div>
      </div>
      <div class="card">
        <div class="label">Fail</div>
        <div class="value">{overall.get('FAIL', 0)}</div>
      </div>
    </div>

    <section class="dimension">
      <h2>Assessment Framework</h2>
      <p class="dim-summary">
        Dimensions aligned with pharmaceutical RWE data-quality practice:
        completeness (missingness), uniqueness (patient identifier integrity),
        validity (date and coded-value conformance), and referential integrity
        (parent-child patient linkage across clinical tables).
      </p>
    </section>

    {''.join(dimension_sections)}

    <footer>
      Report files: data_quality_report.csv, data_quality_report.html
    </footer>
  </div>
</body>
</html>
"""
    report_path.write_text(document, encoding="utf-8")


def print_console_summary(report: QualityReport) -> None:
    df = report.to_dataframe()
    summary = _summary_counts(report.findings)

    print("=" * 72)
    print("RWE DATA QUALITY ASSESSMENT")
    print("=" * 72)
    print(f"Source: {report.data_dir}")
    print(f"Checks run: {summary['overall']['total']}")
    print(
        f"Results: PASS={summary['overall'].get('PASS', 0)} "
        f"WARN={summary['overall'].get('WARN', 0)} "
        f"FAIL={summary['overall'].get('FAIL', 0)}"
    )
    print()

    for dimension in ("Completeness", "Uniqueness", "Validity", "Referential Integrity"):
        subset = df[df["dimension"] == dimension]
        if subset.empty:
            continue
        fails = subset[subset["status"] == "FAIL"]
        warns = subset[subset["status"] == "WARN"]
        print(f"{dimension}: {len(subset)} checks, {len(fails)} fail, {len(warns)} warn")

        flagged = subset[subset["status"].isin(["FAIL", "WARN"])].head(5)
        for _, row in flagged.iterrows():
            print(
                f"  [{row['status']}] {row['table']}.{row['field']} "
                f"({row['check_name']}): {row['issue_count']:,} issues "
                f"({row['issue_rate_pct']:.2f}%)"
            )
        print()


def run_data_quality(data_dir: Path, report_dir: Path) -> QualityReport:
    report = run_assessment(data_dir)
    print_console_summary(report)

    csv_path = report_dir / "data_quality_report.csv"
    html_path = report_dir / "data_quality_report.html"
    write_csv_report(report, csv_path)
    write_html_report(report, html_path)

    print("=" * 72)
    print(f"CSV report written to:  {csv_path}")
    print(f"HTML report written to: {html_path}")
    print("=" * 72)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run RWE data quality assessment on Synthea CSV exports."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"Directory containing Synthea CSV files (default: {DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help=f"Directory for report output (default: {DEFAULT_REPORT_DIR})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_data_quality(args.data_dir.resolve(), args.report_dir.resolve())


if __name__ == "__main__":
    main()
