from django.urls import path
from . import admin_views

app_name = 'platform_admin'

urlpatterns = [
    path('', admin_views.dashboard, name='dashboard'),
    path('tenants/', admin_views.tenant_list, name='tenant_list'),
    path('tenants/<int:pk>/', admin_views.tenant_detail, name='tenant_detail'),
    path('tenants/<int:pk>/extend-trial/', admin_views.tenant_extend_trial, name='tenant_extend_trial'),
    path('tenants/<int:pk>/change-plan/', admin_views.tenant_change_plan, name='tenant_change_plan'),
    path('tenants/<int:pk>/discount/', admin_views.tenant_apply_discount, name='tenant_apply_discount'),
    path('tenants/<int:pk>/toggle-feature/', admin_views.tenant_toggle_feature, name='tenant_toggle_feature'),
    path('revenue/', admin_views.revenue_report, name='revenue_report'),
]
