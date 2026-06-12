from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("shipping_service", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="shipment",
            name="shipping_method",
            field=models.CharField(
                choices=[
                    ("standard", "Standard"),
                    ("express", "Express"),
                    ("same_day", "Same day"),
                ],
                default="standard",
                max_length=50,
            ),
        ),
    ]
