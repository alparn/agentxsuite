import django.db.models.deletion
from django.db import migrations, models


def sync_existing_registrations(apps, schema_editor):
    MCPServerRegistration = apps.get_model("mcp_ext", "MCPServerRegistration")
    Connection = apps.get_model("connections", "Connection")

    for registration in MCPServerRegistration.objects.filter(connection__isnull=True):
        if registration.server_type == "stdio":
            transport = "stdio"
        elif registration.server_type == "ws":
            transport = "sse"
        else:
            transport = "streamable_http"

        if registration.auth_method in {"none", "bearer", "basic"}:
            auth_method = registration.auth_method
        else:
            auth_method = "bearer" if registration.secret_ref else "none"

        metadata = registration.metadata if isinstance(registration.metadata, dict) else {}
        egress_allowlist = metadata.get("egress_allowlist") or []
        env_ref = metadata.get("env_ref")

        connection, _created = Connection.objects.update_or_create(
            organization_id=registration.organization_id,
            environment_id=registration.environment_id,
            name=registration.slug,
            defaults={
                "transport": transport,
                "endpoint": registration.endpoint or None,
                "command": registration.command,
                "args": registration.args or [],
                "env_ref": env_ref,
                "auth_method": auth_method,
                "secret_ref": registration.secret_ref or None,
                "egress_allowlist": egress_allowlist,
                "status": "unknown",
            },
        )
        registration.connection_id = connection.id
        registration.save(update_fields=["connection"])


class Migration(migrations.Migration):

    dependencies = [
        ("connections", "0003_connection_egress_allowlist"),
        ("mcp_ext", "0004_rename_mcp_ext_hu_full_na_idx_mcp_ext_hub_full_na_faf168_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="mcpserverregistration",
            name="connection",
            field=models.OneToOneField(
                blank=True,
                help_text="Canonical AgentxSuite connection backing this legacy registration.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="mcp_server_registration",
                to="connections.connection",
            ),
        ),
        migrations.RunPython(sync_existing_registrations, migrations.RunPython.noop),
    ]
