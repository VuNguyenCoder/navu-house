from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0015_room_reading_update_metadata'),
    ]

    operations = [
        migrations.AddField(
            model_name='room',
            name='type',
            field=models.CharField(choices=[('enclosed', 'Enclosed'), ('rest', 'Rest')], default='enclosed', max_length=20),
        ),
    ]
