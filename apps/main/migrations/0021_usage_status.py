from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0020_subscription_image_paths'),
    ]

    operations = [
        migrations.AddField(
            model_name='usage',
            name='status',
            field=models.CharField(
                choices=[('new', 'New'), ('paid', 'Paid')],
                default='new',
                max_length=20,
            ),
        ),
    ]
