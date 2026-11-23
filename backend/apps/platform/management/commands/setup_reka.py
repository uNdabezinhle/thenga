"""Create the first merchant on an empty server. Does not load Northbound."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import EmailVerificationToken
from apps.notifications.services import notify_email_verification
from apps.platform.models import Merchant
from apps.platform.services import open_merchant


class Command(BaseCommand):
    help = "Open one merchant shop. Pass --demo only when you want the Northbound sample."

    def add_arguments(self, parser):
        parser.add_argument("--trading-name", default="")
        parser.add_argument("--owner-email", default="")
        parser.add_argument("--password", default="")
        parser.add_argument("--package", default="shop_till")
        parser.add_argument("--city", default="")
        parser.add_argument("--demo", action="store_true")
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        if options["demo"]:
            from django.core.management import call_command

            call_command("seed_northbound")
            self.stdout.write("Loaded the Northbound sample catalogue.")
            return

        if Merchant.objects.exists() and not options["force"]:
            raise CommandError("A merchant already exists. Pass --force to add another, or --demo for the sample.")

        trading = options["trading_name"].strip()
        email = options["owner_email"].strip().lower()
        password = options["password"]
        if len(trading) < 2 or "@" not in email or len(password) < 8:
            raise CommandError(
                "Pass --trading-name, --owner-email, and --password (8 or more characters)."
            )

        User = get_user_model()
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            username = email.split("@", 1)[0][:30] or "owner"
            base = username
            suffix = 2
            while User.objects.filter(username=username).exists():
                username = f"{base[:24]}{suffix}"
                suffix += 1
            user = User.objects.create_user(
                email=email,
                username=username,
                password=password,
                email_verified=False,
            )
            token = EmailVerificationToken.create_for(user)
            notify_email_verification(user, token.token)

        merchant = open_merchant(
            user=user,
            payload={
                "trading_name": trading,
                "package": options["package"],
                "city": options["city"],
                "privacy_accepted": True,
                "empty_catalogue_ok": True,
                "addons": [],
            },
        )
        self.stdout.write(f"Opened {merchant.trading_name} at /api/v1/products/?merchant={merchant.slug}")
