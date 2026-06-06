from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0022_usage_status_unpaid'),
    ]

    operations = [
        migrations.CreateModel(
            name='Settings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payment_period', models.PositiveSmallIntegerField(default=15, help_text='If today is before this day, the default billing month will be the previous month.', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(28)])),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Settings',
                'verbose_name_plural': 'Settings',
            },
        ),
    ]
