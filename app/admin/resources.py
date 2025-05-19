# app/admin/resources.py
from import_export import resources, fields, widgets
from app.models import Course, Curriculum, Building, Room, Prerequisite, Section
from app.admin.widgets import BuildingWidget


class CurriculumResource(resources.ModelResource):
    class Meta:
        model = Curriculum
        fields = (
            "id",
            "title",
            "level",
            "academic_year",
            "college__code",
            "is_active",
        )


class CourseResource(resources.ModelResource):
    prerequisites = fields.Field(
        column_name="prerequisites",
        attribute="prerequisites",
        widget=widgets.ManyToManyWidget(Course, field="code", separator=";"),
    )

    class Meta:
        model = Course
        import_id_fields = ("code",)
        exclude = ("description",)


class BuildingResource(resources.ModelResource):
    class Meta:
        model = Building
        import_id_fields = ("short_name",)


class RoomResource(resources.ModelResource):
    building = fields.Field(
        column_name="building",
        attribute="building",
        widget=BuildingWidget("building", "short_name"),
    )

    class Meta:
        model = Room
        import_id_fields = ("name", "building")
        fields = ("name", "building")


class PrerequisiteResource(resources.ModelResource):
    class Meta:
        model = Prerequisite
        import_id_fields = ("course", "prerequisite_course")


class SectionResource(resources.ModelResource):
    class Meta:
        model = Section
        import_id_fields = ("course", "semester", "number")
