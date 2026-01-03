"""Functional helpers to import people from directory data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
import phonenumbers

from app.people.utils import NameParts, parse_name
from app.shared.importing import CsvRowLogger, drop_constant_columns, get_import_logger
from app.shared.utils import get_in_row


@dataclass
class DirectoryRow:
    """Normalized representation of a directory entry."""

    first_name: str
    last_name: str
    full_name: str
    email: str
    position: str
    phone: str
    division: str
    org_unit_path: str
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


def tag_legacy(
    bio_tags: list[str], full_name: str, username: str, email: str
) -> list[str]:
    """Append legacy tags for username/email when available."""
    tags = list(bio_tags)
    if full_name:
        tags.append(f"legacy_fullname: {full_name}")
    if username:
        tags.append(f"legacy_username: {username}")
    if email:
        tags.append(f"legacy_email: {email}")
    return tags


def load_directory_rows(path: Path) -> list[DirectoryRow]:
    """Load and normalize rows from a directory CSV/XLSX."""
    logger = get_import_logger()
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path, dtype="str")
        if "Name" in df:
            to_drop = df.loc[df["Name"].str.contains("Showing")].index
            df = df.drop(to_drop)
    else:
        df = pd.read_csv(path, dtype="str")
        df.loc[:, "Name"] = df["First Name [Required]"] + " " + df["Last Name [Required]"]
        df = df.drop(columns=["Last Name [Required]", "First Name [Required]"])
        if "Org Unit Path [Required]" in df.columns:
            df.loc[:, "Org Unit Path [Required]"] = df[
                "Org Unit Path [Required]"
            ].str.replace("/", "")
    df = df.fillna("")
    # Drop sensitive password columns if present
    pwd_columns = [c for c in df.columns if "password" in c.lower()]
    df = df.drop(columns=pwd_columns)
    df = drop_constant_columns(df, log_fn=lambda msg: logger.info(msg))
    # Harmonize expected columns
    df = df.rename(
        columns={
            "Email Address [Required]": "email",
            "Recovery Email": "recovery_email",
            "Employee Title": "position",
            "Department": "division",
            "Org Unit Path [Required]": "org_unit_path",
            "CellNo": "cell",
            "Email": "email",
            "Position": "position",
            "Offices/Divisions": "division",
            "Name": "full_name",
        }
    )

    rows: list[DirectoryRow] = []
    for _, row in df.iterrows():
        row_dict = row.to_dict() if hasattr(row, "to_dict") else dict(row)
        email = get_in_row("email", row_dict)
        if not email:
            continue

        # Build name from the unified full_name column (first/last already concatenated for CSV)
        full_name = get_in_row("full_name", row_dict)
        _n = parse_name(full_name)  # not used?

        position = get_in_row("position", row_dict)
        division = get_in_row("division", row_dict)
        # Collect phones: choose a primary, keep alternates as bio tags
        phone_candidates = [
            row_dict.get("cell"),
            row_dict.get("Mobile Phone"),
            row_dict.get("Work Phone"),
            row_dict.get("Home Phone"),
            row_dict.get("Recovery Phone [MUST BE IN THE E.164 FORMAT]"),
        ]
        phone_cleaned = [format_phone(p) for p in phone_candidates if p]
        phone_primary = phone_cleaned[0] if phone_cleaned else ""
        phone_alts = phone_cleaned[1:] if len(phone_cleaned) > 1 else []
        legacy_user = extract_legacy_username(email)

        bio_tags: list[str] = []
        # legacy identifiers
        bio_tags = tag_legacy(bio_tags, full_name, legacy_user, email)
        # alternate emails
        for key in ["Recovery Email", "Home Secondary Email", "Work Secondary Email"]:
            extra_email = get_in_row(key, row_dict)
            if extra_email:
                bio_tags.append(f"alt_email: {extra_email}")
        # alternate phones
        for extra_phone in phone_alts:
            bio_tags.append(f"alt_phone: {extra_phone}")
        oup = get_in_row("org_unit_path", row_dict)
        if oup:
            bio_tags.append(f"org_unit_path: {oup}")
        # any remaining non-empty columns not already captured
        mapped_keys = {
            "full_name",
            "email",
            "position",
            "division",
            "org_unit_path",
            "cell",
            "Mobile Phone",
            "Work Phone",
            "Home Phone",
            "Recovery Phone [MUST BE IN THE E.164 FORMAT]",
            "Recovery Email",
            "Home Secondary Email",
            "Work Secondary Email",
        }
        residual = {
            k: v for k, v in row_dict.items() if k not in mapped_keys and str(v).strip()
        }
        for key, val in residual.items():
            bio_tags.append(f"{key}: {val}")

        rows.append(
            DirectoryRow(
                first_name=_n.first,
                last_name=_n.last,
                full_name=full_name,
                email=email,
                position=position,
                phone=phone_primary,
                division=division,
                org_unit_path=get_in_row("org_unit_path", row_dict),
                bio_tags=bio_tags,
            )
        )
    return rows
