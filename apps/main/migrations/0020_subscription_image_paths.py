from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0019_usage_restroom_optional_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='image_paths',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
