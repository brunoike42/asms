from django.urls import path
from . import dashboard_views

app_name = 'network_admin'

urlpatterns = [
    path('', dashboard_views.network_list, name='dashboard'),
    path('<int:network_pk>/', dashboard_views.network_schools, name='network_schools'),
    path('<int:network_pk>/admins/', dashboard_views.network_admins, name='network_admins'),
    path('<int:network_pk>/admins/<int:role_pk>/toggle/', dashboard_views.network_admin_toggle, name='network_admin_toggle'),
    path('<int:network_pk>/rollups/', dashboard_views.network_rollups, name='network_rollups'),
    path('<int:network_pk>/curriculum/', dashboard_views.network_curriculum, name='network_curriculum'),
    path('<int:network_pk>/curriculum/<int:resource_pk>/publish/', dashboard_views.network_curriculum_publish, name='network_curriculum_publish'),
    path('<int:network_pk>/admins/add/', dashboard_views.network_admin_add, name='network_admin_add'),
path('<int:network_pk>/curriculum/new/', dashboard_views.network_curriculum_create, name='network_curriculum_create'),
]