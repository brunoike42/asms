from django.urls import path
from . import views
app_name = 'admissions'
urlpatterns = [
    path('',              views.application_list,   name='list'),
    path('new/',          views.application_create, name='create'),
    path('<int:pk>/',     views.application_detail, name='detail'),
    path('<int:pk>/edit/', views.application_edit,  name='edit'),
]
