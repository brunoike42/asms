from django.urls import path
from . import views

app_name = 'discipline'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Incidents
    path('incidents/', views.incident_list, name='incident_list'),
    path('incidents/new/', views.incident_create, name='incident_create'),
    path('incidents/<int:pk>/', views.incident_detail, name='incident_detail'),
    path('incidents/<int:pk>/edit/', views.incident_edit, name='incident_edit'),
    path('incidents/<int:pk>/resolve/', views.resolve_incident, name='resolve_incident'),
    path('incidents/<int:pk>/appeal/', views.appeal_incident, name='appeal_incident'),
    path('incidents/<int:pk>/appeal/outcome/', views.appeal_outcome, name='appeal_outcome'),

    # Workflow actions on an incident
    path('incidents/<int:pk>/investigation/', views.save_investigation, name='save_investigation'),
    path('incidents/<int:pk>/principal-review/', views.principal_review, name='principal_review'),
    path('incidents/<int:pk>/notify-parent/', views.mark_parent_notified, name='mark_parent_notified'),

    # Consequences
    path('incidents/<int:pk>/consequences/add/', views.add_consequence, name='add_consequence'),
    path('incidents/<int:pk>/consequences/<int:consequence_pk>/approve/', views.approve_consequence, name='approve_consequence'),
    path('incidents/<int:pk>/consequences/<int:consequence_pk>/complete/', views.complete_consequence, name='complete_consequence'),

    # Witnesses & Evidence
    path('incidents/<int:pk>/witnesses/add/', views.add_witness, name='add_witness'),
    path('incidents/<int:pk>/evidence/add/', views.add_evidence, name='add_evidence'),

    # Student history
    path('students/<int:student_pk>/history/', views.student_history, name='student_history'),

    # Merits
    path('merits/', views.merit_list, name='merit_list'),
    path('merits/new/', views.merit_create, name='merit_create'),

    # Categories
    path('categories/', views.category_list, name='category_list'),
    path('categories/new/', views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_edit, name='category_edit'),
]
