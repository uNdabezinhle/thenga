import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("platform", "0001_initial"),
        ("pos", "0002_drawermovement"),
    ]

    operations = [
        migrations.AddField(
            model_name="store",
            name="merchant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="stores",
                to="platform.merchant",
            ),
        ),
    ]
