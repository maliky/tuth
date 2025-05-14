# app/resources.p
from import_export import resources, fields, widgets
from app.models.academics import Course, Prerequisite


class CourseResource(resources.ModelResource):
    prerequisites = fields.Field(
        column_name="prerequisites",
        attribute="prerequisites",  # the manager on Course
        widget=widgets.ManyToManyWidget(
            Course,  
            field="code",  
            separator=";",  
        ),
    )

    class Meta:
        model = Course
        import_id_fields = ("code",)
        exclude = ("description",)  # keep your previous exclusion
