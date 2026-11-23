import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalogue", "0003_flash_price"),
        ("orders", "0005_shipping_rate"),
        ("promotions", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Bundle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=120, unique=True)),
                ("price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["title"]},
        ),
        migrations.CreateModel(
            name="BundleItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveSmallIntegerField(default=1)),
                (
                    "bundle",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="promotions.bundle",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bundle_items",
                        to="catalogue.product",
                    ),
                ),
                (
                    "variant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bundle_items",
                        to="catalogue.productvariant",
                    ),
                ),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="LoyaltyAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("points", models.PositiveIntegerField(default=0)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="loyalty",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ReferralProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=16, unique=True)),
                ("settled", models.BooleanField(default=False)),
                ("referrer_points", models.PositiveIntegerField(default=0)),
                (
                    "referrer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="referred_customers",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "reward_voucher",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="referral_rewards",
                        to="promotions.voucher",
                    ),
                ),
                (
                    "rewarded_order",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="referral_rewards",
                        to="orders.order",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="referral",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
