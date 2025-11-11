"""Initialization for the models package."""
from .core import Space, Room

# Backwards compatibility alias
Location = Space

__all__ = [
    "Room",
    "Space",
    "Location",
]
