"""Mixins module."""

from typing import Any, Iterable
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from typing import Optional

from app.shared.constants import STATUS_CHOICES


class StatusHistory(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="statuses_authored",
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES)

    # --- generic link ---
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_obj = GenericForeignKey("content_type", "object_id")

    class Meta:  # keep the table reusable
        ordering = ["-created_at"]
        abstract = False


class StatusableMixin(models.Model):
    """
    Plug-and-play: inherit *before* concrete model.
    Adds `status_history` + helper methods.
    """

    status_history = GenericRelation(
        StatusHistory, related_query_name="%(app_label)s_%(class)s"
    )

    # ─── helpers ──────────────────────────────────────────────
    def _add_status(self, state: str, author: Optional[User]) -> StatusHistory:
        """Helper to append a new status entry."""
        return self.status_history.create(state=state, author=author)

    def current_status(self) -> Optional[StatusHistory]:
        return self.status_history.first()

    def set_pending(self, author: Optional[User]) -> StatusHistory:
        return self._add_status("pending", author)

    def set_revision(self, author: Optional[User]) -> StatusHistory:
        return self._add_status("needs_revision", author)

    def set_approved(self, author: Optional[User]) -> StatusHistory:
        return self._add_status("approved", author)

    def set_rejected(self, author: Optional[User]) -> StatusHistory:
        return self._add_status("rejected", author)

    def validate_status(self, allowed: Iterable[Any]) -> None:
        """
        Ensure ``self.status`` is one of ``allowed``.
        accept list of tuple or list of str
        """

        status = getattr(self, "status", None)
        allowed = {a.value if hasattr(a, "value") else a for a in allowed}

        if status not in allowed:
            raise ValidationError(
                f"Invalid state '{status}'. Allowed states: {', '.join(allowed)}."
            )

    class Meta:
        abstract = True
