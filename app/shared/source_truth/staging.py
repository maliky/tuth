"""SQLite staging primitives for source-truth builds."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from app.shared.source_truth.io import RowT

RowsT: TypeAlias = Iterable[RowT]


@dataclass(frozen=True)
class StageResultT:
    """Counts written to the SQLite staging database."""

    witness_rows: int
    report_rows: int


def open_stage(path: Path) -> sqlite3.Connection:
    """Open and initialize the reconciliation SQLite database."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    _init_schema(conn)
    return conn


def stage_witness_rows(
    conn: sqlite3.Connection, domain: str, rows: RowsT, *, key_field: str = "row_key"
) -> int:
    """Store normalized witness rows with payload hashes."""
    count = 0
    for row in rows:
        payload = _payload(row)
        conn.execute(
            """
            INSERT INTO witness_rows(domain, source_name, row_key, payload_json, row_hash)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                domain,
                row.get("source_name", ""),
                row.get(key_field, "") or _hash_payload(payload),
                payload,
                _hash_payload(payload),
            ),
        )
        count += 1
    conn.commit()
    return count


def stage_report_rows(conn: sqlite3.Connection, report_name: str, rows: RowsT) -> int:
    """Store report rows in SQLite for traceability."""
    count = 0
    for row_number, row in enumerate(rows, start=1):
        conn.execute(
            """
            INSERT INTO report_rows(report_name, row_number, payload_json)
            VALUES (?, ?, ?)
            """,
            (report_name, row_number, _payload(row)),
        )
        count += 1
    conn.commit()
    return count


def stage_output_count(conn: sqlite3.Connection, filename: str, row_count: int) -> None:
    """Record one generated output file count."""
    conn.execute(
        """
        INSERT INTO output_files(filename, row_count)
        VALUES (?, ?)
        """,
        (filename, row_count),
    )
    conn.commit()


def stage_truth_witnesses(
    conn: sqlite3.Connection,
    *,
    courses: RowsT,
    curricula: RowsT,
    curriculum_courses: RowsT,
    requirements: RowsT,
    students: RowsT,
    grades: RowsT,
    registrations: RowsT,
    semester_enrollments: RowsT,
    payments: RowsT,
) -> None:
    """Persist normalized source-truth witnesses into SQLite."""
    stage_witness_rows(conn, "course", courses)
    stage_witness_rows(conn, "curriculum", curricula, key_field="curriculum")
    stage_witness_rows(
        conn, "curriculum_course", curriculum_courses, key_field="curriculum"
    )
    stage_witness_rows(conn, "curriculum_requirement", requirements)
    stage_witness_rows(conn, "student", students, key_field="student_id")
    stage_witness_rows(conn, "grade", grades)
    stage_witness_rows(conn, "registration", registrations)
    stage_witness_rows(conn, "semester_enrollment", semester_enrollments)
    stage_witness_rows(conn, "payment", payments)


def _init_schema(conn: sqlite3.Connection) -> None:
    """Create staging tables if this is a fresh run."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS witness_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            source_name TEXT NOT NULL,
            row_key TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            row_hash TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_witness_domain_key
            ON witness_rows(domain, row_key);
        CREATE TABLE IF NOT EXISTS report_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_name TEXT NOT NULL,
            row_number INTEGER NOT NULL,
            payload_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_report_name
            ON report_rows(report_name);
        CREATE TABLE IF NOT EXISTS output_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            row_count INTEGER NOT NULL
        );
        """
    )
    conn.commit()


def _payload(row: RowT) -> str:
    """Serialize a row deterministically."""
    return json.dumps(row, sort_keys=True, ensure_ascii=True)


def _hash_payload(payload: str) -> str:
    """Return a stable row hash."""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
