from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0026_usage_optional_internet_laundry'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='use_internet',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='subscription',
            name='use_laundry',
            field=models.BooleanField(default=True),
        ),
    ]
