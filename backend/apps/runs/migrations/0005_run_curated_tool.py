import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tools", "0004_tool_curation_models"),
        ("runs", "0004_modelpricing_run_cost_currency_run_cost_input_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="run",
            name="tool",
            field=models.ForeignKey(
                blank=True,
                help_text="Tool instance",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="runs",
                to="tools.tool",
            ),
        ),
        migrations.AddField(
            model_name="run",
            name="curated_tool",
            field=models.ForeignKey(
                blank=True,
                help_text="Curated tool instance, when this run was agent-facing curation.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="runs",
                to="tools.curatedtool",
            ),
        ),
        migrations.AddIndex(
            model_name="run",
            index=models.Index(
                fields=["curated_tool", "created_at"],
                name="runs_run_curated_9d30c1_idx",
            ),
        ),
    ]

