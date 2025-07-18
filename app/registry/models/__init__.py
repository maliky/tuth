"""Initialization for the models package."""

# app/registry/models/__init__.py
from .document import Document
from .grade import Grade
from .registration import Registration

__all__ = ["Document", "Registration", "Grade"]
