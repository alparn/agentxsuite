from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("connections", "0002_connection_transport_stdio_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="connection",
            name="egress_allowlist",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Allowed outbound hostnames, wildcard host patterns, or CIDR ranges for HTTP MCP transports.",
            ),
        ),
    ]
