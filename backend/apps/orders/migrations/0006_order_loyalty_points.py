from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0005_shipping_rate"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="loyalty_points",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="order",
            name="specials_awarded",
            field=models.BooleanField(default=False),
        ),
    ]
