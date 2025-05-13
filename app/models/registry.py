from __future__ import (
    annotations,
)  # to postpone evaluation of type hints

from django.db import models
from django.contrib.auth.models import User
from app.constants import REGISTRATION_STATUS_CHOICES
from app.models.utils import validate_model_status
from django.contrib.contenttypes.fields import GenericRelation
from app.app_utils import make_choices


# ─────────── Documents ─────────────────────────────
class Document(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.FileField(upload_to="documents/")
    document_type = models.CharField(max_length=50)
    status_history = GenericRelation("app.StatusHistory", related_query_name="document")

    def clean(self):
        super().clean()
        validate_model_status(self)


# ─────────── Registrations & Rosters ───────────────
class Registration(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    section = models.ForeignKey("app.Section", on_delete=models.CASCADE)
    status = models.CharField(
        max_length=30,
        choices=make_choices(REGISTRATION_STATUS_CHOICES),
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
