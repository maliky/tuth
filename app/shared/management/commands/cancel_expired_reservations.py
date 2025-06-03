from django.core.management.base import BaseCommand
from app.timetable.tasks import cancel_expired_reservations

class Command(BaseCommand):
    help = "Cancel expired reservations and adjust seat counts."

    def handle(self, *args, **options):
        cancel_expired_reservations()
        self.stdout.write(self.style.SUCCESS('Expired reservations cancelled.'))
