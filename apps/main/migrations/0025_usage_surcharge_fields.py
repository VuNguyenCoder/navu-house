from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0024_subscription_tenant_count'),
    ]

    operations = [
        migrations.AddField(
            model_name='usage',
            name='surcharge_amount',
            field=models.DecimalField(blank=True, decimal_places=0, default=0, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name='usage',
            name='surcharge_description',
            field=models.TextField(blank=True),
        ),
    ]
