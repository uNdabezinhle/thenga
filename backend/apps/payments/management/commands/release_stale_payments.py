from django.core.management.base import BaseCommand

from apps.payments.tasks import release_stale_pending_payments


class Command(BaseCommand):
    help = "Cancel abandoned checkouts and release reserved stock"

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=2,
            help="Age threshold in hours (default 2)",
        )

    def handle(self, *args, **options):
        result = release_stale_pending_payments(hours=options["hours"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Cancelled {result['cancelled_orders']} orders, "
                f"released {result['released_units']} reserved units."
            )
        )
