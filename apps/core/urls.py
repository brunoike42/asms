from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('',           views.dashboard,           name='dashboard'),
    path('teacher/',   views.teacher_dashboard,   name='teacher_dashboard'),
    path('finance/',   views.finance_dashboard,   name='finance_dashboard'),
    path('welfare/',   views.welfare_dashboard,   name='welfare_dashboard'),
    path('library/',   views.library_dashboard,   name='library_dashboard'),
    path('visitor/',   views.visitor_dashboard,   name='visitor_dashboard'),
    path('principal/', views.principal_dashboard, name='principal_dashboard'),
]