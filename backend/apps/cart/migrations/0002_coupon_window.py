from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cart", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="coupon",
            name="title",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="coupon",
            name="description",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="coupon",
            name="starts_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="coupon",
            name="ends_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
