from django.db import models
from app.models.timed import Section
from django.contrib.auth.models import User


# ─────────── Documents ─────────────────────────────
class Document(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.FileField(upload_to="documents/")
    document_type = models.CharField(max_length=50)
    upload_date = models.DateTimeField(auto_now_add=True)
    verification_status = models.CharField(
        max_length=50,
        choices=[
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="pending",
    )


# ─────────── Finance ───────────────────────────────
class FinancialRecord(models.Model):
    student = models.OneToOneField(User, on_delete=models.CASCADE)
    total_due = models.DecimalField(max_digits=10, decimal_places=2)
    total_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    clearance_status = models.CharField(
        max_length=50,
        choices=[
            ("pending", "Pending"),
            ("cleared", "Cleared"),
            ("blocked", "Blocked"),
        ],
        default="pending",
    )
    last_updated = models.DateTimeField(auto_now=True)
    verified_by = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name="financial_records_verified",
    )


class PaymentHistory(models.Model):
    financial_record = models.ForeignKey(
        FinancialRecord, related_name="payments", on_delete=models.CASCADE
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    method = models.CharField(max_length=50, blank=True)  # cash, bank, mobile …
    recorded_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="payments_recorded"
    )


# ─────────── Registrations & Rosters ───────────────
class Registration(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=30,
        choices=[
            ("pre_registered", "Pre-registered"),
            ("confirmed", "Confirmed"),
            ("pending_clearance", "Pending Clearance"),
        ],
        default="pre_registered",
    )
    date_registered = models.DateTimeField(auto_now_add=True)
    date_pre_registered = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "section"],
                name="uniq_registration_student_section",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.student} – {self.section} -  {self.status}"


class ClassRoster(models.Model):
    section = models.OneToOneField(Section, on_delete=models.CASCADE)
    updated_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="rosters_updated"
    )
    last_updated = models.DateTimeField(auto_now=True)

    @property
    def students(self):
        """Return all users registered to this section."""
        return User.objects.filter(
            registration__section=self.section
        )  # or self.section.registration_set
