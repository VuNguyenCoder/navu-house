from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0002_room_subscription_usage'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscription',
            name='contact_email',
            field=models.EmailField(blank=True, max_length=254),
        ),
    ]
