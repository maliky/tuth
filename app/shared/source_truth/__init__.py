"""Read-only source-truth builders for TUSIS data reconciliation."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.shared.source_truth.builder import build_tusis_truth

__all__ = ["build_tusis_truth"]


def __getattr__(name: str) -> object:
    """Lazy-load Django-dependent builders only when callers request them."""
    if name == "build_tusis_truth":
        from app.shared.source_truth.builder import build_tusis_truth

        return build_tusis_truth
    raise AttributeError(name)
