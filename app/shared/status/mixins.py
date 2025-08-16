"""Mixins module."""

from typing import Any, Iterable, Optional, cast

from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models

from app.registry.constants import STATUS_CHOICES


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
    status = models.CharField(max_length=30, choices=STATUS_CHOICES)

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
    :class:StatusHistory entries (set_pending, set_approved …).  Your
    model is expected to declare a status field storing its current state.

    Example:
        >>> class MyModel(StatusableMixin, models.Model):
        ...     status = models.CharField(max_length=30, choices=STATUS_CHOICES)
        ...
        ...     class Meta:
        ...         app_label = "myapp"

        >>> obj = MyModel.objects.create()
        >>> obj.set_pending(author=None)
        >>> obj.current_status().status
        'pending'

    Side Effects:
        Creating a status entry may trigger post_save receivers tied to
        :class:StatusHistory.
    """

    status_history = GenericRelation(
        StatusHistory, related_query_name="%(app_label)s_%(class)s"
    )

    # ─── helpers ──────────────────────────────────────────────
    def _add_status(self, status: str, author: Optional[User]) -> StatusHistory:
        """Helper to append a new status entry."""
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

        Accept list of tuple or list of str
        Status should be a StatusMixin with code and label
        """
        # > this need to be handle without braking the whole code.
        # > maybe bubble up the error and catch it at the interface to prpose a fix, a messages
        # > proposing to go to the related model and add the status or check the entry.
        status_id = getattr(self, "status_id", None)
        allowed = {a.value if hasattr(a, "value") else a for a in allowed}

        if status_id not in allowed:
            raise ValidationError(
                f"Invalid state '{status_id}'. Allowed states: {', '.join(allowed)}."
            )

    class Meta:
        abstract = True
