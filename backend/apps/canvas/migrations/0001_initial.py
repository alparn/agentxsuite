"""
Initial migration for canvas app.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CanvasState",
            fields=[
                ("id", models.UUIDField(primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "name",
                    models.CharField(
                        default="default",
                        help_text="Canvas name (e.g., 'default', 'production', 'staging')",
                        max_length=255,
                    ),
                ),
                (
                    "state_json",
                    models.JSONField(
                        default=dict,
                        help_text="Canvas state including nodes, edges, viewport, and groups",
                    ),
                ),
                (
                    "environment",
                    models.ForeignKey(
                        blank=True,
                        help_text="Optional: Canvas state for specific environment",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="canvas_states",
                        to="tenants.environment",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="canvas_states",
                        to="tenants.organization",
                    ),
                ),
            ],
            options={
                "db_table": "canvas_canvasstate",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.AddIndex(
            model_name="canvasstate",
            index=models.Index(
                fields=["organization", "environment", "name"],
                name="canvas_canv_organiz_idx",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="canvasstate",
            unique_together={("organization", "environment", "name")},
        ),
    ]

