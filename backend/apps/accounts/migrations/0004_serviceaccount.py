"""
Migration for ServiceAccount model.
"""
import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_alter_user_managers"),
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceAccount",
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
                ("name", models.CharField(help_text="Human-readable name for the service account", max_length=255)),
                (
                    "audience",
                    models.CharField(
                        help_text="Expected audience (aud) claim in tokens. Must match MCP_CANONICAL_URI or resource parameter.",
                        max_length=512,
                    ),
                ),
                (
                    "issuer",
                    models.CharField(
                        help_text="Expected issuer (iss) claim in tokens. Must match one of the authorization servers.",
                        max_length=512,
                    ),
                ),
                (
                    "scope_allowlist",
                    models.JSONField(
                        default=list,
                        help_text="List of allowed scopes for this service account. Empty list means all scopes are allowed.",
                    ),
                ),
                ("enabled", models.BooleanField(default=True)),
                (
                    "environment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="service_accounts",
                        to="tenants.environment",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="service_accounts",
                        to="tenants.organization",
                    ),
                ),
            ],
            options={
                "db_table": "accounts_serviceaccount",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="serviceaccount",
            index=models.Index(fields=["organization", "environment", "enabled"], name="accounts_se_organiz_idx"),
        ),
        migrations.AddIndex(
            model_name="serviceaccount",
            index=models.Index(fields=["audience", "issuer"], name="accounts_se_audienc_idx"),
        ),
        migrations.AlterUniqueTogether(
            name="serviceaccount",
            unique_together={("organization", "name")},
        ),
    ]

