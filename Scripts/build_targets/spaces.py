"""Spaces-domain transforms."""

from __future__ import annotations

import re

import pandas as pd


_LOCATION_RE = re.compile(r"^(?P<space>[A-Za-z]+)(?P<room>.*)$")


def _split_location(value: str) -> tuple[str, str]:
    raw = str(value).strip()
    if not raw:
        return "", ""
    match = _LOCATION_RE.match(raw.replace(" ", ""))
    if not match:
        return raw, raw
    return match.group("space").upper(), match.group("room").upper()


def build_rooms_table(
    sections_df: pd.DataFrame,
    *,
    schedule_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return RoomResource rows from section/schedule tables."""
    rooms = sections_df[["Location", "Capacity"]].dropna(how="all").copy()
    rooms = rooms.rename(columns={"Location": "location", "Capacity": "standard_capacity"})
    split = rooms["location"].map(_split_location).apply(pd.Series)
    split.columns = ["space", "room"]
    rooms = pd.concat([rooms, split], axis=1)
    rooms["standard_capacity"] = (
        rooms["standard_capacity"]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0)
        .astype(int)
    )
    rooms = rooms[["space", "room", "standard_capacity"]]

    if schedule_df is not None and not schedule_df.empty:
        extra = schedule_df[["RoomNo"]].dropna().rename(columns={"RoomNo": "location"})
        extra["standard_capacity"] = 0
        split_extra = extra["location"].map(_split_location).apply(pd.Series)
        split_extra.columns = ["space", "room"]
        extra = pd.concat([extra, split_extra], axis=1)
        rooms = pd.concat(
            [rooms, extra[["space", "room", "standard_capacity"]]], ignore_index=True
        )

    rooms = (
        rooms.drop_duplicates(subset=["space", "room"])
        .sort_values(["space", "room"])
        .reset_index(drop=True)
    )
    rooms["exam_capacity"] = rooms["standard_capacity"]
    return rooms[["space", "room", "standard_capacity", "exam_capacity"]]


__all__ = ["build_rooms_table"]
