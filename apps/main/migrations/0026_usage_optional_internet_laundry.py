from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0025_usage_surcharge_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='usage',
            name='use_internet',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='usage',
            name='use_laundry',
            field=models.BooleanField(default=True),
        ),
    ]
