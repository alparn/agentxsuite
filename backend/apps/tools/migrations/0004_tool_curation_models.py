import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("connections", "0002_connection_transport_stdio_fields"),
        ("tools", "0003_add_connection_sync_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="tool",
            name="is_agent_visible",
            field=models.BooleanField(
                default=False,
                help_text="Whether this raw tool can be exposed directly to agents.",
            ),
        ),
        migrations.AddIndex(
            model_name="tool",
            index=models.Index(
                fields=["organization", "environment", "is_agent_visible"],
                name="tools_tool_organiz_966914_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="tool",
            index=models.Index(
                fields=["connection", "enabled"],
                name="tools_tool_connect_9f400b_idx",
            ),
        ),
        migrations.CreateModel(
            name="CuratedTool",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("display_name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("schema_json", models.JSONField(default=dict)),
                ("curator_type", models.CharField(max_length=100)),
                ("orchestration_config", models.JSONField(blank=True, default=dict)),
                ("enabled", models.BooleanField(default=True)),
                ("category", models.CharField(blank=True, max_length=100)),
                ("tags", models.JSONField(blank=True, default=list)),
                ("usage_count", models.PositiveIntegerField(default=0)),
                ("avg_execution_time_ms", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "connection",
                    models.ForeignKey(
                        help_text="Source MCP server connection for this curated tool.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="curated_tools",
                        to="connections.connection",
                    ),
                ),
                (
                    "environment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="curated_tools",
                        to="tenants.environment",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="curated_tools",
                        to="tenants.organization",
                    ),
                ),
            ],
            options={
                "db_table": "tools_curated_tool",
                "ordering": ["-created_at"],
                "unique_together": {("organization", "environment", "name")},
            },
        ),
        migrations.CreateModel(
            name="CurationMapping",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("execution_order", models.PositiveIntegerField(default=0)),
                ("parameter_mapping", models.JSONField(blank=True, default=dict)),
                ("condition", models.CharField(blank=True, max_length=255)),
                (
                    "curated_tool",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mappings",
                        to="tools.curatedtool",
                    ),
                ),
                (
                    "raw_tool",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="curation_mappings",
                        to="tools.tool",
                    ),
                ),
            ],
            options={
                "db_table": "tools_curation_mapping",
                "ordering": ["execution_order", "created_at"],
                "unique_together": {("curated_tool", "raw_tool", "execution_order")},
            },
        ),
        migrations.AddField(
            model_name="curatedtool",
            name="raw_tools",
            field=models.ManyToManyField(
                blank=True,
                related_name="curated_parents",
                through="tools.CurationMapping",
                to="tools.tool",
            ),
        ),
        migrations.AddIndex(
            model_name="curatedtool",
            index=models.Index(
                fields=["connection", "enabled"],
                name="tools_curat_connect_a884e7_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="curatedtool",
            index=models.Index(
                fields=["curator_type"],
                name="tools_curat_curator_381c75_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="curatedtool",
            index=models.Index(
                fields=["category"],
                name="tools_curat_categor_4352b2_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="curationmapping",
            index=models.Index(
                fields=["curated_tool", "execution_order"],
                name="tools_curat_curated_d4155e_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="curationmapping",
            index=models.Index(
                fields=["raw_tool"],
                name="tools_curat_raw_too_b57e1a_idx",
            ),
        ),
    ]
