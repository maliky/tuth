"""Mixins module."""

from typing import Any, Iterable, Optional, cast

from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models


class StatusHistory(models.Model):
    """Single entry in the status timeline of another model.

    Each row links back to the target object via a generic relation and is
    created whenever :class:StatusableMixin helpers are called.  Receivers of
    post_save may react to the addition of a status row.

    Example:
        >>> from app.shared.status.mixins import StatusHistory
        >>> StatusHistory.objects.create(
        ...     status="approved",
        ...     content_object=my_obj,
        ...     author=user,
        ... )
    """

    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="statuses_authored",
    )
    status = models.CharField(max_length=30)

    # --- generic link ---
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_obj = GenericForeignKey("content_type", "object_id")

    class Meta:  # keep the table reusable
        ordering = ["-created_at"]
        abstract = False


class StatusableMixin(models.Model):
    """Add a status audit trail to any model.

    Inherit from this mixin before the concrete model class.  It injects a
    status_history generic relation along with helpers that create
    :class:StatusHistory entries (set_pending, set_approved …).
    ! The model is expected to declare a status field storing its current state
     as a SimpleTableMixin

    Example:
        >>> class MyModel(StatusableMixin, models.Model):
        ...     status = models.ClearanceStatus(code="pending")
    """

    # > ! note this class may not be necessary with Simplehistory.  Needs testing.
    class Meta:
        abstract = True

    status_history = GenericRelation(
        StatusHistory, related_query_name="%(app_label)s_%(class)s"
    )

    # ─── helpers ──────────────────────────────────────────────
    def _add_status(self, status: str, author: Optional[User]) -> StatusHistory:
        """Helper to append a new status entry in the table StatusHistory."""
        return cast(
            StatusHistory, self.status_history.create(status=status, author=author)
        )

    def current_status(self) -> Optional[StatusHistory]:
        """Get the current status of the object."""
        return cast(Optional[StatusHistory], self.status_history.first())

    def set_pending(self, author: Optional[User]) -> StatusHistory:
        """Set the status to pending."""
        return self._add_status("pending", author)

    def set_revision(self, author: Optional[User]) -> StatusHistory:
        """Set the status to revisions."""
        return self._add_status("needs_revision", author)

    def set_approved(self, author: Optional[User]) -> StatusHistory:
        """Set the status to approved."""
        return self._add_status("approved", author)

    def set_rejected(self, author: Optional[User]) -> StatusHistory:
        """Set the status to rejected."""
        return self._add_status("rejected", author)

    def validate_status(self, allowed: Iterable[Any]) -> None:
        """Ensure self.status is an allowed one.

        To be overrident with allowed states
        Accept list of tuple or list of str
        Status should be a StatusMixin / SimpleTableMixin with code and label
        """
        # > maybe need to bubble up the error and catch it at the interface to propose a fix, a messages
        # > proposing to go to the related model and add the status or check the entry.

        # >! mandatory the subclass needs a status field
        # _allowed = {a.value if hasattr(a, "value") else a for a in allowed}

        if self.status not in allowed:
            raise ValidationError(
                f"Invalid state '{status}'. Allowed states: {', '.join(allowed)}."
            )

    def _get_status_id(self):
        """Return the status field of the subclass."""
        return getattr(self, "status_id", None)

    def _ensure_status(self):
        """Ensure we have a status field in the subclass."""
        if not self._get_status_id():
            raise ValidationError(f"A status field need to be declared for {self}")

    def save(self, *args, **kwargs):
        """Do some check before saving."""
        self._ensure_status()
        return super().save(*args, **kwargs)
