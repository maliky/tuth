"""Management command that set create the default status and states tables."""

from django.core.management.base import BaseCommand

from app.academics.models.curriculum import CurriStatus
from app.finance.fee_stack_defaults import ensure_dft_fee_stacks_from_fee_types
from app.finance.models.status_types_methods import (
    AccountChartType,
    AccountType,
    FeeType,
    InvoiceStatus,
    Payer,
    PaymentMethod,
    PaymentStatus,
)
from app.people.admin.resources import StdResource
from app.registry.models.document import DocStatus, DocType
from app.registry.models.grade import GradeValue
from app.registry.models.registration import RegistrationStatus
from app.registry.models import CreditHour
from app.timetable.models.semester import SemesterStatus


class Command(BaseCommand):
    """CLI helper available as manage.py create_states."""

    help = "Create default states/types for clearance, payment, fee, documents."

    # > what's this *_ and **__ ?
    def handle(self, *args, **kwargs) -> None:
        """Read YAML, validate, wipe current grants and recreate them."""
        CLASS_MAP = [
            ("AccountType", AccountType),  # before charttype
            ("AccountChartType", AccountChartType),
            ("PaymentStatus", PaymentStatus),
            ("InvoiceStatus", InvoiceStatus),
            ("CreditHour", CreditHour),
            ("CurriStatus", CurriStatus),
            ("DocStatus", DocStatus),
            ("DocType", DocType),
            ("FeeType", FeeType),
            ("Payer", Payer),
            ("PaymentMethod", PaymentMethod),
            ("RegistrationStatus", RegistrationStatus),
            ("SemesterStatus", SemesterStatus),
            ("CreditHour", CreditHour),
            ("GradeValue", GradeValue),
        ]

        for name, cls in CLASS_MAP:
            populate = getattr(cls, "_populate_attributes_and_db", None)
            if callable(populate):
                populate()
            self.stdout.write((f" - Defaults for {name} Created"))

        created_stack_count, created_line_count = ensure_dft_fee_stacks_from_fee_types()
        self.stdout.write(
            (
                " - Default fee stacks synced "
                f"({created_stack_count} created stack(s), "
                f"{created_line_count} created line(s))"
            )
        )

        self.stdout.write(self.style.SUCCESS("Defaults states and status Created"))
