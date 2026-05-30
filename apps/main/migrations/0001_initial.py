from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='PriceTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='Bang gia chung', max_length=100, unique=True)),
                ('room_price', models.DecimalField(decimal_places=0, default=2000000, max_digits=12)),
                ('electricity_price', models.DecimalField(decimal_places=0, default=4500, max_digits=12)),
                ('water_price', models.DecimalField(decimal_places=0, default=40000, max_digits=12)),
                ('internet_price', models.DecimalField(decimal_places=0, default=60000, max_digits=12)),
                ('cleaning_price', models.DecimalField(decimal_places=0, default=30000, max_digits=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
    ]
