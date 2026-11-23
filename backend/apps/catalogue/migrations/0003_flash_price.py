import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalogue", "0002_product_cooling_off_excluded"),
    ]

    operations = [
        migrations.CreateModel(
            name="FlashPrice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sale_price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("starts_at", models.DateTimeField(blank=True, null=True)),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flash_prices",
                        to="catalogue.product",
                    ),
                ),
            ],
            options={"ordering": ["-id"]},
        ),
    ]
