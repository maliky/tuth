from __future__ import annotations

from app.shared.mixins import StatusableMixin
from django.contrib.auth.models import User
from django.db import models


# need to do this extensively and for other profils when import tests ok
class StudentProfile(StatusableMixin, models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    student_id = models.CharField(max_length=20, unique=True)
    date_of_birth = models.DateField(null=True, blank=True)

    # Contact Information
    phone_number = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    email_number = models.CharField(max_length=15, blank=True)

    # Academic Information
    college = models.ForeignKey("academics.College", on_delete=models.SET_NULL, null=True)
    curriculum = models.ForeignKey(
        "academics.Curriculum", on_delete=models.SET_NULL, null=True
    )
    enrollment_year = models.PositiveSmallIntegerField()
    enrollment_date = models.DateField(null=True, blank=True)

    # Optional: additional personal information
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to="student_photos/", null=True, blank=True)

    # Automatic timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.student_id})"

    class Meta:
        ordering = ["user__last_name", "user__first_name"]
