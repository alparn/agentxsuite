# Generated manually to clean up old tokens and make fields required

from django.db import migrations, models
import django.db.models.deletion


def delete_old_tokens(apps, schema_editor):
    """Delete tokens that don't have the new required fields."""
    IssuedToken = apps.get_model("agents", "IssuedToken")
    deleted_count = IssuedToken.objects.filter(
        models.Q(organization__isnull=True) |
        models.Q(environment__isnull=True) |
        models.Q(name__isnull=True) |
        models.Q(issued_to__isnull=True)
    ).delete()[0]
    if deleted_count > 0:
        print(f"Deleted {deleted_count} old token(s) without required fields")


class Migration(migrations.Migration):

    dependencies = [
        ("agents", "0008_add_user_token_fields"),
        ("accounts", "0007_remove_subject_unique"),
        ("tenants", "0003_organizationmembership"),
    ]

    operations = [
        # First: Delete old tokens that don't have the required fields
        migrations.RunPython(delete_old_tokens, reverse_code=migrations.RunPython.noop),
        
        # Then: Make fields NOT NULL
        migrations.AlterField(
            model_name="issuedtoken",
            name="environment",
            field=models.ForeignKey(
                help_text="Environment this token is valid for",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="issued_tokens",
                to="tenants.environment",
            ),
        ),
        migrations.AlterField(
            model_name="issuedtoken",
            name="issued_to",
            field=models.ForeignKey(
                help_text="User who created this token",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="my_issued_tokens",
                to="accounts.user",
            ),
        ),
        migrations.AlterField(
            model_name="issuedtoken",
            name="name",
            field=models.CharField(
                help_text="User-friendly name for this token (e.g., 'My Claude Desktop Token')",
                max_length=255,
            ),
        ),
        migrations.AlterField(
            model_name="issuedtoken",
            name="organization",
            field=models.ForeignKey(
                help_text="Organization this token belongs to",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="issued_tokens",
                to="tenants.organization",
            ),
        ),
    ]

