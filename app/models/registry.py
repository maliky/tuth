from __future__ import (
    annotations,
)  # to postpone evaluation of type hints

from django.db import models
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


# ─────────── Registrations & Rosters ───────────────
class Registration(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    section = models.ForeignKey("app.Section", on_delete=models.CASCADE)
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
    section = models.OneToOneField("app.Section", on_delete=models.CASCADE)
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
