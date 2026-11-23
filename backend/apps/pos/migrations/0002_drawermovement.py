import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0007_order_channel_store"),
        ("pos", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DrawerMovement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "kind",
                    models.CharField(
                        choices=[("sale", "Sale"), ("pay_in", "Pay in"), ("pay_out", "Pay out")],
                        max_length=16,
                    ),
                ),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "order",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="drawer_movements",
                        to="orders.order",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="movements",
                        to="pos.drawersession",
                    ),
                ),
            ],
            options={"ordering": ["id"]},
        ),
    ]
