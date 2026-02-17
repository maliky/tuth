"""Initialization for the admin package."""

from .resources import CrsResource, CurriCrsResource
from .core import (
    CollegeAdmin,
    CrsAdmin,
    CurriAdmin,
    CurriCrsAdmin,
    PrerequisiteAdmin,
    CurriStdEnrollAdmin,
)

__all__ = [
    "CrsResource",
    "CurriCrsResource",
    "CollegeAdmin",
    "CrsAdmin",
    "CurriAdmin",
    "CurriCrsAdmin",
    "PrerequisiteAdmin",
    "CurriStdEnrollAdmin",
]
