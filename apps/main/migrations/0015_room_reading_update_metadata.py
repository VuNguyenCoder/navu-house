from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0014_subscription_laundry_price_usage_laundry_price'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='room',
            name='latest_electricity_reading_source',
            field=models.CharField(blank=True, choices=[('manual', 'Manual update on Room details'), ('usage', 'Automatic update from subscription usage')], max_length=20),
        ),
        migrations.AddField(
            model_name='room',
            name='latest_electricity_reading_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='room',
            name='latest_electricity_reading_updated_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='room',
            name='latest_electricity_reading_usage',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='+', to='main.usage'),
        ),
        migrations.AddField(
            model_name='room',
            name='latest_water_reading_source',
            field=models.CharField(blank=True, choices=[('manual', 'Manual update on Room details'), ('usage', 'Automatic update from subscription usage')], max_length=20),
        ),
        migrations.AddField(
            model_name='room',
            name='latest_water_reading_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='room',
            name='latest_water_reading_updated_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='room',
            name='latest_water_reading_usage',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='+', to='main.usage'),
        ),
    ]
