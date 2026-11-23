from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_shipment_event"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="discount_code",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="order",
            name="discount_settled",
            field=models.BooleanField(default=False),
        ),
    ]
