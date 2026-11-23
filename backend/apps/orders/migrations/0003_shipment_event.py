from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_alter_payment_status_refund"),
    ]

    operations = [
        migrations.AlterField(
            model_name="shipment",
            name="carrier",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.CreateModel(
            name="ShipmentEvent",
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
                ("status", models.CharField(max_length=20)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "shipment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="orders.shipment",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at", "id"],
            },
        ),
    ]
