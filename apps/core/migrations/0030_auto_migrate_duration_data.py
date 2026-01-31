from django.db import migrations
from django.db.models import F

def migrate_duration_data(apps, schema_editor):
    Service = apps.get_model('core', 'Service')
    # Update duration_value with the value from duration_minutes
    # This assumes duration_minutes holds the correct historical 'minutes' value
    # and we want that to be the initial 'value' for the 'minutes' type (default)
    Service.objects.all().update(duration_value=F('duration_minutes'))

def reverse_migrate_data(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0029_service_duration_type_service_duration_value_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_duration_data, reverse_migrate_data),
    ]
