from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("dashboard", "0003_outboundemail_html_body")]

    operations = [
        migrations.AddField(
            model_name="forecast",
            name="weather_generated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="forecast",
            name="weather_source",
            field=models.CharField(blank=True, max_length=80),
        ),
    ]
