from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Room',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('room_number', models.CharField(max_length=50, unique=True)),
                ('floor_number', models.PositiveIntegerField()),
                ('description', models.TextField(blank=True)),
                ('image_paths', models.JSONField(blank=True, default=list)),
                ('latest_electricity_reading', models.PositiveIntegerField(default=0)),
                ('latest_water_reading', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['floor_number', 'room_number'],
            },
        ),
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('enabled', 'Enabled'), ('disabled', 'Disabled')], default='enabled', max_length=20)),
                ('start_date', models.DateField()),
                ('tenant_count', models.PositiveIntegerField(default=1)),
                ('room_price', models.DecimalField(decimal_places=0, default=0, max_digits=12)),
                ('electricity_price', models.DecimalField(decimal_places=0, default=0, max_digits=12)),
                ('water_price', models.DecimalField(decimal_places=0, default=0, max_digits=12)),
                ('internet_price', models.DecimalField(decimal_places=0, default=0, max_digits=12)),
                ('cleaning_price', models.DecimalField(decimal_places=0, default=0, max_digits=12)),
                ('contact_email', models.EmailField(max_length=254)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('room', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='subscriptions', to='main.room')),
            ],
            options={
                'ordering': ['-start_date', 'room__room_number'],
            },
        ),
        migrations.CreateModel(
            name='Usage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('period', models.DateField()),
                ('tenant_count', models.PositiveIntegerField(default=1)),
                ('room_price', models.DecimalField(decimal_places=0, default=0, max_digits=12)),
                ('electricity_price', models.DecimalField(decimal_places=0, default=0, max_digits=12)),
                ('water_price', models.DecimalField(decimal_places=0, default=0, max_digits=12)),
                ('internet_price', models.DecimalField(decimal_places=0, default=0, max_digits=12)),
                ('cleaning_price', models.DecimalField(decimal_places=0, default=0, max_digits=12)),
                ('latest_electricity_reading', models.PositiveIntegerField(default=0)),
                ('electricity_meter_image_path', models.CharField(blank=True, max_length=500)),
                ('latest_water_reading', models.PositiveIntegerField(default=0)),
                ('water_meter_image_path', models.CharField(blank=True, max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('subscription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='usages', to='main.subscription')),
            ],
            options={
                'ordering': ['-period', 'subscription__room__room_number'],
                'constraints': [
                    models.UniqueConstraint(fields=('subscription', 'period'), name='unique_subscription_usage_period'),
                ],
            },
        ),
    ]
