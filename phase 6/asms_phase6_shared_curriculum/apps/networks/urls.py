"""
Mount this at /api/v1/networks/ in your project's root urlconf:

    # config/urls.py
    urlpatterns = [
        ...
        path("api/v1/networks/", include("apps.networks.urls")),
    ]
"""
from django.urls import path

from . import views

app_name = "networks"

urlpatterns = [
    path("networks/", views.NetworkListView.as_view(), name="network-list"),
    path("networks/<int:pk>/", views.NetworkDetailView.as_view(), name="network-detail"),
    path("networks/<int:network_pk>/schools/", views.NetworkSchoolsView.as_view(), name="network-schools"),
    path(
        "networks/<int:network_pk>/schools/<int:tenant_pk>/",
        views.NetworkSchoolDetailView.as_view(),
        name="network-school-detail",
    ),
    path("networks/<int:network_pk>/admins/", views.NetworkAdminsView.as_view(), name="network-admins"),
    path("networks/<int:network_pk>/logs/", views.NetworkQueryLogsView.as_view(), name="network-logs"),
    path("networks/<int:network_pk>/rollups/", views.NetworkRollupsView.as_view(), name="network-rollups"),
]
