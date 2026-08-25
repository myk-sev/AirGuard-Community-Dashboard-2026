from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("dashboard", "0002_inboundmessage_providerevent_suppression_and_more")]

    operations = [
        migrations.AddField(
            model_name="outboundemail",
            name="html_body",
            field=models.TextField(blank=True),
        ),
    ]
