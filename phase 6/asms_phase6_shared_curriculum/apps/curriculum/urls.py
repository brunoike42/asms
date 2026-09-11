"""
Mount at /api/v1/curriculum/ in your root urlconf:

    path("api/v1/curriculum/", include("apps.curriculum.urls")),
"""
from django.urls import path

from . import views

app_name = "curriculum"

urlpatterns = [
    path("resources/", views.CurriculumResourceListView.as_view(), name="resource-list"),
    path("resources/<int:resource_pk>/publish/", views.CurriculumResourcePublishView.as_view(), name="resource-publish"),
    path(
        "resources/<int:resource_pk>/adoptions/",
        views.CurriculumResourceAdoptionsView.as_view(),
        name="resource-adoptions",
    ),
    path("resources/<int:resource_pk>/adopt/", views.CurriculumResourceAdoptView.as_view(), name="resource-adopt"),
    path("adoptions/<int:adoption_pk>/diverge/", views.CurriculumAdoptionDivergeView.as_view(), name="adoption-diverge"),
]
