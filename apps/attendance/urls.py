from django.urls import path
from .biometric_api import BiometricScanView
from . import views
app_name = 'attendance'
urlpatterns = [
    path('',                            views.attendance_home,    name='home'),
    path('<int:classroom_pk>/mark/',    views.mark_attendance,    name='mark'),
     path('api/biometric/v1/scan/', BiometricScanView.as_view(), name='biometric_scan'),
    path('<int:classroom_pk>/report/',  views.attendance_report,  name='report'),
]
