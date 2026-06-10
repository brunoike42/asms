from django.urls import path
from . import views

urlpatterns = [
    path('',                                    views.lms_dashboard,      name='lms_dashboard'),
    path('resources/',                          views.resource_list,      name='resource_list'),
    path('resources/<int:class_subject_id>/',   views.resource_list,      name='resource_list_cs'),
    path('resources/add/',                      views.resource_create,    name='resource_create'),
    path('lessons/',                            views.lesson_plan_list,   name='lesson_plan_list'),
    path('lessons/add/',                        views.lesson_plan_create, name='lesson_plan_create'),
    path('quizzes/',                            views.quiz_list,          name='quiz_list'),
    path('quizzes/create/',                     views.quiz_create,        name='quiz_create'),
    path('quizzes/<int:quiz_id>/questions/',    views.quiz_add_questions, name='quiz_add_questions'),
    path('quizzes/<int:quiz_id>/publish/',      views.quiz_publish,       name='quiz_publish'),
]
