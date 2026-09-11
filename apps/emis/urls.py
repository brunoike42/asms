from django.urls import path
from . import views

app_name = "emis"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("compliance/", views.run_compliance_check, name="compliance_check"),
    path("export/", views.generate_export, name="generate_export"),
    path("submissions/", views.submission_list, name="submission_list"),
    path("submissions/<int:pk>/", views.submission_detail, name="submission_detail"),
    path("infrastructure/", views.infrastructure_edit, name="infrastructure_edit"),
]
