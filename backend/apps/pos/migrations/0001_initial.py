import django.db.models.deletion
from decimal import Decimal

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("catalogue", "0004_sale_channel_barcode"),
        ("promotions", "0002_specials"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Store",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=32, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("sells_online", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="StoreStock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(default=0)),
                ("reserved_quantity", models.PositiveIntegerField(default=0)),
                (
                    "store",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stock", to="pos.store"),
                ),
                (
                    "variant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="store_stock",
                        to="catalogue.productvariant",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="storestock",
            constraint=models.UniqueConstraint(fields=("store", "variant"), name="pos_store_variant"),
        ),
        migrations.CreateModel(
            name="StoreCatalogItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("price_override", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                (
                    "bundle",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="store_catalog_items",
                        to="promotions.bundle",
                    ),
                ),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="catalog_items",
                        to="pos.store",
                    ),
                ),
                (
                    "variant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="store_catalog_items",
                        to="catalogue.productvariant",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="storecatalogitem",
            constraint=models.UniqueConstraint(
                condition=models.Q(variant__isnull=False),
                fields=("store", "variant"),
                name="pos_catalog_variant",
            ),
        ),
        migrations.AddConstraint(
            model_name="storecatalogitem",
            constraint=models.UniqueConstraint(
                condition=models.Q(bundle__isnull=False),
                fields=("store", "bundle"),
                name="pos_catalog_bundle",
            ),
        ),
        migrations.CreateModel(
            name="DrawerSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("opening_float", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                (
                    "status",
                    models.CharField(
                        choices=[("open", "Open"), ("closed", "Closed")],
                        default="open",
                        max_length=16,
                    ),
                ),
                ("closing_count", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("expected", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("opened_at", models.DateTimeField(auto_now_add=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "opened_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="drawers_opened",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="drawers",
                        to="pos.store",
                    ),
                ),
            ],
            options={"ordering": ["-opened_at"]},
        ),
    ]
