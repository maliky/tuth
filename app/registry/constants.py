"""Constants used by the registry module."""

from app.registry.choices import StatusDocument, StatusRegistration


STATUS_CHOICES = list(
    set(list(StatusDocument.choices) + list(StatusRegistration.choices))
)
