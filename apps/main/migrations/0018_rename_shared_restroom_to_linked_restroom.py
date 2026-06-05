from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0017_room_shared_restroom_and_unenclosed'),
    ]

    operations = [
        migrations.RenameField(
            model_name='room',
            old_name='shared_restroom',
            new_name='linked_restroom',
        ),
    ]
