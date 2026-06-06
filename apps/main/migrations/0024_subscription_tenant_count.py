from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0023_settings'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='tenant_count',
            field=models.PositiveIntegerField(default=1),
        ),
    ]
