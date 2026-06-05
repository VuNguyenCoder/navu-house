from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0016_room_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='room',
            name='type',
            field=models.CharField(choices=[('enclosed', 'Enclosed'), ('unenclosed', 'Unenclosed'), ('rest', 'Rest')], default='enclosed', max_length=20),
        ),
        migrations.AddField(
            model_name='room',
            name='shared_restroom',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.PROTECT, related_name='dependent_rooms', to='main.room'),
        ),
    ]
