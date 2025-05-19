# app/models/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver

from app.models.academics import Curriculum
from app.models.mixins import StatusHistory
from app.constants import APPROVED


@receiver(post_save, sender=StatusHistory)
def sync_curriculum_is_active(sender, instance, **kwargs):
    """
    Whenever a StatusHistory row is added/edited,
    update Curriculum.is_active if the target object is a Curriculum.
    """
    target = instance.content_obj
    if not isinstance(target, Curriculum):
        return

    # fetch the latest status (could be the row just saved or another)
    latest = target.status_history.order_by("-created_at").first()
    should_be_active = latest and latest.state == APPROVED

    # update only when a change is needed to avoid recursive saves
    if target.is_active != should_be_active:
        target.is_active = should_be_active
        target.save(update_fields=["is_active"])


@receiver(pre_save, sender=Section)
def autoincrement_section_number(sender, instance, **kwargs):
    "to increment section number"
    if instance.pk or instance.number:
        return
    with transaction.atomic():
        last = (
            Section.objects.filter(course=instance.course, semester=instance.semester)
            .select_for_update()
            .aggregate(mx=Max("number"))
        )["mx"] or 0
        instance.number = last + 1
