from django.urls import path
from . import views

urlpatterns = [
    path('',                          views.staff_list,   name='staff_list'),
    path('add/',                      views.staff_create, name='staff_create'),
    path('<int:pk>/',                 views.staff_detail, name='staff_detail'),
    path('leave/',                    views.leave_list,   name='leave_list'),
    path('leave/apply/',              views.leave_apply,  name='leave_apply'),
    path('leave/<int:pk>/<str:action>/', views.leave_action, name='leave_action'),
    path('cpd/',                      views.cpd_list,     name='cpd_list'),
    path('cpd/add/',                  views.cpd_create,   name='cpd_create'),
]
