# Generated manually

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mcp_ext', '0002_mcpserverregistration'),
    ]

    operations = [
        migrations.CreateModel(
            name='MCPHubServer',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('github_id', models.BigIntegerField(help_text='GitHub repository ID', unique=True)),
                ('full_name', models.CharField(help_text="GitHub repository full name (e.g., 'modelcontextprotocol/server-github')", max_length=255, unique=True)),
                ('name', models.CharField(help_text='Repository name', max_length=255)),
                ('description', models.TextField(blank=True, help_text='Repository description')),
                ('html_url', models.URLField(help_text='GitHub repository URL', max_length=500)),
                ('stargazers_count', models.IntegerField(default=0, help_text='Number of stars')),
                ('forks_count', models.IntegerField(default=0, help_text='Number of forks')),
                ('language', models.CharField(blank=True, help_text='Primary programming language', max_length=100)),
                ('topics', models.JSONField(default=list, help_text='GitHub topics/tags')),
                ('owner_login', models.CharField(help_text='GitHub owner username', max_length=255)),
                ('owner_avatar_url', models.URLField(blank=True, help_text='Owner avatar URL', max_length=500)),
                ('updated_at_github', models.DateTimeField(help_text='Last update time from GitHub')),
                ('last_synced_at', models.DateTimeField(blank=True, help_text='Last time we synced data from GitHub', null=True)),
                ('is_active', models.BooleanField(default=True, help_text='Whether this server is still active/available')),
            ],
            options={
                'db_table': 'mcp_ext_hub_server',
                'ordering': ['-stargazers_count', '-updated_at_github'],
            },
        ),
        migrations.AddIndex(
            model_name='mcphubserver',
            index=models.Index(fields=['full_name'], name='mcp_ext_hu_full_na_idx'),
        ),
        migrations.AddIndex(
            model_name='mcphubserver',
            index=models.Index(fields=['language'], name='mcp_ext_hu_languag_idx'),
        ),
        migrations.AddIndex(
            model_name='mcphubserver',
            index=models.Index(fields=['stargazers_count'], name='mcp_ext_hu_stargaz_idx'),
        ),
        migrations.AddIndex(
            model_name='mcphubserver',
            index=models.Index(fields=['is_active', '-stargazers_count'], name='mcp_ext_hu_is_acti_idx'),
        ),
    ]

