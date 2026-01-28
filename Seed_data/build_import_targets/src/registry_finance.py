"""Registry + finance composite dataset."""

from __future__ import annotations

import pandas as pd

TARGET_COLUMNS = [
    "record_type",
    "student_id",
    "section_no",
    "status",
    "invoice_number",
    "amount_paid",
    "payment_method",
    "clearance_status",
    "recorded_by_username",
]


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase/strip column names so we can address them consistently."""
    renamed = df.copy()
    renamed.columns = [str(col).strip().lower() for col in renamed.columns]
    return renamed


def build_registry_finance_table(
    registrations_df: pd.DataFrame,
    dbotransactions_df: pd.DataFrame | None = None,
    files_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return the TSV-friendly union of registration + payment rows."""
    registrations = _normalize_columns(registrations_df)
    registrations = registrations.rename(
        columns={
            "studentid": "student_id",
            "enrollmenttype": "status",
        }
    )
    registrations["record_type"] = "registration"
    registrations["section_no"] = pd.NA
    registrations["invoice_number"] = pd.NA
    registrations["amount_paid"] = pd.NA
    registrations["payment_method"] = pd.NA
    registrations["clearance_status"] = pd.NA
    registrations["recorded_by_username"] = pd.NA

    registrations = registrations[
        ["record_type", "student_id", "section_no", "status", "invoice_number"]
        + ["amount_paid", "payment_method", "clearance_status", "recorded_by_username"]
    ]

    payments = pd.DataFrame(columns=TARGET_COLUMNS)
    if dbotransactions_df is not None and not dbotransactions_df.empty:
        payments = _normalize_columns(dbotransactions_df).rename(
            columns={
                "entity": "student_id",
                "reference": "invoice_number",
                "transactiontype": "payment_method",
                "memo": "clearance_status",
            }
        )
        payments["amount_paid"] = payments.get("credit", 0).fillna(0) - payments.get(
            "debit", 0
        ).fillna(0)
        payments["record_type"] = "payment"
        payments["section_no"] = pd.NA
        payments["status"] = pd.NA
        payments["recorded_by_username"] = pd.NA
        payments = payments[
            ["record_type", "student_id", "section_no", "status", "invoice_number"]
            + [
                "amount_paid",
                "payment_method",
                "clearance_status",
                "recorded_by_username",
            ]
        ]
        if files_df is not None and not files_df.empty:
            officials = _normalize_columns(files_df).rename(
                columns={
                    "reference": "invoice_number",
                    "createdby": "recorded_by_username",
                }
            )[["invoice_number", "recorded_by_username"]]
            payments = payments.merge(
                officials, how="left", on="invoice_number", suffixes=("", "_file")
            )
            if "recorded_by_username_file" in payments:
                payments["recorded_by_username"] = payments[
                    "recorded_by_username_file"
                ].combine_first(payments["recorded_by_username"])
                payments = payments.drop(columns=["recorded_by_username_file"])

    output = pd.concat([registrations, payments], ignore_index=True)
    return output[TARGET_COLUMNS].fillna("")


__all__ = ["build_registry_finance_table"]
