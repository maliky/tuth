from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models

from app.shared.constants import STATUS_CHOICES

from .utils import make_choices


class StatusHistory(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="statuses_authored",
    )
    state = models.CharField(max_length=30, choices=make_choices(STATUS_CHOICES))

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
    def _add_status(self, state: str, author):
        return self.status_history.create(state=state, author=author)

    def current_status(self):
        return self.status_history.first()

    def set_pending(self, author):
        return self._add_status("pending", author)

    def set_revision(self, author):
        return self._add_status("needs_revision", author)

    def set_approved(self, author):
        return self._add_status("approved", author)

    def set_rejected(self, author):
        return self._add_status("rejected", author)

    class Meta:
        abstract = True
