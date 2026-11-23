from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalogue", "0003_flash_price"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="sale_channel",
            field=models.CharField(
                choices=[("both", "Both"), ("online", "Online"), ("pos", "Point of sale")],
                default="both",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="productvariant",
            name="barcode",
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
    ]
