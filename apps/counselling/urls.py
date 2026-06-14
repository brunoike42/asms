from django.urls import path
from . import views

app_name = 'counselling'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    path('at-risk/', views.at_risk_dashboard, name='at_risk_dashboard'),

    # Welfare Cases
    path('cases/', views.case_list, name='case_list'),
    path('cases/new/', views.case_create, name='case_create'),
    path('cases/<int:pk>/', views.case_detail, name='case_detail'),
    path('cases/<int:pk>/update/', views.update_case, name='update_case'),
    path('cases/<int:pk>/resolve/', views.resolve_case, name='resolve_case'),
    path('cases/<int:pk>/escalate/', views.escalate_case, name='escalate_case'),
    path('cases/<int:pk>/principal-response/', views.principal_response, name='principal_response'),

    # Sessions & Actions
    path('cases/<int:pk>/sessions/add/', views.add_session, name='add_session'),
    path('cases/<int:pk>/actions/add/', views.add_action, name='add_action'),
    path('cases/<int:pk>/referrals/add/', views.add_referral, name='add_referral'),

    # Bursary
    path('cases/<int:pk>/bursary/create/', views.create_bursary, name='create_bursary'),
    path('cases/<int:pk>/bursary/<int:bursary_pk>/approve/', views.approve_bursary, name='approve_bursary'),

    # Student welfare history
    path('students/<int:student_pk>/welfare/', views.student_welfare_history, name='student_welfare_history'),
]
