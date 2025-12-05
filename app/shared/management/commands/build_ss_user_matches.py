"""Build a SmartSchool→Tusis username match dictionary."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandParser

from app.shared.importing.username_matching import best_matches

User = get_user_model()


def _normalize_header(text: str) -> str:
    """Normalize a CSV header token for comparison."""
    return text.strip().strip('"').lower()


def _read_usernames_from_csv(path: Path, columns: Iterable[str]) -> set[str]:
    """Return non-empty usernames from the provided columns."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-16")

    header_line = text.splitlines()[0] if text else ""
    delimiter = "\t" if "\t" in header_line else ","
    try:
        dialect = csv.Sniffer().sniff(header_line)
        delimiter = dialect.delimiter
    except Exception:
        pass

    rows = set()
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    available = {_normalize_header(h): h for h in (reader.fieldnames or [])}
    requested = [_normalize_header(c) for c in columns]
    matched_headers = [available[c] for c in requested if c in available]
    if not matched_headers:
        return rows

    for row in reader:
        for header in matched_headers:
            value = (row.get(header) or "").strip()
            if value:
                rows.add(value)
    return rows


def _load_existing(path: Path) -> dict[str, list[dict[str, float]]]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_mapping(path: Path, mapping: dict[str, list[dict[str, float]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping, indent=2, sort_keys=True), encoding="utf-8")


class Command(BaseCommand):
    """Compute SS→Tusis username similarity scores."""

    help = "Build a mapping of SmartSchool usernames to Tusis usernames with similarity scores."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "-s",
            "--source",
            default="Seed_data/SS_DB250711/files.csv",
            help="Path to SmartSchool CSV containing a username column.",
        )
        parser.add_argument(
            "-c",
            "--column",
            action="append",
            dest="columns",
            default=None,
            help=(
                "Column name holding the SmartSchool username (can be repeated). "
                "Defaults to UserID, CreatedBy, ModifiedBy, PrintedBy."
            ),
        )
        parser.add_argument(
            "-o",
            "--output",
            default="Seed_data/Tmp/ss_username_matches.json",
            help="Where to write the mapping.",
        )
        parser.add_argument(
            "--force-refresh",
            action="store_true",
            help="Recompute all SS usernames instead of only missing entries.",
        )

    def handle(self, *args, **options) -> str | None:
        source = Path(options["source"])
        columns = options["columns"] or ["UserID", "CreatedBy", "ModifiedBy", "PrintedBy"]
        output = Path(options["output"])
        refresh = options["force_refresh"]

        if not source.exists():
            raise FileNotFoundError(source)

        ss_usernames = _read_usernames_from_csv(source, columns)
        tusis_usernames: Iterable[str] = User.objects.values_list("username", flat=True)

        existing = {} if refresh else _load_existing(output)
        updated = dict(existing)

        new_count = 0
        for ss_name in ss_usernames:
            if ss_name in existing and not refresh:
                continue
            matches = best_matches(ss_name, tusis_usernames, top_n=2, max_gap=0.2)
            updated[ss_name] = [
                {"username": username, "score": round(score, 3)} for username, score in matches
            ]
            new_count += 1

        _save_mapping(output, updated)
        self.stdout.write(
            self.style.SUCCESS(
                f"SmartSchool usernames processed: {len(ss_usernames)} "
                f"(updated {new_count}, total stored {len(updated)})."
            )
        )
        self.stdout.write(self.style.NOTICE(f"Mapping written to {output}"))
        return None
