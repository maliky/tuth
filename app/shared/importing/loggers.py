"""Lightweight CSV logger helpers used by import commands."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Iterable, Mapping

from django.core.management.base import BaseCommand


def get_import_logger() -> logging.Logger:
    """Return a namespaced logger for imports."""
    return logging.getLogger("tusis.import")


class CsvRowLogger:
    """Collect rows and dump them to a CSV file at report time."""

    def __init__(self, filename: str, headers: Iterable[str], message_template: str):
        self.path = Path(filename)
        self.headers = list(headers)
        self.message_template = message_template
        self.rows: list[Mapping[str, str]] = []

    def log(self, row: Mapping[str, str]) -> None:
        """Accumulate a row for later writing."""
        self.rows.append(row)

    def report(self, cmd: BaseCommand) -> None:
        """Write accumulated rows and emit a summary message."""
        if not self.rows:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=self.headers)
            writer.writeheader()
            for row in self.rows:
                writer.writerow({k: row.get(k, "") for k in self.headers})

        msg = self.message_template.format(count=len(self.rows), path=self.path)
        cmd.stdout.write(cmd.style.WARNING(msg))
