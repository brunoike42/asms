from django.urls import path
from . import views
app_name = 'attendance'
urlpatterns = [
    path('',                            views.attendance_home,    name='home'),
    path('<int:classroom_pk>/mark/',    views.mark_attendance,    name='mark'),
    path('<int:classroom_pk>/report/',  views.attendance_report,  name='report'),
]
