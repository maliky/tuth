"""Section fee module."""

from __future__ import annotations

from django.db import models
from simple_history.models import HistoricalRecords

from app.finance.models.status_types_methods import FeeType


class SectionFee(models.Model):
    """Additional fee charged for a specific course section.

    Attributes:
        section (timetable.Section): Section the fee applies to.
        fee_type (str): Type of fee as defined in :class:FeeType.
        amount (Decimal): Monetary value of the fee.

    Example:
        >>> from decimal import Decimal
        >>> SectionFee.objects.create(
        ...     section=section,
        ...     fee_type=FeeType.objects.get(code='lab'),
        ...     amount=Decimal("25.00"),
        ... )
        >>> SectionFee.objects.create(section=section, fee_type=FeeType.LAB, amount=50)
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    section = models.ForeignKey("timetable.Section", on_delete=models.CASCADE)
    fee_type = models.ForeignKey(
        "finance.FeeType",
        on_delete=models.CASCADE,
        related_name="sections_fees",
        default="other",
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    # ~~~~ Auto-filled ~~~~
    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        """Ensure the status exist befor saving."""
        FeeType.objects.get_or_create(code=self.fee_type_id)
        return super().save(*args, **kwargs)
