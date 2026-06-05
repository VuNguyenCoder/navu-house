from django.db import migrations, models


def migrate_usage_status_new_to_unpaid(apps, schema_editor):
    Usage = apps.get_model('main', 'Usage')
    Usage.objects.filter(status='new').update(status='unpaid')


def migrate_usage_status_unpaid_to_new(apps, schema_editor):
    Usage = apps.get_model('main', 'Usage')
    Usage.objects.filter(status='unpaid').update(status='new')


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0021_usage_status'),
    ]

    operations = [
        migrations.RunPython(
            migrate_usage_status_new_to_unpaid,
            migrate_usage_status_unpaid_to_new,
        ),
        migrations.AlterField(
            model_name='usage',
            name='status',
            field=models.CharField(
                choices=[('unpaid', 'Unpaid'), ('paid', 'Paid')],
                default='unpaid',
                max_length=20,
            ),
        ),
    ]
