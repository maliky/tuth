"""Management command that set create the default status and states tables."""

from app.academics.models.curriculum import CurriculumStatus
from app.finance.models.payment import ClearanceStatus, FeeType, PaymentMethod
from app.registry.models.document import DocumentStatus, DocumentType
from app.registry.models.registration import RegistrationStatus
from app.shared.models import CreditHour
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """CLI helper available as manage.py create_states."""

    help = "Create default states/types for clearance, payment, fee, documents."

    # > what's this *_ and **__ ?
    def handle(self, *args, **kwargs) -> None:
        """Read YAML, validate, wipe current grants and recreate them."""
        CLASS_MAP = [
            ("DocumentStatus", DocumentStatus),
            ("ClearanceStatus", ClearanceStatus),
            ("CurriculumStatus", CurriculumStatus),
            ("RegistrationStatus", RegistrationStatus),
            ("DocumentType", DocumentType),
            ("PaymentMethod", PaymentMethod),
            ("FeeType", FeeType),
        ]

        for name, cls in CLASS_MAP:
            cls()._populate_attributes_and_db()
            self.stdout.write((f" - Defaults for {name} Created"))

        CreditHour._populate_attributes_and_db()

        self.stdout.write(self.style.SUCCESS("Defaults states and status Created"))
