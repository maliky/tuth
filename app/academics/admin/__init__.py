"""Initialization for the admin package."""

from .requirement_resources import CurriCrsRequirementResource
from .resources import CrsResource, CurriCrsResource, CurriResource
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
    "CurriCrsRequirementResource",
    "CurriResource",
    "CollegeAdmin",
    "CrsAdmin",
    "CurriAdmin",
    "CurriCrsAdmin",
    "PrerequisiteAdmin",
    "CurriStdEnrollAdmin",
]
