import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0006_order_loyalty_points"),
        ("pos", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="channel",
            field=models.CharField(
                choices=[("online", "Online"), ("pos", "Point of sale")],
                db_index=True,
                default="online",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="store",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="orders",
                to="pos.store",
            ),
        ),
    ]
