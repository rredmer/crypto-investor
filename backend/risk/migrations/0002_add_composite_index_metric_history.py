from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("risk", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="riskmetrichistory",
            index=models.Index(
                fields=["portfolio_id", "recorded_at"],
                name="idx_risk_metric_portfolio_time",
            ),
        ),
    ]
