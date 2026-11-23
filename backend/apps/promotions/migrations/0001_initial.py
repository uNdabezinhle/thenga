import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("orders", "0004_order_discount_code"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ShopAd",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=120)),
                ("body", models.CharField(blank=True, max_length=255)),
                (
                    "placement",
                    models.CharField(
                        choices=[("shop_top", "Shop top")],
                        default="shop_top",
                        max_length=32,
                    ),
                ),
                ("product_slug", models.CharField(blank=True, max_length=160)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
            ],
            options={"ordering": ["sort_order", "id"]},
        ),
        migrations.CreateModel(
            name="Voucher",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("code", models.CharField(max_length=64, unique=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                (
                    "remaining_amount",
                    models.DecimalField(decimal_places=2, max_digits=12),
                ),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="vouchers",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "redeemed_order",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="redeemed_vouchers",
                        to="orders.order",
                    ),
                ),
            ],
            options={"ordering": ["code"]},
        ),
    ]
