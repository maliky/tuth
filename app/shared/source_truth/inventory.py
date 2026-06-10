"""Source inventory and SmartSchool table integrity checks."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from app.shared.source_truth.io import RowT, profile_file, read_rows

InventoryRowsT: TypeAlias = list[RowT]
VerifiedRowsT: TypeAlias = dict[str, int]
FileNamesT: TypeAlias = Iterable[str]


@dataclass(frozen=True)
class SourcePathT:
    """Configured source path with a stable source label."""

    source_name: str
    root: Path
    pattern: str


def smartschool_csv_name(table_name: str) -> str:
    """Return the CSV filename for a SmartSchool dbo table."""
    return f"dbo_{table_name}.csv"


def table_status(
    expected_rows: int,
    actual_rows: int,
    column_count: int,
    *,
    verified_rows: int | None = None,
) -> str:
    """Classify whether a CSV export can be trusted for its manifest table."""
    if expected_rows > 0 and column_count == 0 and actual_rows == 0:
        return "empty_export_for_nonempty_manifest"
    if verified_rows is not None and verified_rows == actual_rows and column_count > 0:
        return "ok_verified_reexport"
    if expected_rows == actual_rows and column_count > 0:
        return "ok"
    if expected_rows == 0 and actual_rows == 0:
        return "ok_empty"
    return "row_count_mismatch"


def build_smartschool_integrity(
    smartschool_dir: Path, table_names: set[str] | None = None
) -> InventoryRowsT:
    """Compare latest SmartSchool manifest row counts to actual CSV exports."""
    manifest_path = smartschool_dir / "_table_manifest.csv"
    verified_rows = _load_verified_reexport_rows(smartschool_dir)
    rows: InventoryRowsT = []
    if not manifest_path.exists():
        return rows
    for manifest in read_rows(manifest_path):
        table_name = manifest.get("table_name", "")
        if not table_name:
            continue
        if table_names is not None and table_name not in table_names:
            continue
        path = smartschool_dir / smartschool_csv_name(table_name)
        expected = _to_int(manifest.get("row_count", "0"))
        if not path.exists():
            rows.append(
                {
                    "table_name": table_name,
                    "manifest_rows": str(expected),
                    "actual_rows": "0",
                    "column_count": "0",
                    "status": "missing_file",
                    "selected_source": "fallback_required",
                    "selected_path": "",
                }
            )
            continue
        profile = profile_file(path)
        status = table_status(
            expected,
            profile.actual_rows,
            len(profile.headers),
            verified_rows=verified_rows.get(table_name),
        )
        rows.append(
            {
                "table_name": table_name,
                "manifest_rows": str(expected),
                "actual_rows": str(profile.actual_rows),
                "column_count": str(len(profile.headers)),
                "status": status,
                "selected_source": (
                    "latest_smartschool"
                    if status in {"ok", "ok_empty", "ok_verified_reexport"}
                    else "fallback_required"
                ),
                "selected_path": str(path),
            }
        )
    return rows


def build_source_inventory(paths: Iterable[SourcePathT]) -> InventoryRowsT:
    """Profile configured source roots without mutating raw data."""
    rows: InventoryRowsT = []
    for source_path in paths:
        if not source_path.root.exists():
            rows.append(_missing_inventory_row(source_path))
            continue
        for path in sorted(source_path.root.glob(source_path.pattern)):
            profile = profile_file(path)
            rows.append(
                {
                    "source_name": source_path.source_name,
                    "path": str(path),
                    "actual_rows": str(profile.actual_rows),
                    "column_count": str(len(profile.headers)),
                    "size_bytes": str(profile.size_bytes),
                    "sha256": profile.sha256,
                    "headers": "|".join(profile.headers[:20]),
                    "status": "present",
                }
            )
    return rows


def build_configured_inventory(
    *,
    smartschool_dir: Path,
    fundamentals_dir: Path,
    grapro_csv_dir: Path,
    tucurricula_import_dir: Path,
    grapro_mdb: Path,
    smartschool_tables: FileNamesT | None = None,
    fundamental_files: FileNamesT | None = None,
    grapro_files: FileNamesT | None = None,
    tucurricula_files: FileNamesT | None = None,
) -> InventoryRowsT:
    """Return source inventory rows for the standard TUSIS truth inputs."""
    if any(
        files is not None
        for files in (
            smartschool_tables,
            fundamental_files,
            grapro_files,
            tucurricula_files,
        )
    ):
        rows = [
            *_build_named_source_inventory(
                "latest_smartschool",
                smartschool_dir,
                (
                    smartschool_csv_name(table_name)
                    for table_name in smartschool_tables or ()
                ),
            ),
            *_build_named_source_inventory(
                "fundamentals_smartschool", fundamentals_dir, fundamental_files or ()
            ),
            *_build_named_source_inventory(
                "grapro_legacy_csv", grapro_csv_dir, grapro_files or ()
            ),
            *_build_named_source_inventory(
                "tucurricula_import", tucurricula_import_dir, tucurricula_files or ()
            ),
        ]
    else:
        rows = build_source_inventory(
            (
                SourcePathT("latest_smartschool", smartschool_dir, "*.csv"),
                SourcePathT("fundamentals_smartschool", fundamentals_dir, "*.csv"),
                SourcePathT("fundamentals_smartschool", fundamentals_dir, "*.tsv"),
                SourcePathT("grapro_legacy_csv", grapro_csv_dir, "*.csv"),
                SourcePathT("tucurricula_import", tucurricula_import_dir, "*.tsv"),
            )
        )
    if grapro_mdb.exists():
        rows.append(
            {
                "source_name": "grapro_legacy_mdb",
                "path": str(grapro_mdb),
                "actual_rows": "0",
                "column_count": "0",
                "size_bytes": str(grapro_mdb.stat().st_size),
                "sha256": "",
                "headers": "",
                "status": "present_binary_mdb",
            }
        )
    return rows


def _build_named_source_inventory(
    source_name: str, root: Path, filenames: FileNamesT
) -> InventoryRowsT:
    """Profile an explicit file list for scoped source-truth builds."""
    rows: InventoryRowsT = []
    for filename in filenames:
        path = root / filename
        if not path.exists():
            rows.append(
                {
                    "source_name": source_name,
                    "path": str(path),
                    "actual_rows": "0",
                    "column_count": "0",
                    "size_bytes": "0",
                    "sha256": "",
                    "headers": "",
                    "status": "missing_file",
                }
            )
            continue
        profile = profile_file(path)
        rows.append(
            {
                "source_name": source_name,
                "path": str(path),
                "actual_rows": str(profile.actual_rows),
                "column_count": str(len(profile.headers)),
                "size_bytes": str(profile.size_bytes),
                "sha256": profile.sha256,
                "headers": "|".join(profile.headers[:20]),
                "status": "present",
            }
        )
    return rows


def list_mdb_tables(path: Path) -> InventoryRowsT:
    """List MDB table names when mdbtools is available."""
    if not path.exists() or shutil.which("mdb-tables") is None:
        return []
    result = subprocess.run(
        ["mdb-tables", "-1", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return [{"table_name": "", "status": f"mdb_tables_failed:{result.returncode}"}]
    return [
        {"table_name": line.strip(), "status": "present"}
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def ok_smartschool_tables(rows: Iterable[RowT]) -> set[str]:
    """Return SmartSchool table names whose latest CSV passed integrity checks."""
    ok_statuses = {"ok", "ok_empty", "ok_verified_reexport"}
    return {row["table_name"] for row in rows if row.get("status") in ok_statuses}


def _load_verified_reexport_rows(smartschool_dir: Path) -> VerifiedRowsT:
    """Return table row counts verified by the no-sequential re-export pass."""
    path = smartschool_dir / "_reexport_attempts_no_sequential.csv"
    if not path.exists():
        return {}
    verified: VerifiedRowsT = {}
    for row in read_rows(path):
        if row.get("status") != "OK":
            continue
        table_name = row.get("table", "")
        if not table_name:
            continue
        verified[table_name] = _to_int(row.get("written_rows"))
    return verified


def _missing_inventory_row(source_path: SourcePathT) -> RowT:
    """Return one inventory row for a missing configured source root."""
    return {
        "source_name": source_path.source_name,
        "path": str(source_path.root),
        "actual_rows": "0",
        "column_count": "0",
        "size_bytes": "0",
        "sha256": "",
        "headers": "",
        "status": "missing_root",
    }


def _to_int(value: str | None) -> int:
    """Parse an integer cell, defaulting bad values to zero."""
    try:
        return int(str(value or "0").strip())
    except ValueError:
        return 0
