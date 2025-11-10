# Generated manually for security improvements

import uuid
from django.db import migrations, models
import django.db.models.deletion


def migrate_existing_tools(apps, schema_editor):
    """
    Migrate existing tools to have a connection.
    
    For existing tools without a connection, we try to find a connection
    in the same organization/environment. If none exists, we mark sync_status as 'failed'.
    """
    Tool = apps.get_model('tools', 'Tool')
    Connection = apps.get_model('connections', 'Connection')
    
    for tool in Tool.objects.filter(connection__isnull=True):
        # Try to find a connection in the same org/env
        connection = Connection.objects.filter(
            organization=tool.organization,
            environment=tool.environment
        ).first()
        
        if connection:
            tool.connection = connection
            tool.sync_status = 'stale'  # Mark as stale since we don't know sync status
        else:
            tool.sync_status = 'failed'  # No connection available
        
        tool.save(update_fields=['connection', 'sync_status'])


class Migration(migrations.Migration):

    dependencies = [
        ('tools', '0002_alter_tool_created_at_alter_tool_id'),
        ('connections', '0001_initial'),
    ]

    operations = [
        # Step 1: Add connection field as nullable
        migrations.AddField(
            model_name='tool',
            name='connection',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='tools',
                to='connections.connection',
                help_text='MCP server connection this tool belongs to',
            ),
        ),
        # Step 2: Add sync_status field
        migrations.AddField(
            model_name='tool',
            name='sync_status',
            field=models.CharField(
                max_length=20,
                choices=[('synced', 'Synced'), ('failed', 'Sync Failed'), ('stale', 'Stale')],
                default='synced',
                help_text='Status of the last sync operation',
            ),
        ),
        # Step 3: Add synced_at field
        migrations.AddField(
            model_name='tool',
            name='synced_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text='Timestamp of last successful sync',
            ),
        ),
        # Step 4: Migrate existing data
        migrations.RunPython(migrate_existing_tools, migrations.RunPython.noop),
        # Step 5: Make connection non-nullable
        migrations.AlterField(
            model_name='tool',
            name='connection',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='tools',
                to='connections.connection',
                help_text='MCP server connection this tool belongs to',
            ),
        ),
    ]

