"""Profile Synthea synthetic healthcare CSV exports.

Loads every CSV in ``data/synthea_csv``, prints summary statistics, infers
primary keys, detects foreign-key relationships, and writes a markdown report.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "synthea_csv"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "reports"

# Synthea column name -> (referenced_table, referenced_column)
KNOWN_FOREIGN_KEYS: dict[str, tuple[str, str]] = {
    "PATIENT": ("patients", "Id"),
    "PATIENTID": ("patients", "Id"),
    "ENCOUNTER": ("encounters", "Id"),
    "APPOINTMENTID": ("encounters", "Id"),
    "ORGANIZATION": ("organizations", "Id"),
    "PROVIDER": ("providers", "Id"),
    "PROVIDERID": ("providers", "Id"),
    "PAYER": ("payers", "Id"),
    "SECONDARY_PAYER": ("payers", "Id"),
    "CLAIMID": ("claims", "Id"),
    "PRIMARYPATIENTINSURANCEID": ("payers", "Id"),
    "SECONDARYPATIENTINSURANCEID": ("payers", "Id"),
    "PATIENTINSURANCEID": ("payer_transitions", "MEMBERID"),
    "SUPERVISINGPROVIDERID": ("providers", "Id"),
}

PRIMARY_KEY_CANDIDATES = ("Id", "ID")


@dataclass
class ColumnProfile:
    name: str
    dtype: str
    non_null: int
    null_count: int
    null_pct: float
    unique: int
    unique_pct: float
    sample_values: list[str] = field(default_factory=list)


@dataclass
class TableProfile:
    name: str
    path: Path
    row_count: int
    column_count: int
    columns: list[ColumnProfile]
    primary_keys: list[str]
    foreign_keys: list[dict[str, Any]]


def load_csv_tables(data_dir: Path) -> dict[str, pd.DataFrame]:
    """Load all CSV files from *data_dir* keyed by stem name."""
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    tables: dict[str, pd.DataFrame] = {}
    for csv_path in sorted(data_dir.glob("*.csv")):
        tables[csv_path.stem] = pd.read_csv(csv_path, low_memory=False)
    if not tables:
        raise FileNotFoundError(f"No CSV files found in: {data_dir}")
    return tables


def profile_column(series: pd.Series) -> ColumnProfile:
    """Build a profile for a single column."""
    row_count = len(series)
    non_null = int(series.notna().sum())
    null_count = row_count - non_null
    unique = int(series.nunique(dropna=True))
    null_pct = (null_count / row_count * 100) if row_count else 0.0
    unique_pct = (unique / non_null * 100) if non_null else 0.0

    sample = series.dropna().astype(str).head(3).tolist()
    return ColumnProfile(
        name=series.name,
        dtype=str(series.dtype),
        non_null=non_null,
        null_count=null_count,
        null_pct=round(null_pct, 2),
        unique=unique,
        unique_pct=round(unique_pct, 2),
        sample_values=sample,
    )


def identify_primary_keys(df: pd.DataFrame, table_name: str) -> list[str]:
    """Infer primary key column(s) for a table."""
    row_count = len(df)
    if row_count == 0:
        return []

    for candidate in PRIMARY_KEY_CANDIDATES:
        if candidate in df.columns:
            series = df[candidate]
            if series.notna().all() and series.nunique() == row_count:
                return [candidate]

    singletons = [
        col
        for col in df.columns
        if df[col].notna().all() and df[col].nunique() == row_count
    ]
    if len(singletons) == 1:
        return singletons

    # Tables without a surrogate key often use composite natural keys.
    if table_name in {
        "conditions",
        "observations",
        "medications",
        "procedures",
        "allergies",
        "immunizations",
        "supplies",
        "devices",
        "payer_transitions",
    }:
        return ["(composite - no single surrogate key)"]

    return []


def fk_match_rate(
    source: pd.Series,
    target_values: set[Any],
) -> tuple[float, int, int]:
    """Return match rate and counts for non-null FK values."""
    non_null = source.dropna()
    checked = len(non_null)
    if checked == 0:
        return 0.0, 0, 0
    matched = int(non_null.isin(target_values).sum())
    return matched / checked, matched, checked


def identify_foreign_keys(
    table_name: str,
    df: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
    primary_keys: dict[str, list[str]],
) -> list[dict[str, Any]]:
    """Detect foreign-key relationships via naming conventions and value overlap."""
    relationships: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    for column in df.columns:
        if column in primary_keys.get(table_name, []):
            continue

        candidates: list[tuple[str, str]] = []
        if column in KNOWN_FOREIGN_KEYS:
            candidates.append(KNOWN_FOREIGN_KEYS[column])
        elif column.endswith("ID") and column not in KNOWN_FOREIGN_KEYS:
            stem = column[:-2].lower()
            for ref_table, pk_cols in primary_keys.items():
                if pk_cols and pk_cols[0].startswith("("):
                    continue
                if stem == ref_table or stem.rstrip("s") == ref_table.rstrip("s"):
                    candidates.append((ref_table, pk_cols[0]))

        for ref_table, ref_column in candidates:
            if ref_table not in tables or ref_column not in tables[ref_table].columns:
                continue

            ref_values = set(tables[ref_table][ref_column].dropna().unique())
            rate, matched, checked = fk_match_rate(df[column], ref_values)
            if checked == 0:
                continue

            key = (table_name, column, ref_table, ref_column)
            if key in seen:
                continue
            seen.add(key)

            confidence = "high" if rate >= 0.99 else "medium" if rate >= 0.90 else "low"
            if rate >= 0.90:
                relationships.append(
                    {
                        "source_table": table_name,
                        "source_column": column,
                        "target_table": ref_table,
                        "target_column": ref_column,
                        "match_rate_pct": round(rate * 100, 2),
                        "matched_values": matched,
                        "checked_values": checked,
                        "confidence": confidence,
                        "known_mapping": column in KNOWN_FOREIGN_KEYS,
                    }
                )

    return sorted(relationships, key=lambda r: (-r["match_rate_pct"], r["source_column"]))


def profile_table(
    name: str,
    df: pd.DataFrame,
    path: Path,
    primary_keys: dict[str, list[str]],
    foreign_keys: list[dict[str, Any]] | None = None,
) -> TableProfile:
    """Build a full profile for one table."""
    columns = [profile_column(df[col]) for col in df.columns]
    pks = identify_primary_keys(df, name)
    primary_keys[name] = pks

    return TableProfile(
        name=name,
        path=path,
        row_count=len(df),
        column_count=len(df.columns),
        columns=columns,
        primary_keys=pks,
        foreign_keys=foreign_keys or [],
    )


def print_console_summary(profiles: list[TableProfile]) -> None:
    """Print a human-readable summary to stdout."""
    print("=" * 72)
    print("SYNTHEA CSV DATA PROFILE")
    print("=" * 72)
    print(f"Tables loaded: {len(profiles)}")
    print()

    print("DATASET DIMENSIONS")
    print("-" * 72)
    total_rows = 0
    for profile in profiles:
        total_rows += profile.row_count
        print(f"  {profile.name:25s}  {profile.row_count:>10,} rows x {profile.column_count:>3} cols")
    print(f"  {'TOTAL':25s}  {total_rows:>10,} rows")
    print()

    for profile in profiles:
        print("=" * 72)
        print(f"TABLE: {profile.name}")
        print(f"File:  {profile.path.name}")
        print(f"Shape: {profile.row_count:,} rows x {profile.column_count} columns")
        print("-" * 72)

        print("Columns:")
        for col in profile.columns:
            print(
                f"  - {col.name:<28} {col.dtype:<12} "
                f"null={col.null_pct:5.1f}%  unique={col.unique:>8,} ({col.unique_pct:.1f}%)"
            )

        print()
        if profile.primary_keys:
            print(f"Primary key(s): {', '.join(profile.primary_keys)}")
        else:
            print("Primary key(s): (not identified)")

        if profile.foreign_keys:
            print("Foreign keys:")
            for fk in profile.foreign_keys:
                known = " [known Synthea mapping]" if fk["known_mapping"] else ""
                print(
                    f"  - {fk['source_column']} -> "
                    f"{fk['target_table']}.{fk['target_column']}  "
                    f"({fk['match_rate_pct']:.2f}% match, {fk['confidence']}){known}"
                )
        else:
            print("Foreign keys: (none detected)")
        print()


def write_markdown_report(
    profiles: list[TableProfile],
    data_dir: Path,
    report_path: Path,
) -> None:
    """Write a markdown data-profile report."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "# Synthea CSV Data Profile Report",
        "",
        f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"- Source directory: `{data_dir}`",
        f"- Tables: {len(profiles)}",
        "",
        "## Dataset Overview",
        "",
        "| Table | Rows | Columns | Primary Key |",
        "| --- | ---: | ---: | --- |",
    ]

    for profile in profiles:
        pk = ", ".join(profile.primary_keys) if profile.primary_keys else "—"
        lines.append(
            f"| {profile.name} | {profile.row_count:,} | {profile.column_count} | {pk} |"
        )

    lines.extend(["", "## Entity Relationships", ""])
    all_fks = [fk for p in profiles for fk in p.foreign_keys]
    if all_fks:
        lines.extend(
            [
                "| Source Table | Source Column | Target Table | Target Column | Match % | Confidence |",
                "| --- | --- | --- | --- | ---: | --- |",
            ]
        )
        for fk in sorted(all_fks, key=lambda r: (r["source_table"], r["source_column"])):
            lines.append(
                f"| {fk['source_table']} | {fk['source_column']} | "
                f"{fk['target_table']} | {fk['target_column']} | "
                f"{fk['match_rate_pct']:.2f} | {fk['confidence']} |"
            )
    else:
        lines.append("_No foreign-key relationships detected._")

    for profile in profiles:
        lines.extend(
            [
                "",
                f"## {profile.name}",
                "",
                f"- **File:** `{profile.path.name}`",
                f"- **Shape:** {profile.row_count:,} rows × {profile.column_count} columns",
                f"- **Primary key(s):** {', '.join(profile.primary_keys) if profile.primary_keys else '—'}",
                "",
                "### Columns",
                "",
                "| Column | Dtype | Non-Null | Null % | Unique | Unique % | Sample Values |",
                "| --- | --- | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for col in profile.columns:
            samples = ", ".join(col.sample_values) if col.sample_values else ""
            lines.append(
                f"| {col.name} | {col.dtype} | {col.non_null:,} | {col.null_pct} | "
                f"{col.unique:,} | {col.unique_pct} | {samples} |"
            )

        if profile.foreign_keys:
            lines.extend(["", "### Foreign Keys", ""])
            for fk in profile.foreign_keys:
                lines.append(
                    f"- `{fk['source_column']}` → `{fk['target_table']}.{fk['target_column']}` "
                    f"({fk['match_rate_pct']:.2f}% of {fk['checked_values']:,} values matched)"
                )

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_profile(data_dir: Path, report_dir: Path) -> list[TableProfile]:
    """Load CSVs, build profiles, print summary, and write report."""
    tables = load_csv_tables(data_dir)
    primary_keys: dict[str, list[str]] = {}

    profiles: list[TableProfile] = []
    for name, df in tables.items():
        path = data_dir / f"{name}.csv"
        profiles.append(profile_table(name, df, path, primary_keys))

    for i, (name, df) in enumerate(tables.items()):
        fks = identify_foreign_keys(name, df, tables, primary_keys)
        profile = profiles[i]
        profiles[i] = TableProfile(
            name=profile.name,
            path=profile.path,
            row_count=profile.row_count,
            column_count=profile.column_count,
            columns=profile.columns,
            primary_keys=profile.primary_keys,
            foreign_keys=fks,
        )

    profiles.sort(key=lambda p: p.name)
    print_console_summary(profiles)

    report_path = report_dir / "synthea_data_profile.md"
    write_markdown_report(profiles, data_dir, report_path)
    print("=" * 72)
    print(f"Report written to: {report_path}")
    print("=" * 72)

    return profiles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile Synthea CSV exports.")
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
        help=f"Directory for markdown report output (default: {DEFAULT_REPORT_DIR})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_profile(args.data_dir.resolve(), args.report_dir.resolve())


if __name__ == "__main__":
    main()
