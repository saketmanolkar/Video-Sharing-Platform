from django.db import migrations, models
import uuid

def gen_uuid(apps, schema_editor):
    Follow = apps.get_model('users', 'Follow')
    for row in Follow.objects.all():
        row.temp_uuid = uuid.uuid4()
        row.save(update_fields=['temp_uuid'])

class Migration(migrations.Migration):
    dependencies = [
        ('users', '0005_alter_follow_id'),  # Replace with your last migration
    ]

    operations = [
        # 1. Add temporary UUID field
        migrations.AddField(
            model_name='follow',
            name='temp_uuid',
            field=models.UUIDField(null=True),
        ),
        # 2. Generate UUIDs for existing records
        migrations.RunPython(gen_uuid),
        # 3. Remove null and make it primary
        migrations.AlterField(
            model_name='follow',
            name='temp_uuid',
            field=models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False),
        ),
        # 4. Remove old AutoField id
        migrations.RemoveField(
            model_name='follow',
            name='id',
        ),
        # 5. Rename temp_uuid to id
        migrations.RenameField(
            model_name='follow',
            old_name='temp_uuid',
            new_name='id',
        ),
    ]