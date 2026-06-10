from django.urls import path
from . import views

urlpatterns = [
    path('',                                views.exam_list,       name='exam_list'),
    path('create/',                         views.exam_create,     name='exam_create'),
    path('<int:exam_id>/marks/',            views.enter_marks,     name='enter_marks'),
    path('<int:exam_id>/publish/',          views.publish_exam,    name='publish_exam'),
    path('<int:exam_id>/results/',          views.exam_results,    name='exam_results'),
    path('reports/<int:term_id>/',          views.report_list,     name='report_list'),
    path('reports/<int:term_id>/compute/',  views.compute_reports, name='compute_reports'),
    path('reports/<int:term_id>/publish/',  views.publish_reports, name='publish_reports'),
    path('reports/student/<int:report_id>/',views.student_report,  name='student_report'),
]
