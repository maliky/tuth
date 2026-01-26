"""Shared models for approvals and lookups."""

from typing import cast

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models

from app.registry.models.credit_hours import CreditHour
from app.shared.mixins import StatusHistory


class ApprovalQueue(models.Model):
    """Centralized approval queue used by Deans and VPAA."""

    REQUEST_TYPES = [
        ("curriculum_activation", "Curriculum activation"),
        ("overload_proposal", "Faculty overload proposal"),
        ("prerequisite_change", "Prerequisite change"),
        ("policy_update", "Academic policy update"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_review", "In review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    TARGET_ROLES = [
        ("dean", "Dean"),
        ("vpaa", "VPAA"),
        ("registrar", "Registrar"),
    ]

    request_type = models.CharField(max_length=50, choices=REQUEST_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    target_role = models.CharField(max_length=30, choices=TARGET_ROLES)
    payload = models.JSONField(default=dict, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="approvals_submitted",
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approvals_decided",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    related_content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True
    )
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey("related_content_type", "related_object_id")

    status_history = GenericRelation(
        StatusHistory, related_query_name="approvalqueue_entries"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.get_request_type_display()} → {self.get_target_role_display()}"

    def push_status(self, status: str, author=None) -> StatusHistory:
        """Append a status entry and update the current status."""
        self.status = status
        self.save(update_fields=["status", "updated_at"])
        history_entry = self.status_history.create(status=status, author=author)
        return cast(StatusHistory, history_entry)


__all__ = ["CreditHour", "ApprovalQueue"]
