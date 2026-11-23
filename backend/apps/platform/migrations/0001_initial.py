import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Merchant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(unique=True)),
                ("trading_name", models.CharField(max_length=120)),
                ("legal_name", models.CharField(blank=True, max_length=160)),
                ("vat_number", models.CharField(blank=True, max_length=32)),
                ("city", models.CharField(blank=True, max_length=120)),
                ("support_email", models.EmailField(blank=True, max_length=254)),
                ("package", models.CharField(max_length=32)),
                (
                    "status",
                    models.CharField(
                        choices=[("trialing", "Trialing"), ("active", "Active"), ("read_only", "Read only")],
                        default="trialing",
                        max_length=16,
                    ),
                ),
                ("trial_ends", models.DateTimeField(blank=True, null=True)),
                ("empty_catalogue_ok", models.BooleanField(default=False)),
                ("privacy_accepted", models.BooleanField(default=False)),
                (
                    "operated_ads",
                    models.BooleanField(
                        default=True,
                        help_text="Reka may place operated ads. The merchant cannot edit those creatives.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["trading_name"]},
        ),
        migrations.CreateModel(
            name="MerchantMembership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "role",
                    models.CharField(
                        choices=[("owner", "Owner"), ("staff", "Staff")],
                        default="staff",
                        max_length=16,
                    ),
                ),
                (
                    "merchant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="platform.merchant",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="merchant_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="merchantmembership",
            constraint=models.UniqueConstraint(fields=("merchant", "user"), name="platform_member_once"),
        ),
        migrations.CreateModel(
            name="MerchantAddOn",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=32)),
                (
                    "merchant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="addons",
                        to="platform.merchant",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="merchantaddon",
            constraint=models.UniqueConstraint(fields=("merchant", "code"), name="platform_addon_once"),
        ),
    ]
