from django.urls import path
from . import views

app_name = 'visitor'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Check-in flow
    path('checkin/', views.checkin, name='checkin'),
    path('checkin/<int:visitor_pk>/', views.checkin_known, name='checkin_known'),
    path('lookup/', views.visitor_lookup, name='visitor_lookup'),
    path('log/<int:pk>/checkout/', views.checkout, name='checkout'),
    path('log/<int:pk>/badge/', views.badge_print, name='badge_print'),
    path('onsite/', views.onsite_list, name='onsite_list'),

    # Pre-registration (expected visitors)
    path('expected/', views.expected_today, name='expected_today'),
    path('expected/new/', views.expected_create, name='expected_create'),
    path('expected/<int:pk>/cancel/', views.expected_cancel, name='expected_cancel'),

    # Emergency muster
    path('muster/', views.muster_report, name='muster_report'),

    # Watchlist
    path('watchlist/', views.watchlist_list, name='watchlist_list'),
    path('watchlist/new/', views.watchlist_create, name='watchlist_create'),
    path('watchlist/<int:pk>/deactivate/', views.watchlist_deactivate, name='watchlist_deactivate'),
]