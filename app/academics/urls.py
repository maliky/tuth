"""Academic app URLs."""

from django.urls import path

from app.academics import views

urlpatterns = [
    path("prereq/<slug:slug>/", views.prereq_graph_view, name="academics_prereq_graph"),
]
