"""Functional helpers to import people from directory data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
import phonenumbers

from app.people.importing.names import NameParts, parse_name
from app.shared.importing.loggers import CsvRowLogger


@dataclass
class DirectoryRow:
    """Normalized representation of a directory entry."""

    first_name: str
    last_name: str
    email: str
    position: str
    phone: str
    division: str
    bio_tags: list[str]


def format_phone(raw: str | float | int | None) -> str:
    """Return a normalized Liberian phone number in E.164, or empty string if invalid."""
    if raw is None:
        return ""
    text = str(raw).strip()
    text = text.replace(" ", "").replace("\u00a0", "")
    text = text.replace("o", "0").replace("O", "0")
    for ch in "-().":
        text = text.replace(ch, "")
    if not text:
        return ""
    # tolerate numbers without +231; default to LR region
    try:
        num = phonenumbers.parse(text, "LR")
        if not phonenumbers.is_valid_number(num):
            return ""
        return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        return ""


def extract_legacy_username(email: str) -> str:
    """Derive a legacy username from an email before @."""
    if not email or "@" not in email:
        return ""
    return email.split("@", 1)[0].strip()


def tag_legacy(bio_tags: list[str], username: str, email: str) -> list[str]:
    """Append legacy tags for username/email when available."""
    tags = list(bio_tags)
    if username:
        tags.append(f"legacy_username: {username}")
    if email:
        tags.append(f"legacy_email: {email}")
    return tags


def load_directory_rows(path: Path) -> list[DirectoryRow]:
    """Load and normalize rows from a directory CSV/XLSX."""
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)

    # Harmonize expected columns
    df = df.rename(
        columns={
            "First Name [Required]": "first_name",
            "Last Name [Required]": "last_name",
            "Email Address [Required]": "email",
            "Recovery Email": "recovery_email",
            "Employee Title": "position",
            "Department": "division",
            "CellNo": "cell",
            "Email": "email",
            "Position": "position",
            "Offices/Divisions": "division",
            "Name": "full_name",
        }
    )

    rows: list[DirectoryRow] = []
    for _, row in df.iterrows():
        row_dict = row.to_dict() if hasattr(row, "to_dict") else row
        email = get_in_row("email", row_dict)
        if not email:
            continue

        # Prefer split components; fall back to a generic full_name when present
        full_name = " ".join(
            part
            for part in [
                get_in_row("first_name", row_dict),
                get_in_row("last_name", row_dict),
                get_in_row("full_name", row_dict),
            ]
            if part
        )
        name = parse_name(full_name)

        position = get_in_row("position", row_dict)
        division = get_in_row("division", row_dict)
        phone = format_phone(
            row_dict.get("cell")
            or row_dict.get("Mobile Phone")
            or row_dict.get("Work Phone")
        )
        legacy_user = extract_legacy_username(email)
        bio_tags: list[str] = []
        bio_tags = tag_legacy(bio_tags, legacy_user, email)

        rows.append(
            DirectoryRow(
                first_name=name.first,
                last_name=name.last,
                email=email,
                position=position,
                phone=phone,
                division=division,
                bio_tags=bio_tags,
            )
        )
    return rows
