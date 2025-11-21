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


def build_registry_finance_table(
    registrations_df: pd.DataFrame,
    dbotransactions_df: pd.DataFrame | None = None,
    files_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return the TSV-friendly union of registration + payment rows."""
    registrations = registrations_df.rename(
        columns={
            "studentid": "student_id",
            "enrollmenttype": "status",
        }
    ).copy()
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
        payments = dbotransactions_df.rename(
            columns={
                "Entity": "student_id",
                "Reference": "invoice_number",
                "TransactionType": "payment_method",
                "Memo": "clearance_status",
            }
        ).copy()
        payments["amount_paid"] = (
            payments["Credit"].fillna(0) - payments["Debit"].fillna(0)
        )
        payments["record_type"] = "payment"
        payments["section_no"] = pd.NA
        payments["status"] = pd.NA
        payments["recorded_by_username"] = pd.NA
        payments = payments[
            ["record_type", "student_id", "section_no", "status", "invoice_number"]
            + ["amount_paid", "payment_method", "clearance_status", "recorded_by_username"]
        ]
        if files_df is not None and not files_df.empty:
            officials = files_df.rename(
                columns={
                    "Reference": "invoice_number",
                    "CreatedBy": "recorded_by_username",
                }
            )[["invoice_number", "recorded_by_username"]]
            payments = payments.merge(
                officials, how="left", on="invoice_number", suffixes=("", "_file")
            )
            payments["recorded_by_username"] = payments[
                ["recorded_by_username_file", "recorded_by_username"]
            ].bfill(axis=1)[0]
            payments = payments.drop(columns=["recorded_by_username_file"])

    output = pd.concat([registrations, payments], ignore_index=True)
    return output[TARGET_COLUMNS].fillna("")


__all__ = ["build_registry_finance_table"]
