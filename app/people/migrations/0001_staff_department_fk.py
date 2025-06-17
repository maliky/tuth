from django.db import migrations, models


def forwards(apps, schema_editor):
    Staff = apps.get_model("people", "Staff")
    Department = apps.get_model("academics", "Department")
    for name in Staff.objects.values_list("department", flat=True).distinct():
        if name:
            Department.objects.get_or_create(code=name, defaults={"full_name": name})
    for staff in Staff.objects.all():
        if staff.department:
            dept = Department.objects.get(code=staff.department)
            staff.department_fk = dept
            staff.save(update_fields=["department_fk"])


def backwards(apps, schema_editor):
    Staff = apps.get_model("people", "Staff")
    for staff in Staff.objects.all():
        if staff.department_fk_id:
            staff.department = staff.department_fk.code
            staff.save(update_fields=["department"])


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0001_create_department"),
    ]

    operations = [
        migrations.AddField(
            model_name="staff",
            name="department_fk",
            field=models.ForeignKey(
                to="academics.department",
                null=True,
                blank=True,
                on_delete=models.SET_NULL,
            ),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(model_name="staff", name="department"),
        migrations.RenameField(
            model_name="staff",
            old_name="department_fk",
            new_name="department",
        ),
    ]

