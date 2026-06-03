from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("connections", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="connection",
            name="transport",
            field=models.CharField(
                choices=[
                    ("stdio", "stdio"),
                    ("streamable_http", "Streamable HTTP"),
                    ("sse", "SSE"),
                    ("legacy_http", "Legacy HTTP"),
                ],
                db_index=True,
                default="legacy_http",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="connection",
            name="endpoint",
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name="connection",
            name="command",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="connection",
            name="args",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="connection",
            name="env_ref",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
