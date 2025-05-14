# app/resources.p
from import_export import resources, fields, widgets
from app.models.academics import Course


class CourseResource(resources.ModelResource):
    prerequisites = fields.Field(
        column_name="prerequisites",  # header in the CSV / Excel file
        attribute="prerequisites",  # the M2M manager on Course
        widget=widgets.ManyToManyWidget(
            Course,  # model being related to
            field="code",  # unique text used in the file
            separator=";",  # how multiple values are split
        ),
    )

    class Meta:
        model = Course
        import_id_fields = ("code",)  # treat course.code as the PK when importing
        exclude = ("description",)  # keep long text out of flat files
