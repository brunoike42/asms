from django.urls import path
from . import views

urlpatterns = [
    path('',                                    views.assignment_list,   name='assignment_list'),
    path('create/',                             views.assignment_create, name='assignment_create'),
    path('<int:pk>/',                           views.assignment_detail, name='assignment_detail'),
    path('<int:pk>/publish/',                   views.publish_assignment,name='publish_assignment'),
    path('submission/<int:submission_id>/grade/',views.grade_submission, name='grade_submission'),
]
