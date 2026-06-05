from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0018_rename_shared_restroom_to_linked_restroom'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usage',
            name='tenant_count',
            field=models.PositiveIntegerField(blank=True, default=1, null=True),
        ),
        migrations.AlterField(
            model_name='usage',
            name='room_price',
            field=models.DecimalField(blank=True, decimal_places=0, default=0, max_digits=12, null=True),
        ),
        migrations.AlterField(
            model_name='usage',
            name='internet_price',
            field=models.DecimalField(blank=True, decimal_places=0, default=0, max_digits=12, null=True),
        ),
        migrations.AlterField(
            model_name='usage',
            name='cleaning_price',
            field=models.DecimalField(blank=True, decimal_places=0, default=0, max_digits=12, null=True),
        ),
        migrations.AlterField(
            model_name='usage',
            name='laundry_price',
            field=models.DecimalField(blank=True, decimal_places=0, default=0, max_digits=12, null=True),
        ),
    ]
