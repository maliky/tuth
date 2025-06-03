"""Signals module."""

from django.db import transaction
from django.db.models import Max
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

from django.db.models import F

from app.timetable.models import Section, Reservation
from app.shared.constants import StatusReservation


@receiver(pre_save, sender=Section)
def autoincrement_section_number(sender, instance, **kwargs):
    "to increment section number"
    # but you skip the logic when ``instance.pk`` is truthy (evaluates to True).
    # That works for normal updates, however ``bulk_create`` bypasses signals
    # entirely. Consider using a database sequence to guarantee unique numbers
    # when inserting rows in bulk.
    if instance.pk or instance.number:

        return
    with transaction.atomic():
        last = (
            Section.objects.filter(course=instance.course, semester=instance.semester)
            .select_for_update()
            .aggregate(mx=Max("number"))
        )["mx"] or 0
        instance.number = last + 1


@receiver(post_save, sender=Reservation)
def increment_current_registration(sender, instance, created, **kwargs):
    """Increment ``current_registrations`` when a reservation is validated."""
    if instance.status != StatusReservation.VALIDATED:
        return
    with transaction.atomic():
        Section.objects.filter(pk=instance.section_id).update(
            current_registrations=F("current_registrations") + 1
        )


@receiver(post_delete, sender=Reservation)
def decrement_current_registration(sender, instance, **kwargs):
    """Decrement ``current_registrations`` when a reservation is removed."""
    if instance.status not in [StatusReservation.VALIDATED, StatusReservation.PAID]:
        return
    with transaction.atomic():
        Section.objects.filter(pk=instance.section_id).update(
            current_registrations=F("current_registrations") - 1
        )
