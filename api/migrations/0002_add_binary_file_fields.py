from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="researchsession",
            name="pdf_bytes",
            field=models.BinaryField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="researchsession",
            name="audio_bytes",
            field=models.BinaryField(blank=True, null=True),
        ),
    ]
