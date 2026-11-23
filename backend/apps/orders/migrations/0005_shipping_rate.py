from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0004_order_discount_code"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShippingRate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("method_name", models.CharField(max_length=64, unique=True)),
                ("price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("estimated_days", models.CharField(max_length=64)),
                ("sort_order", models.PositiveIntegerField(default=0)),
            ],
            options={
                "ordering": ["sort_order", "id"],
            },
        ),
    ]
