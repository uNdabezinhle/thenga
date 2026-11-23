import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cart", "0002_coupon_window"),
        ("promotions", "0002_specials"),
    ]

    operations = [
        migrations.AddField(
            model_name="cartitem",
            name="bundle",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="cart_items",
                to="promotions.bundle",
            ),
        ),
    ]
