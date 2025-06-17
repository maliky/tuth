from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Department",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, unique=True)),
                ("full_name", models.CharField(blank=True, max_length=128)),
                (
                    "college",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.PROTECT,
                        related_name="departments",
                        to="academics.college",
                    ),
                ),
            ],
            options={"ordering": ["code"]},
        ),
    ]
