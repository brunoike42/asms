from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from apps.attendance.biometric_api import BiometricScanView

urlpatterns = [
    path('admin/',         admin.site.urls),
    path('accounts/',      include('apps.accounts.urls',      namespace='accounts')),
    path('students/',      include('apps.students.urls',      namespace='students')),
    path('admissions/',    include('apps.admissions.urls',    namespace='admissions')),
    path('attendance/',    include('apps.attendance.urls',    namespace='attendance')),
    path('finance/',       include('apps.finance.urls',       namespace='finance')),
    path('communication/', include('apps.communication.urls', namespace='communication')),
   path('dashboard/',     include('apps.core.urls',          namespace='core')),
    path('academics/', include('apps.academics.urls')),
    path('exams/', include('apps.exams.urls')),
    path('staff_hr/', include('apps.staff_hr.urls')),
    path('lms/', include('apps.lms.urls')),
    path('assignments/', include('apps.assignments.urls')),
    path('library/', include('apps.library.urls')),
    path('discipline/', include('apps.discipline.urls', namespace='discipline')),
    path('counselling/', include('apps.counselling.urls', namespace='counselling')),
    path('payments/', include('apps.payments.urls', namespace='payments')),
     path('parent/',       include('apps.parent_portal.urls', namespace='parent')), 
    path('portal/', include('apps.student_portal.urls', namespace='student_portal')),
    path('visitor/', include('apps.visitor.urls', namespace='visitor')),
    path('api/v1/transport/', include('apps.transport.urls', namespace='transport')),
    path('api/biometric/v1/scan/', BiometricScanView.as_view(), name='biometric_scan'),
    path('emis/', include('apps.emis.urls', namespace='emis')),
    path("webhooks/sms/", include("apps.notifications.urls")),
     path("api/v1/networks/", include("apps.networks.urls")),
    path("api/v1/curriculum/", include("apps.curriculum.urls")),

    path('register/', include('apps.platform_billing.urls', namespace='platform_billing')),
    path('platform-admin/', include('apps.platform_billing.admin_urls', namespace='platform_admin')),
    

    path('',               lambda r: redirect('core:dashboard'), name='home'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


