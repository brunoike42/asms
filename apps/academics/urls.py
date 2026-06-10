from django.urls import path
from . import views

urlpatterns = [
    path('subjects/',              views.subject_list,        name='subject_list'),
    path('subjects/add/',          views.subject_create,      name='subject_create'),
    path('class-subjects/',        views.class_subject_list,  name='class_subject_list'),
    path('class-subjects/assign/', views.class_subject_assign,name='class_subject_assign'),
    path('timetable/',             views.timetable_view,      name='timetable_view'),
]
