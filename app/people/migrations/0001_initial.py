from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("student_id", models.CharField(max_length=20, unique=True)),
                ("date_of_birth", models.DateField(blank=True, null=True)),
                ("phone_number", models.CharField(blank=True, max_length=15)),
                ("address", models.TextField(blank=True)),
                ("email_number", models.CharField(blank=True, max_length=15)),
                ("enrollment_year", models.PositiveSmallIntegerField()),
                ("bio", models.TextField(blank=True)),
                ("photo", models.ImageField(blank=True, null=True, upload_to="student_photos/")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("college", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to="academics.college")),
                ("curriculum", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to="academics.curriculum")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to="auth.user")),
            ],
            options={
                "ordering": ["user__last_name", "user__first_name"],
            },
        ),
        migrations.CreateModel(
            name="RoleAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(max_length=30)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField(blank=True, null=True)),
                ("college", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="role_assignments", to="academics.college")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="role_assignments", to="auth.user")),
            ],
            options={},
        ),
        migrations.CreateModel(
            name="InstructorProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("employment_date", models.DateField(blank=True, null=True)),
                ("department", models.CharField(blank=True, max_length=100)),
                ("status", models.CharField(blank=True, max_length=20)),
                ("bio", models.TextField(blank=True)),
                ("photo", models.ImageField(blank=True, null=True, upload_to="instructor_photos/")),
                ("personal_page", models.URLField(blank=True)),
                ("google_profile", models.URLField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("college", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="academics.college")),
                ("courses", models.ManyToManyField(blank=True, related_name="instructors", to="academics.course")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to="auth.user")),
            ],
            options={
                "ordering": ["user__last_name", "user__first_name"],
            },
        ),
        migrations.AddConstraint(
            model_name="roleassignment",
            constraint=models.UniqueConstraint(fields=("user", "role", "college", "start_date"), name="unique_role_per_period"),
        ),
        migrations.AddIndex(
            model_name="roleassignment",
            index=models.Index(fields=["role", "college", "end_date"], name="people_roleassignment_role_979956_idx"),
        ),
    ]
